from datetime import date
from dateutil.relativedelta import relativedelta
from django.db.models import Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.conf import settings

from analytics.models import OrgKPI_Daily, OrgMonthlySnapshot, ProjectKPI_Daily
from projects.models import Project
from core.models import Organization

from .views import get_org, normalize_status


def _quarter_label(year: int, month: int) -> str:
    """Return e.g. 'Q1 2024'."""
    q = (month - 1) // 3 + 1
    return f"Q{q} {year}"


class InvestorDashboardAPIView(APIView):
    """
    API endpoint for Investor Dashboard (Board & Investor View).
    Returns portfolio metrics, quarterly performance, realization timeline,
    project portfolio table, risk summary, and highlights.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            org = get_org(request)
            if not org:
                return Response({"detail": "No organization mapped to user."}, status=400)

            today = date.today()
            quarter = (today.month - 1) // 3 + 1
            quarter_label = _quarter_label(today.year, today.month)

            # Latest org-level KPI
            latest_org_kpi = (
                OrgKPI_Daily.objects.filter(organization=org).order_by("-date").first()
            )

            # Projects with latest ProjectKPI_Daily
            projects = Project.objects.filter(organization=org).order_by("name")
            latest_date = (
                ProjectKPI_Daily.objects.filter(project__organization=org)
                .order_by("-date")
                .values_list("date", flat=True)
                .first()
            )

            total_revenue_booked = 0.0
            total_revenue_collected = 0.0
            total_budget = 0.0
            total_cost_incurred = 0.0
            construction_sum = 0.0
            project_count = 0
            projects_data = []

            for project in projects:
                latest_kpi = None
                if latest_date:
                    latest_kpi = (
                        ProjectKPI_Daily.objects.filter(
                            project=project, date=latest_date
                        ).first()
                    )

                total_units = int(getattr(latest_kpi, "total_units", 0) or 0) if latest_kpi else 0
                units_sold = int(getattr(latest_kpi, "sold_units", 0) or 0) if latest_kpi else 0
                units_booked = int(getattr(latest_kpi, "booked_units", 0) or 0) if latest_kpi else 0
                construction_percent = float(getattr(latest_kpi, "construction_percent", 0) or 0) if latest_kpi else 0.0
                revenue_booked = float(getattr(latest_kpi, "revenue_booked", 0) or 0) if latest_kpi else 0.0
                revenue_collected = float(getattr(latest_kpi, "revenue_collected", 0) or 0) if latest_kpi else 0.0
                cost_incurred = float(getattr(latest_kpi, "cost_incurred", 0) or 0) if latest_kpi else 0.0
                margin_percent = float(getattr(latest_kpi, "margin_percent", 0) or 0) if latest_kpi else 0.0
                budget = float(getattr(latest_kpi, "budget", 0) or 0) if latest_kpi else float(project.budget or 0)

                total_revenue_booked += revenue_booked
                total_revenue_collected += revenue_collected
                total_budget += budget
                total_cost_incurred += cost_incurred
                construction_sum += construction_percent
                project_count += 1

                expected_completion = None
                if project.expected_completion_date:
                    expected_completion = project.expected_completion_date.strftime("%Y-%m-%d")
                elif project.planned_completion_date:
                    expected_completion = project.planned_completion_date.strftime("%Y-%m-%d")

                projects_data.append({
                    "project_id": project.id,
                    "name": project.name,
                    "location": project.location,
                    "status": normalize_status(project.status),
                    "total_units": total_units,
                    "units_sold": units_sold,
                    "units_booked": units_booked,
                    "construction_percent": construction_percent,
                    "revenue_booked": revenue_booked,
                    "revenue_collected": revenue_collected,
                    "cost_incurred": cost_incurred,
                    "margin_percent": margin_percent,
                    "expected_completion_date": expected_completion,
                })

            # Portfolio value = total revenue booked (or use org KPI if preferred)
            if latest_org_kpi:
                org_revenue_booked = float(getattr(latest_org_kpi, "revenue_booked", 0) or 0)
                org_revenue_collected = float(getattr(latest_org_kpi, "revenue_collected", 0) or 0)
            else:
                org_revenue_booked = total_revenue_booked
                org_revenue_collected = total_revenue_collected

            portfolio_value = org_revenue_booked if org_revenue_booked > 0 else total_revenue_booked
            total_investment = total_cost_incurred if total_cost_incurred > 0 else total_budget

            current_roi = 0.0
            if total_investment and total_investment > 0:
                current_roi = round(((portfolio_value - total_investment) / total_investment) * 100, 1)

            revenue_realization = 0.0
            rev_booked = org_revenue_booked or total_revenue_booked
            rev_collected = org_revenue_collected or total_revenue_collected
            if rev_booked and rev_booked > 0:
                revenue_realization = round((rev_collected / rev_booked) * 100, 1)

            completion_confidence = round(construction_sum / project_count, 1) if project_count else 0.0

            investor_metrics = {
                "portfolio_value": portfolio_value,
                "total_investment": total_investment,
                "current_roi": current_roi,
                "projected_irr": None,
                "revenue_realization": revenue_realization,
                "completion_confidence": completion_confidence,
            }

            # Quarterly performance from OrgMonthlySnapshot (last 4 quarters)
            quarterly_performance = []
            for i in range(4):
                d = today - relativedelta(months=3 * (3 - i))
                y, m = d.year, d.month
                q_start_month = ((m - 1) // 3) * 3 + 1
                snapshots = OrgMonthlySnapshot.objects.filter(
                    organization=org,
                    year=y,
                    month__in=[q_start_month, q_start_month + 1, q_start_month + 2],
                )
                agg = snapshots.aggregate(
                    revenue=Sum("revenue_booked"),
                    realization=Sum("revenue_collected"),
                )
                rev = float(agg["revenue"] or 0)
                real = float(agg["realization"] or 0)
                quarterly_performance.append({
                    "quarter": _quarter_label(y, q_start_month),
                    "revenue": rev,
                    "target": rev,
                    "realization": real,
                })

            # Realization timeline by year (past year, current, next 2; use snapshots where available)
            realization_timeline = []
            current_year = today.year
            for y in range(current_year - 1, current_year + 3):
                agg = OrgMonthlySnapshot.objects.filter(organization=org, year=y).aggregate(
                    projected=Sum("revenue_booked"),
                    realized=Sum("revenue_collected"),
                )
                projected = float(agg["projected"] or 0)
                realized = float(agg["realized"] or 0)
                if y == current_year and projected == 0 and rev_booked > 0:
                    projected = rev_booked
                    realized = rev_collected
                realization_timeline.append({
                    "year": str(y),
                    "projected": projected,
                    "realized": realized,
                })

            # Risk summary (derived from org KPI and project status)
            at_risk = int(getattr(latest_org_kpi, "at_risk_projects", 0) or 0) if latest_org_kpi else 0
            stalled = int(getattr(latest_org_kpi, "stalled_projects", 0) or 0) if latest_org_kpi else 0
            delayed_count = sum(1 for p in projects_data if p["status"] == "delayed")
            risk_summary = [
                {
                    "category": "Construction Delays",
                    "level": "Medium" if (at_risk + delayed_count) > 0 else "Low",
                    "projects": at_risk + delayed_count,
                    "impact": f"₹{int(total_cost_incurred / 10000000)} Cr cost incurred; monitor schedule" if at_risk else "On schedule",
                },
                {
                    "category": "Market Risk",
                    "level": "Low",
                    "projects": 0,
                    "impact": "Stable demand across locations",
                },
                {
                    "category": "Regulatory",
                    "level": "Medium" if stalled else "Low",
                    "projects": stalled,
                    "impact": "Clearances in place" if not stalled else "Review pending clearances",
                },
                {
                    "category": "Financial",
                    "level": "Low",
                    "projects": 0,
                    "impact": "Healthy cash position" if rev_collected > 0 else "Monitor collections",
                },
            ]

            # Highlights (derived)
            total_units_sold = sum(p["units_sold"] for p in projects_data)
            highlights = []
            if total_units_sold > 0:
                highlights.append({
                    "type": "positive",
                    "title": "Strong Sales Momentum",
                    "description": f"{total_units_sold} units sold across portfolio",
                })
            if rev_collected > 0:
                highlights.append({
                    "type": "positive",
                    "title": "Healthy Cash Position",
                    "description": f"Revenue collected: ₹{int(rev_collected / 10000000)} Cr",
                })
            if at_risk > 0 or delayed_count > 0:
                highlights.append({
                    "type": "warning",
                    "title": "Construction Attention Needed",
                    "description": f"{at_risk + delayed_count} project(s) at risk or delayed",
                })
            near_complete = [p for p in projects_data if p["construction_percent"] >= 85 and p["construction_percent"] < 100]
            if near_complete:
                p0 = near_complete[0]
                highlights.append({
                    "type": "info",
                    "title": f"{p0['name']} Near Completion",
                    "description": f"{p0['construction_percent']:.0f}% complete",
                })
            if not highlights:
                highlights.append({
                    "type": "info",
                    "title": "Portfolio Summary",
                    "description": f"{project_count} projects; ₹{int(portfolio_value / 10000000)} Cr portfolio value",
                })

            return Response({
                "organization_name": org.name,
                "quarter_label": quarter_label,
                "investor_metrics": investor_metrics,
                "quarterly_performance": quarterly_performance,
                "realization_timeline": realization_timeline,
                "projects": projects_data,
                "risk_summary": risk_summary,
                "highlights": highlights,
            })

        except Exception as e:
            import traceback
            return Response(
                {
                    "detail": f"Error processing request: {str(e)}",
                    "traceback": traceback.format_exc() if settings.DEBUG else None,
                },
                status=500,
            )
