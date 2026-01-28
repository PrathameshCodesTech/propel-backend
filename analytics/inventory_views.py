from datetime import date
from decimal import Decimal
from collections import defaultdict

from django.db.models import Sum, Count, Avg, F, Q, Case, When, Value, IntegerField
from django.db.models.functions import Coalesce
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from analytics.models import (
    ProjectKPI_Daily,
    InventoryAgingMonthly,
    PriceBandAnalysis,
    OrgKPI_Daily,
)
from projects.models import Project, Unit
from core.models import Organization
from .views import get_org, calculate_trend


class InventoryAPIView(APIView):
    """
    API endpoint for Inventory & Unsold Units dashboard.
    Returns KPIs, project-wise inventory, unit type distribution,
    price band analysis, and inventory aging data.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        org = get_org(request)
        if not org:
            return Response({"detail": "No organization mapped to user."}, status=400)

        project_filter = request.query_params.get("project_id")

        # ----------------------------
        # 1) Get latest ProjectKPI_Daily date
        # ----------------------------
        latest_kpi_date = (
            ProjectKPI_Daily.objects
            .filter(project__organization=org)
            .order_by("-date")
            .values_list("date", flat=True)
            .first()
        )

        # Get previous month's date for trend calculation
        today = date.today()
        last_month_start = date(today.year, today.month - 1 if today.month > 1 else 12, 1)
        if today.month == 1:
            last_month_start = date(today.year - 1, 12, 1)

        # ----------------------------
        # 2) Build project-wise inventory data
        # ----------------------------
        projects_data = []
        total_unsold = 0
        total_unsold_value = Decimal("0")
        total_blocked = 0
        total_sold = 0
        total_booked = 0
        total_units = 0

        projects_qs = Project.objects.filter(organization=org)
        if project_filter and project_filter != "all":
            projects_qs = projects_qs.filter(id=project_filter)

        for project in projects_qs:
            # Get latest KPI for this project
            kpi = None
            if latest_kpi_date:
                kpi = ProjectKPI_Daily.objects.filter(
                    project=project, date=latest_kpi_date
                ).first()

            # If KPI exists, use it; otherwise calculate from Unit model
            if kpi:
                sold = int(kpi.sold_units or 0)
                booked = int(kpi.booked_units or 0)
                blocked = int(kpi.blocked_units or 0)
                unsold = int(kpi.unsold_units or 0)
                proj_total = int(kpi.total_units or 0)
            else:
                # Fallback: calculate from Unit model
                unit_counts = Unit.objects.filter(project=project).aggregate(
                    sold=Count("id", filter=Q(status=Unit.Status.SOLD)),
                    booked=Count("id", filter=Q(status=Unit.Status.BOOKED)),
                    blocked=Count("id", filter=Q(status=Unit.Status.BLOCKED)),
                    available=Count("id", filter=Q(status=Unit.Status.AVAILABLE)),
                    total=Count("id"),
                )
                sold = unit_counts["sold"] or 0
                booked = unit_counts["booked"] or 0
                blocked = unit_counts["blocked"] or 0
                unsold = unit_counts["available"] or 0
                proj_total = unit_counts["total"] or 0

            # Calculate unsold value (average unit price * unsold units)
            avg_price = Unit.objects.filter(
                project=project, status=Unit.Status.AVAILABLE
            ).aggregate(avg=Avg("final_price"))["avg"] or Decimal("0")

            if avg_price == 0:
                # Fallback to base_price if final_price not set
                avg_price = Unit.objects.filter(
                    project=project
                ).aggregate(avg=Avg("base_price"))["avg"] or Decimal("8500000")

            unsold_value = Decimal(unsold) * avg_price

            projects_data.append({
                "project_id": project.id,
                "name": project.name,
                "short_name": project.name.split()[0] if project.name else "",
                "location": project.location,
                "total_units": proj_total,
                "sold": sold,
                "booked": booked,
                "blocked": blocked,
                "unsold": unsold,
                "unsold_value": float(unsold_value),
                "avg_price_per_unit": float(avg_price),
            })

            total_unsold += unsold
            total_unsold_value += unsold_value
            total_blocked += blocked
            total_sold += sold
            total_booked += booked
            total_units += proj_total

        # ----------------------------
        # 3) KPIs
        # ----------------------------
        # Get last month's unsold for trend
        last_month_unsold = None
        if last_month_start:
            lm_kpi = (
                ProjectKPI_Daily.objects
                .filter(
                    project__organization=org,
                    date__year=last_month_start.year,
                    date__month=last_month_start.month
                )
                .aggregate(unsold=Sum("unsold_units"))
            )
            last_month_unsold = lm_kpi.get("unsold")

        unsold_trend = calculate_trend(total_unsold, last_month_unsold)

        # Calculate average days on market
        # Use InventoryAgingMonthly if available, otherwise estimate from Unit listed_date
        avg_days_on_market = 0
        aging_data = InventoryAgingMonthly.objects.filter(
            project__organization=org,
            year=today.year,
            month=today.month
        ).aggregate(
            total_unsold=Sum("unsold_units"),
            weighted_age=Sum(F("unsold_units") * F("avg_unsold_age_days"))
        )

        if aging_data["total_unsold"] and aging_data["total_unsold"] > 0:
            avg_days_on_market = int(
                aging_data["weighted_age"] / aging_data["total_unsold"]
            )
        else:
            # Fallback: calculate from Unit.listed_date
            available_units = Unit.objects.filter(
                project__organization=org,
                status=Unit.Status.AVAILABLE,
                listed_date__isnull=False
            )
            if available_units.exists():
                total_days = sum(
                    (today - u.listed_date).days
                    for u in available_units
                    if u.listed_date
                )
                avg_days_on_market = total_days // available_units.count() if available_units.count() > 0 else 0

        # Get last month's avg days for trend
        last_month_aging = InventoryAgingMonthly.objects.filter(
            project__organization=org,
            year=last_month_start.year,
            month=last_month_start.month
        ).aggregate(
            total_unsold=Sum("unsold_units"),
            weighted_age=Sum(F("unsold_units") * F("avg_unsold_age_days"))
        )
        last_month_avg_days = None
        if last_month_aging["total_unsold"] and last_month_aging["total_unsold"] > 0:
            last_month_avg_days = int(
                last_month_aging["weighted_age"] / last_month_aging["total_unsold"]
            )

        days_on_market_trend = calculate_trend(avg_days_on_market, last_month_avg_days)
        # Invert the trend (lower is better)
        if days_on_market_trend is not None:
            days_on_market_trend = -days_on_market_trend

        # Determine price sensitivity based on enquiry-to-booking ratio
        # This is a simplified heuristic
        price_sensitivity = "Medium"
        if total_unsold > 0:
            unsold_ratio = total_unsold / total_units if total_units > 0 else 0
            if unsold_ratio > 0.4:
                price_sensitivity = "High"
            elif unsold_ratio < 0.2:
                price_sensitivity = "Low"

        kpis = {
            "total_unsold": total_unsold,
            "total_unsold_value": float(total_unsold_value),
            "avg_days_on_market": avg_days_on_market,
            "blocked_units": total_blocked,
            "price_sensitivity": price_sensitivity,
            "trends": {
                "total_unsold": {
                    "value": unsold_trend,
                    "label": "vs LM"
                },
                "avg_days_on_market": {
                    "value": days_on_market_trend,
                    "label": "improving" if days_on_market_trend and days_on_market_trend < 0 else "vs LM"
                }
            }
        }

        # ----------------------------
        # 4) Unit Type Distribution
        # ----------------------------
        unit_type_qs = (
            Unit.objects
            .filter(project__organization=org, status=Unit.Status.AVAILABLE)
            .values("unit_type__label")
            .annotate(
                count=Count("id"),
                avg_price=Avg("final_price")
            )
            .order_by("unit_type__label")
        )

        unit_type_data = []
        colors = [
            "hsl(var(--chart-1))",
            "hsl(var(--chart-2))",
            "hsl(var(--chart-3))",
            "hsl(var(--chart-4))",
            "hsl(var(--chart-5))",
        ]
        for idx, ut in enumerate(unit_type_qs):
            unit_type_label = ut["unit_type__label"] or "Unknown"
            unit_type_data.append({
                "type": unit_type_label,
                "count": ut["count"],
                "avg_price": float(ut["avg_price"] or 0),
                "color": colors[idx % len(colors)],
            })

        # If no unit types found, provide default data
        if not unit_type_data:
            # Fallback: group by a simple heuristic or show "All Units"
            total_available = Unit.objects.filter(
                project__organization=org,
                status=Unit.Status.AVAILABLE
            ).count()
            avg_price_all = Unit.objects.filter(
                project__organization=org,
                status=Unit.Status.AVAILABLE
            ).aggregate(avg=Avg("final_price"))["avg"] or 0

            unit_type_data = [{
                "type": "All Units",
                "count": total_available,
                "avg_price": float(avg_price_all),
                "color": colors[0],
            }]

        # ----------------------------
        # 5) Price Band Analysis
        # ----------------------------
        price_bands = []
        price_band_qs = PriceBandAnalysis.objects.filter(
            project__organization=org,
            year=today.year,
            month=today.month
        ).values("price_range_label", "demand_level", "action").annotate(
            units=Sum("unsold_units")
        ).order_by("price_range_label")

        if price_band_qs.exists():
            for pb in price_band_qs:
                price_bands.append({
                    "range": pb["price_range_label"],
                    "units": pb["units"] or 0,
                    "demand": pb["demand_level"].capitalize() if pb["demand_level"] else "Medium",
                    "action": dict(PriceBandAnalysis.Action.choices).get(
                        pb["action"], "Maintain Pricing"
                    ),
                })
        else:
            # Fallback: calculate from Unit prices
            price_ranges = [
                ("40-60L", 4000000, 6000000),
                ("60-80L", 6000000, 8000000),
                ("80L-1Cr", 8000000, 10000000),
                ("1-1.2Cr", 10000000, 12000000),
                ("1.2-1.5Cr", 12000000, 15000000),
                ("1.5Cr+", 15000000, 999999999),
            ]
            for label, min_price, max_price in price_ranges:
                count = Unit.objects.filter(
                    project__organization=org,
                    status=Unit.Status.AVAILABLE,
                    final_price__gte=min_price,
                    final_price__lt=max_price
                ).count()

                # Determine demand based on proportion of total
                demand = "Medium"
                if total_unsold > 0:
                    ratio = count / total_unsold
                    if ratio > 0.25:
                        demand = "High"
                    elif ratio < 0.1:
                        demand = "Low"

                action = "Maintain pricing" if demand != "Low" else "Consider price revision"

                price_bands.append({
                    "range": label,
                    "units": count,
                    "demand": demand,
                    "action": action,
                })

        # ----------------------------
        # 6) Inventory Aging
        # ----------------------------
        aging_categories = []
        aging_qs = InventoryAgingMonthly.objects.filter(
            project__organization=org,
            year=today.year,
            month=today.month
        )

        if aging_qs.exists():
            # Group by age ranges if we have detailed data
            # For now, aggregate what we have
            for aging in aging_qs:
                avg_age = aging.avg_unsold_age_days
                unsold = aging.unsold_units

                # Categorize
                if avg_age <= 30:
                    category = "0-30 days"
                elif avg_age <= 60:
                    category = "31-60 days"
                elif avg_age <= 90:
                    category = "61-90 days"
                else:
                    category = "90+ days"

                # Find or create category
                found = False
                for cat in aging_categories:
                    if cat["category"] == category:
                        cat["units"] += unsold
                        found = True
                        break
                if not found:
                    aging_categories.append({
                        "category": category,
                        "units": unsold
                    })
        else:
            # Fallback: calculate from Unit.listed_date
            categories_map = defaultdict(int)
            available_units = Unit.objects.filter(
                project__organization=org,
                status=Unit.Status.AVAILABLE
            )

            for unit in available_units:
                if unit.listed_date:
                    days = (today - unit.listed_date).days
                    if days <= 30:
                        categories_map["0-30 days"] += 1
                    elif days <= 60:
                        categories_map["31-60 days"] += 1
                    elif days <= 90:
                        categories_map["61-90 days"] += 1
                    else:
                        categories_map["90+ days"] += 1
                else:
                    # If no listed_date, assume recent
                    categories_map["0-30 days"] += 1

            # Ensure all categories exist
            for cat in ["0-30 days", "31-60 days", "61-90 days", "90+ days"]:
                aging_categories.append({
                    "category": cat,
                    "units": categories_map.get(cat, 0)
                })

        # Sort aging categories
        category_order = {"0-30 days": 0, "31-60 days": 1, "61-90 days": 2, "90+ days": 3}
        aging_categories.sort(key=lambda x: category_order.get(x["category"], 99))

        # Calculate units aging beyond 90 days for warning
        units_over_90 = sum(
            cat["units"] for cat in aging_categories
            if cat["category"] == "90+ days"
        )

        # ----------------------------
        # 7) Projects list for filter dropdown
        # ----------------------------
        projects_list = [
            {"id": p.id, "name": p.name}
            for p in Project.objects.filter(organization=org).order_by("name")
        ]

        return Response({
            "kpis": kpis,
            "projects_inventory": projects_data,
            "unit_type_distribution": unit_type_data,
            "price_bands": price_bands,
            "inventory_aging": aging_categories,
            "units_over_90_days": units_over_90,
            "projects_list": projects_list,
        })
