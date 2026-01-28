from datetime import date
from dateutil.relativedelta import relativedelta

from django.db.models import Sum, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,AllowAny

from analytics.models import OrgKPI_Daily, OrgMonthlySnapshot, ProjectKPI_Daily
from alerts.models import Alert
from crm.models import Complaint
from compliance.models import ComplianceItem
from projects.models import Project
from core.models import Organization
from django.conf import settings


def get_org(request):
    """
    Multi-tenant org resolution:
    1. Authenticated user with employee_profile.organization → use that (org admin sees only their org).
    2. Staff/superuser with org_code in query → use that org (admin override for upload/testing).
    3. Unauthenticated: org_code from query (dev/testing).
    4. DEBUG: fallback to first organization.
    """
    # 1) Authenticated user: prefer their org (org admin sees only their data)
    if getattr(request.user, "is_authenticated", False):
        emp = getattr(request.user, "employee_profile", None)
        if emp and emp.organization:
            # Staff can override via org_code (e.g. for upload or viewing another org)
            if request.user.is_staff:
                org_code = request.query_params.get("org_code")
                if org_code:
                    org = Organization.objects.filter(code=org_code).first()
                    if org:
                        return org
            return emp.organization
        # Authenticated but no employee profile: staff can still use org_code
        if request.user.is_staff:
            org_code = request.query_params.get("org_code")
            if org_code:
                org = Organization.objects.filter(code=org_code).first()
                if org:
                    return org
        return None

    # 2) Not authenticated: org_code from query (dev/testing, current frontend behavior)
    org_code = request.query_params.get("org_code")
    if org_code:
        org = Organization.objects.filter(code=org_code).first()
        if org:
            return org

    # 3) DEBUG fallback
    if settings.DEBUG:
        org = Organization.objects.first()
        if org:
            return org

    return None


def month_range(months: int):
    # end month = current month start
    end = date.today().replace(day=1)
    start = (end - relativedelta(months=months - 1))
    return start, end


def calculate_trend(current_value, previous_value):
    """Calculate percentage trend between current and previous value."""
    if not previous_value or previous_value == 0:
        return None
    if current_value is None:
        current_value = 0
    return round(((current_value - previous_value) / previous_value) * 100, 1)


def normalize_status(status):
    """Normalize status from backend format to frontend format."""
    status_map = {
        "on_track": "on-track",
        "at_risk": "at-risk",
        "delayed": "delayed",
        "stalled": "stalled",
        "completed": "completed",
    }
    return status_map.get(status, status)


class ExecutiveOverviewAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        org = get_org(request)
        if not org:
            return Response({"detail": "No organization mapped to user."}, status=400)

        months = int(request.query_params.get("months", 12))
        months = max(1, min(months, 24))
        start, end = month_range(months)

        # ----------------------------
        # 1) KPI cards (daily snapshot)
        # ----------------------------
        kpi = (
            OrgKPI_Daily.objects
            .filter(organization=org)
            .order_by("-date")
            .first()
        )

        # Get current date for trend calculations
        today = date.today()
        current_year = today.year
        current_month = today.month
        current_quarter = (current_month - 1) // 3 + 1
        
        # Calculate previous periods for trends
        # Last Year: same month, previous year
        last_year_date = today.replace(year=current_year - 1) if current_year > 1 else None
        
        # Last Month: previous month
        last_month = today - relativedelta(months=1)
        
        # Last Quarter: use the last month of previous quarter
        # For simplicity, we'll use 3 months ago as "last quarter" comparison point
        last_quarter_date = today - relativedelta(months=3)
        
        # Get historical KPIs for trend calculations
        kpi_last_year = None
        kpi_last_month = None
        kpi_last_quarter = None
        
        if last_year_date:
            kpi_last_year = (
                OrgKPI_Daily.objects
                .filter(organization=org, date__year=last_year_date.year, date__month=last_year_date.month)
                .order_by("-date")
                .first()
            )
        
        if last_month:
            kpi_last_month = (
                OrgKPI_Daily.objects
                .filter(organization=org, date__year=last_month.year, date__month=last_month.month)
                .order_by("-date")
                .first()
            )
        
        # For last quarter, get the KPI from 3 months ago
        if last_quarter_date:
            kpi_last_quarter = (
                OrgKPI_Daily.objects
                .filter(organization=org, date__year=last_quarter_date.year, date__month=last_quarter_date.month)
                .order_by("-date")
                .first()
            )

        # Current values (handle None kpi case)
        total_units = int(getattr(kpi, "total_units", 0) or 0) if kpi else 0
        revenue_booked = float(getattr(kpi, "revenue_booked", 0) or 0) if kpi else 0.0
        revenue_collected = float(getattr(kpi, "revenue_collected", 0) or 0) if kpi else 0.0
        outstanding = float(getattr(kpi, "outstanding", 0) or 0) if kpi else 0.0
        avg_construction = float(getattr(kpi, "avg_construction", 0) or 0) if kpi else 0.0
        customer_satisfaction = float(getattr(kpi, "satisfaction_avg", 0) or 0) if kpi else 0.0

        # Calculate trends
        total_units_trend_ly = calculate_trend(
            total_units,
            int(getattr(kpi_last_year, "total_units", 0) or 0) if kpi_last_year else None
        )
        revenue_booked_trend_lq = calculate_trend(
            revenue_booked,
            float(getattr(kpi_last_quarter, "revenue_booked", 0) or 0) if kpi_last_quarter else None
        )
        outstanding_trend_lm = calculate_trend(
            outstanding,
            float(getattr(kpi_last_month, "outstanding", 0) or 0) if kpi_last_month else None
        )
        customer_satisfaction_trend_lq = calculate_trend(
            customer_satisfaction,
            float(getattr(kpi_last_quarter, "satisfaction_avg", 0) or 0) if kpi_last_quarter else None
        )

        kpis = {
            "total_units": total_units,
            "revenue_booked": revenue_booked,
            "revenue_collected": revenue_collected,
            "outstanding": outstanding,
            "avg_construction": avg_construction,
            "customer_satisfaction": customer_satisfaction,
            "ring_alerts": int(getattr(kpi, "ring_alerts", 0) or 0) if kpi else 0,
            "stalled_projects": int(getattr(kpi, "stalled_projects", 0) or 0) if kpi else 0,
            "at_risk_projects": int(getattr(kpi, "at_risk_projects", 0) or 0) if kpi else 0,
            "active_complaints": int(getattr(kpi, "active_complaints", 0) or 0) if kpi else 0,
            "compliance_alerts": int(getattr(kpi, "compliance_alerts", 0) or 0) if kpi else 0,
            "net_cashflow_mtd": float(getattr(kpi, "net_cashflow_mtd", 0) or 0) if kpi else 0.0,
            # Trend calculations
            "trends": {
                "total_units": {
                    "value": total_units_trend_ly,
                    "label": "vs LY"
                },
                "revenue_booked": {
                    "value": revenue_booked_trend_lq,
                    "label": "vs LQ"
                },
                "outstanding": {
                    "value": outstanding_trend_lm,
                    "label": "vs LM"
                },
                "customer_satisfaction": {
                    "value": customer_satisfaction_trend_lq,
                    "label": "vs LQ"
                },
            },
        }

        # ----------------------------------
        # 2) Donut chart (portfolio units)
        # ----------------------------------
        latest_project_kpi_date = (
            ProjectKPI_Daily.objects
            .filter(project__organization=org)
            .order_by("-date")
            .values_list("date", flat=True)
            .first()
        )

        donut = {"labels": ["Sold", "Booked", "Blocked", "Unsold"], "values": [0, 0, 0, 0]}
        sold = 0
        booked = 0
        blocked = 0
        unsold = 0
        
        if latest_project_kpi_date:
            agg = (
                ProjectKPI_Daily.objects
                .filter(project__organization=org, date=latest_project_kpi_date)
                .aggregate(
                    sold=Sum("sold_units"),
                    booked=Sum("booked_units"),
                    blocked=Sum("blocked_units"),
                    unsold=Sum("unsold_units"),
                    total=Sum("total_units"),
                )
            )
            sold = int(agg["sold"] or 0)
            booked = int(agg["booked"] or 0)
            blocked = int(agg["blocked"] or 0)
            unsold = int(agg["unsold"] or 0)

            # fallback (if unsold not filled)
            if unsold == 0 and (agg.get("total") is not None):
                total = int(agg["total"] or 0)
                unsold = max(0, total - sold - booked - blocked)

            donut["values"] = [sold, booked, blocked, unsold]
        
        # Add unit breakdown to KPIs for easy access
        kpis.update({
            "sold_units": sold,
            "booked_units": booked,
            "blocked_units": blocked,
            "unsold_units": unsold,
        })

        # ----------------------------------
        # 3) Revenue trend (monthly line)
        # ----------------------------------
        months_qs = (
            OrgMonthlySnapshot.objects
            .filter(organization=org)
            .filter(Q(year__gt=start.year) | Q(year=start.year, month__gte=start.month))
            .filter(Q(year__lt=end.year) | Q(year=end.year, month__lte=end.month))
            .order_by("year", "month")
        )

        revenue_trend = {
            "x": [f"{m.year}-{str(m.month).zfill(2)}" for m in months_qs],
            "series": [
                {"name": "Booked", "data": [float(m.revenue_booked or 0) for m in months_qs]},
                {"name": "Collected", "data": [float(m.revenue_collected or 0) for m in months_qs]},
            ],
        }

        # ----------------------------------
        # 4) Cash position (monthly bar)
        # ----------------------------------
        cash_position = {
            "x": [f"{m.year}-{str(m.month).zfill(2)}" for m in months_qs],
            "series": [
                {"name": "Inflow", "data": [float(m.cash_inflow or 0) for m in months_qs]},
                {"name": "Outflow", "data": [float(m.cash_outflow or 0) for m in months_qs]},
            ],
        }

        # ----------------------------------
        # 5) Project status list (latest daily KPI)
        #  - UI needs: name, location, sold/total, progress actual/planned, status
        # ----------------------------------
        projects_status = []
        on_track_count = 0
        delayed_count = 0
        
        if latest_project_kpi_date:
            p_qs = (
                ProjectKPI_Daily.objects
                .filter(project__organization=org, date=latest_project_kpi_date)
                .select_related("project")
                .order_by("project__name")
            )
            for p in p_qs:
                normalized_status = normalize_status(p.project.status)
                if normalized_status == "on-track":
                    on_track_count += 1
                elif normalized_status == "delayed":
                    delayed_count += 1
                
                projects_status.append({
                    "project_id": p.project_id,
                    "project_name": p.project.name,
                    "location": p.project.location,
                    "status": normalized_status,  # Normalized status
                    "units_sold": int(p.sold_units or 0),
                    "units_booked": int(p.booked_units or 0),
                    "units_blocked": int(p.blocked_units or 0),
                    "total_units": int(p.total_units or 0),
                    "construction_percent": float(p.construction_percent or 0),
                    "planned_percent": float(getattr(p, "planned_percent", 0) or 0),
                    "revenue_booked": float(p.revenue_booked or 0),
                    "revenue_collected": float(p.revenue_collected or 0),
                    "outstanding": float(p.outstanding or 0),
                })
        else:
            for p in Project.objects.filter(organization=org).order_by("name"):
                normalized_status = normalize_status(p.status)
                if normalized_status == "on-track":
                    on_track_count += 1
                elif normalized_status == "delayed":
                    delayed_count += 1
                
                projects_status.append({
                    "project_id": p.id,
                    "project_name": p.name,
                    "location": p.location,
                    "status": normalized_status,  # Normalized status
                    "units_sold": 0,
                    "units_booked": 0,
                    "units_blocked": 0,
                    "total_units": 0,
                    "construction_percent": 0,
                    "planned_percent": 0,
                    "revenue_booked": 0,
                    "revenue_collected": 0,
                    "outstanding": 0,
                })
        
        # Add project counts to KPIs
        kpis.update({
            "on_track_projects": on_track_count,
            "delayed_projects": delayed_count,
        })
        
        # Calculate avg construction trend vs plan
        # Compare current avg_construction with average planned_percent from projects
        if projects_status:
            total_planned = sum(p.get("planned_percent", 0) for p in projects_status)
            avg_planned = total_planned / len(projects_status) if projects_status else 0
            avg_construction_trend = calculate_trend(avg_construction, avg_planned)
        else:
            # If no projects, set trend to None
            avg_construction_trend = None
        
        # Add avg_construction trend to trends dict
        kpis["trends"]["avg_construction"] = {
            "value": avg_construction_trend,
            "label": "vs plan"
        }

        # ----------------------------------
        # 6) Bottom stats (live counters) - fallback if KPI not filled
        # ----------------------------------
        if not kpi:
            ring_alerts = Alert.objects.filter(
                organization=org, is_resolved=False, priority=Alert.Priority.CRITICAL
            ).count()
            stalled_projects = Project.objects.filter(organization=org, status=Project.Status.STALLED).count()
            at_risk_projects = Project.objects.filter(organization=org, status=Project.Status.AT_RISK).count()
            active_complaints = Complaint.objects.filter(project__organization=org).exclude(status=Complaint.Status.RESOLVED).count()
            compliance_alerts = ComplianceItem.objects.filter(
                project__organization=org,
                status__in=[ComplianceItem.Status.PENDING, ComplianceItem.Status.NON_COMPLIANT],
            ).count()

            kpis.update({
                "ring_alerts": ring_alerts,
                "stalled_projects": stalled_projects,
                "at_risk_projects": at_risk_projects,
                "active_complaints": active_complaints,
                "compliance_alerts": compliance_alerts,
            })

        return Response({
            "kpis": kpis,
            "donut": donut,
            "revenue_trend": revenue_trend,
            "cash_position": cash_position,
            "projects_status": projects_status,
        })


class ExecutiveProjectDetailAPIView(APIView):
    """
    For your Project modal (click on a project row).
    """
    permission_classes = [AllowAny]

    def get(self, request, project_id: int):
        org = get_org(request)
        if not org:
            return Response({"detail": "No organization mapped to user."}, status=400)

        p = Project.objects.filter(organization=org, id=project_id).first()
        if not p:
            return Response({"detail": "Project not found."}, status=404)

        latest_date = (
            ProjectKPI_Daily.objects
            .filter(project=p)
            .order_by("-date")
            .values_list("date", flat=True)
            .first()
        )

        snap = None
        if latest_date:
            snap = ProjectKPI_Daily.objects.filter(project=p, date=latest_date).first()

        return Response({
            "project": {
                "id": p.id,
                "name": p.name,
                "location": p.location,
                "status": normalize_status(p.status),  # Normalized status
                "planned_start_date": p.planned_start_date,
                "expected_completion_date": p.expected_completion_date,
            },
            "kpi": {
                "total_units": int(getattr(snap, "total_units", 0) or 0),
                "units_sold": int(getattr(snap, "sold_units", 0) or 0),
                "units_booked": int(getattr(snap, "booked_units", 0) or 0),
                "units_blocked": int(getattr(snap, "blocked_units", 0) or 0),
                "construction_percent": float(getattr(snap, "construction_percent", 0) or 0),
                "planned_percent": 0,  # ProjectKPI_Daily model doesn't have planned_percent field
                "revenue_booked": float(getattr(snap, "revenue_booked", 0) or 0),
                "revenue_collected": float(getattr(snap, "revenue_collected", 0) or 0),
                "outstanding": float(getattr(snap, "outstanding", 0) or 0),
            }
        })
