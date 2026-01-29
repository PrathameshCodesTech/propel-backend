from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict

from django.db.models import Sum, Count, Avg, F, Q
from django.db.models.functions import Coalesce
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from finance.models import (
    Vendor,
    VendorBill,
    CashFlowEntry,
    CashFlowForecast,
)
from crm.models import Customer, CustomerPayment, Booking
from projects.models import Project
from analytics.models import OrgMonthlySnapshot, ProjectKPI_Daily
from .views import get_org, calculate_trend


class FinanceCashflowAPIView(APIView):
    """
    API endpoint for Finance & Cashflow dashboard.
    Returns KPIs, monthly cashflow, receivables/payables aging,
    project P&L, budget vs actual, cash flow forecast, and margin alerts.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        org = get_org(request)
        if not org:
            return Response({"detail": "No organization mapped to user."}, status=400)

        today = date.today()
        current_year = today.year
        current_month = today.month

        # ----------------------------
        # 1) KPIs
        # ----------------------------
        projects = Project.objects.filter(organization=org)

        # Get latest KPIs for revenue data
        latest_kpi_date = (
            ProjectKPI_Daily.objects
            .filter(project__organization=org)
            .order_by("-date")
            .values_list("date", flat=True)
            .first()
        )

        revenue_booked_ytd = Decimal("0")
        revenue_collected_ytd = Decimal("0")

        if latest_kpi_date:
            kpi_agg = (
                ProjectKPI_Daily.objects
                .filter(project__organization=org, date=latest_kpi_date)
                .aggregate(
                    booked=Sum("revenue_booked"),
                    collected=Sum("revenue_collected"),
                )
            )
            revenue_booked_ytd = kpi_agg["booked"] or Decimal("0")
            revenue_collected_ytd = kpi_agg["collected"] or Decimal("0")

        # Get trends from last year
        last_year_date = date(current_year - 1, current_month, 1)
        ly_snapshot = OrgMonthlySnapshot.objects.filter(
            organization=org,
            year=last_year_date.year,
            month=last_year_date.month
        ).first()

        revenue_booked_trend = None
        revenue_collected_trend = None
        if ly_snapshot:
            revenue_booked_trend = calculate_trend(
                float(revenue_booked_ytd),
                float(ly_snapshot.revenue_booked or 0)
            )
            revenue_collected_trend = calculate_trend(
                float(revenue_collected_ytd),
                float(ly_snapshot.revenue_collected or 0)
            )

        # ----------------------------
        # 2) Customer Receivables (Outstanding)
        # ----------------------------
        receivables_aging = []
        total_receivables = Decimal("0")
        overdue_90_plus = Decimal("0")

        # Get outstanding amounts from Bookings
        bookings = Booking.objects.filter(
            customer__project__organization=org
        ).select_related("customer")

        receivables_by_age = defaultdict(lambda: {"amount": Decimal("0"), "customers": set()})

        for booking in bookings:
            outstanding = (booking.booking_value or Decimal("0")) - (
                CustomerPayment.objects
                .filter(booking=booking)
                .aggregate(paid=Coalesce(Sum("amount"), Decimal("0")))["paid"]
            )

            if outstanding > 0:
                # Calculate days based on booking date
                booking_date = booking.booking_date or today
                days_outstanding = (today - booking_date).days

                if days_outstanding <= 30:
                    category = "0-30 days"
                elif days_outstanding <= 60:
                    category = "31-60 days"
                elif days_outstanding <= 90:
                    category = "61-90 days"
                else:
                    category = "90+ days"
                    overdue_90_plus += outstanding

                receivables_by_age[category]["amount"] += outstanding
                receivables_by_age[category]["customers"].add(booking.customer_id)
                total_receivables += outstanding

        # Order categories
        category_order = ["0-30 days", "31-60 days", "61-90 days", "90+ days"]
        for cat in category_order:
            data = receivables_by_age.get(cat, {"amount": Decimal("0"), "customers": set()})
            receivables_aging.append({
                "category": cat,
                "amount": float(data["amount"]),
                "customers": len(data["customers"]),
            })

        overdue_90_percent = round((float(overdue_90_plus) / float(total_receivables) * 100), 0) if total_receivables > 0 else 0

        # Receivables details for drilldown
        receivables_details = []
        customers_with_outstanding = (
            Customer.objects
            .filter(project__organization=org)
            .annotate(
                booking_value=Sum("bookings__booking_value"),
                paid=Coalesce(Sum("bookings__payments__amount"), Decimal("0")),
            )
            .filter(booking_value__gt=F("paid"))
            .select_related("project")
            .order_by("-booking_value")[:10]
        )

        for cust in customers_with_outstanding:
            outstanding = (cust.booking_value or Decimal("0")) - (cust.paid or Decimal("0"))
            walk_in_date = cust.walk_in_date or today
            days_overdue = (today - walk_in_date).days

            priority = "Low"
            if days_overdue > 90 or outstanding > 5000000:
                priority = "High"
            elif days_overdue > 60 or outstanding > 3000000:
                priority = "Medium"

            receivables_details.append({
                "customer": cust.name,
                "project": cust.project.name if cust.project else "N/A",
                "amount": float(outstanding),
                "days_overdue": max(0, days_overdue),
                "priority": priority,
            })

        # ----------------------------
        # 3) Vendor Payables
        # ----------------------------
        payables_aging = []
        total_payables = Decimal("0")
        due_now_amount = Decimal("0")

        payables_by_age = defaultdict(lambda: {"amount": Decimal("0"), "vendors": set()})

        unpaid_bills = VendorBill.objects.filter(
            project__organization=org,
            status__in=[VendorBill.Status.UNPAID, VendorBill.Status.PARTIAL]
        ).select_related("vendor")

        for bill in unpaid_bills:
            due_date = bill.due_date or today
            days_until_due = (due_date - today).days

            # Calculate remaining amount for partial payments
            paid_amount = bill.payments.aggregate(paid=Coalesce(Sum("amount"), Decimal("0")))["paid"]
            remaining = bill.amount - paid_amount

            if remaining > 0:
                if days_until_due <= 0:
                    category = "Due Now"
                    due_now_amount += remaining
                elif days_until_due <= 30:
                    category = "0-30 days"
                elif days_until_due <= 60:
                    category = "31-60 days"
                else:
                    category = "60+ days"

                payables_by_age[category]["amount"] += remaining
                payables_by_age[category]["vendors"].add(bill.vendor_id)
                total_payables += remaining

        # Order payables categories
        payables_order = ["Due Now", "0-30 days", "31-60 days", "60+ days"]
        for cat in payables_order:
            data = payables_by_age.get(cat, {"amount": Decimal("0"), "vendors": set()})
            payables_aging.append({
                "category": cat,
                "amount": float(data["amount"]),
                "vendors": len(data["vendors"]),
            })

        # Payables details for drilldown
        payables_details = []
        upcoming_bills = (
            VendorBill.objects
            .filter(
                project__organization=org,
                status__in=[VendorBill.Status.UNPAID, VendorBill.Status.PARTIAL]
            )
            .select_related("vendor", "project")
            .order_by("due_date")[:10]
        )

        for bill in upcoming_bills:
            paid_amount = bill.payments.aggregate(paid=Coalesce(Sum("amount"), Decimal("0")))["paid"]
            remaining = bill.amount - paid_amount
            due_date = bill.due_date or today
            days_until_due = (due_date - today).days

            if days_until_due <= 0:
                status = "Due Now"
            elif days_until_due <= 30:
                status = "0-30 days"
            else:
                status = "31-60 days"

            payables_details.append({
                "vendor": bill.vendor.name,
                "category": bill.project.name if bill.project else "General",
                "amount": float(remaining),
                "due_date": due_date.isoformat(),
                "status": status,
            })

        # ----------------------------
        # 4) Net Cashflow MTD
        # ----------------------------
        mtd_start = date(current_year, current_month, 1)
        mtd_inflow = CashFlowEntry.objects.filter(
            organization=org,
            flow_type=CashFlowEntry.FlowType.INFLOW,
            date__gte=mtd_start,
            date__lte=today
        ).aggregate(total=Coalesce(Sum("amount"), Decimal("0")))["total"]

        mtd_outflow = CashFlowEntry.objects.filter(
            organization=org,
            flow_type=CashFlowEntry.FlowType.OUTFLOW,
            date__gte=mtd_start,
            date__lte=today
        ).aggregate(total=Coalesce(Sum("amount"), Decimal("0")))["total"]

        net_cashflow_mtd = mtd_inflow - mtd_outflow

        # Get last month's net for trend
        last_month = date(current_year, current_month - 1 if current_month > 1 else 12, 1)
        if current_month == 1:
            last_month = date(current_year - 1, 12, 1)

        lm_snapshot = OrgMonthlySnapshot.objects.filter(
            organization=org,
            year=last_month.year,
            month=last_month.month
        ).first()

        cashflow_trend = None
        if lm_snapshot and lm_snapshot.net_cashflow:
            cashflow_trend = calculate_trend(float(net_cashflow_mtd), float(lm_snapshot.net_cashflow))

        kpis = {
            "revenue_booked_ytd": float(revenue_booked_ytd),
            "revenue_booked_trend": revenue_booked_trend,
            "revenue_collected_ytd": float(revenue_collected_ytd),
            "revenue_collected_trend": revenue_collected_trend,
            "total_receivables": float(total_receivables),
            "overdue_90_percent": overdue_90_percent,
            "total_payables": float(total_payables),
            "net_cashflow_mtd": float(net_cashflow_mtd),
            "cashflow_trend": cashflow_trend,
            "is_positive_cashflow": net_cashflow_mtd >= 0,
        }

        # ----------------------------
        # 5) Monthly Cashflow Data (last 12 months)
        # ----------------------------
        monthly_cashflow = []
        # Get last 12 months by ordering descending and limiting, then reverse
        months_qs = list(
            OrgMonthlySnapshot.objects
            .filter(organization=org)
            .order_by("-year", "-month")[:12]
        )
        months_qs.reverse()  # Reverse to get chronological order

        for snapshot in months_qs:
            month_name = date(snapshot.year, snapshot.month, 1).strftime("%b")
            monthly_cashflow.append({
                "month": month_name,
                "inflow": float(snapshot.cash_inflow or 0) / 10000000,  # Convert to Cr
                "outflow": float(snapshot.cash_outflow or 0) / 10000000,
                "net": float(snapshot.net_cashflow or 0) / 10000000,
            })

        # ----------------------------
        # 6) Cash Flow Forecast (6 months)
        # ----------------------------
        forecast_data = []
        forecast_summary = {
            "total_inflow": 0,
            "total_outflow": 0,
            "avg_monthly_net": 0,
            "low_confidence_months": 0,
        }

        forecasts = (
            CashFlowForecast.objects
            .filter(organization=org)
            .filter(
                Q(year=current_year, month__gte=current_month) |
                Q(year=current_year + 1)
            )
            .order_by("year", "month")[:6]
        )

        total_forecast_inflow = Decimal("0")
        total_forecast_outflow = Decimal("0")
        low_confidence_count = 0

        for fc in forecasts:
            month_label = date(fc.year, fc.month, 1).strftime("%b %Y")
            risks = [r.strip() for r in fc.key_risks.split(",") if r.strip()] if fc.key_risks else []

            forecast_data.append({
                "month": month_label,
                "projected_inflow": float(fc.projected_inflow),
                "projected_outflow": float(fc.projected_outflow),
                "net_cashflow": float(fc.net_cashflow),
                "cumulative_cash": float(fc.cumulative),
                "confidence": fc.confidence.capitalize() if fc.confidence else "Medium",
                "risks": risks,
            })

            total_forecast_inflow += fc.projected_inflow
            total_forecast_outflow += fc.projected_outflow
            if fc.confidence == CashFlowForecast.Confidence.LOW:
                low_confidence_count += 1

        forecast_count = len(forecast_data)
        if forecast_count > 0:
            forecast_summary = {
                "total_inflow": float(total_forecast_inflow),
                "total_outflow": float(total_forecast_outflow),
                "avg_monthly_net": float(total_forecast_inflow - total_forecast_outflow) / forecast_count,
                "low_confidence_months": low_confidence_count,
            }

        # ----------------------------
        # 7) Project P&L
        # ----------------------------
        project_pnl = []
        for project in projects:
            kpi = None
            if latest_kpi_date:
                kpi = ProjectKPI_Daily.objects.filter(project=project, date=latest_kpi_date).first()

            revenue = float(kpi.revenue_booked or 0) if kpi else 0
            cost = float(kpi.cost_incurred or 0) if kpi else 0
            margin = round(((revenue - cost) / revenue * 100), 1) if revenue > 0 else 0

            if margin > 30:
                status = "Healthy"
            elif margin > 15:
                status = "At Risk"
            else:
                status = "Loss"

            project_pnl.append({
                "project_id": project.id,
                "name": project.name.split()[0] if project.name else "",
                "full_name": project.name,
                "revenue": revenue / 10000000,  # Convert to Cr
                "cost": cost / 10000000,
                "margin": margin,
                "status": status,
            })

        # ----------------------------
        # 8) Budget vs Actual
        # ----------------------------
        budget_vs_actual = []
        for project in projects:
            kpi = None
            if latest_kpi_date:
                kpi = ProjectKPI_Daily.objects.filter(project=project, date=latest_kpi_date).first()

            budget = float(project.budget or 0)
            actual = float(kpi.cost_incurred or 0) if kpi else 0
            variance = round(((actual - budget) / budget * 100), 1) if budget > 0 else 0

            budget_vs_actual.append({
                "project_id": project.id,
                "name": project.name.split()[0] if project.name else "",
                "full_name": project.name,
                "budget": budget / 10000000,
                "actual": actual / 10000000,
                "variance": variance,
            })

        # ----------------------------
        # 9) Margin Alerts
        # ----------------------------
        margin_alerts = []

        # Find cost overrun projects
        for item in budget_vs_actual:
            if item["variance"] > 5:  # More than 5% over budget
                overrun_cr = item["actual"] - item["budget"]  # already in Cr
                margin_alerts.append({
                    "type": "cost_overrun",
                    "title": "Cost Overrun",
                    "value": f"{overrun_cr:.1f} Cr" if overrun_cr >= 0.01 else f"{abs(item['variance'])}%",
                    "description": f"{item['full_name']} project exceeding budget by {abs(item['variance']):.1f}%",
                    "severity": "high" if item["variance"] > 10 else "medium",
                })
                break  # Only show one

        # Material cost alert (simplified - in real app would track material costs)
        margin_alerts.append({
            "type": "material_cost",
            "title": "Material Cost Spike",
            "value": "+15%",
            "description": "Steel and cement prices increased YoY",
            "severity": "medium",
        })

        # Labor cost alert
        margin_alerts.append({
            "type": "labor_cost",
            "title": "Labor Cost Variance",
            "value": "3.8 Cr",
            "description": "Overtime costs due to schedule recovery",
            "severity": "medium",
        })

        return Response({
            "kpis": kpis,
            "receivables_aging": receivables_aging,
            "receivables_details": receivables_details,
            "payables_aging": payables_aging,
            "payables_details": payables_details,
            "monthly_cashflow": monthly_cashflow,
            "forecast": forecast_data,
            "forecast_summary": forecast_summary,
            "project_pnl": project_pnl,
            "budget_vs_actual": budget_vs_actual,
            "margin_alerts": margin_alerts,
        })
