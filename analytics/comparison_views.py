from datetime import date
from dateutil.relativedelta import relativedelta

from django.db.models import Sum, Q, Min
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from analytics.models import ProjectKPI_Daily
from projects.models import Project
from core.models import Organization
from django.conf import settings

# Import helper functions from views.py
from .views import get_org, normalize_status


class ProjectComparisonAPIView(APIView):
    """
    API endpoint for Project Comparison page.
    Returns all projects with their comparison metrics including:
    - Units (sold, booked, blocked, available)
    - Construction progress
    - Budget and cost incurred
    - Satisfaction score
    - Revenue metrics
    - Sales velocity (calculated from historical data)
    """
    permission_classes = [AllowAny]

    def get(self, request):
        org = get_org(request)
        if not org:
            return Response({"detail": "No organization mapped to user."}, status=400)

        # Get all projects for the organization
        projects = Project.objects.filter(organization=org).order_by("name")
        
        # Get the latest date for ProjectKPI_Daily across all projects
        latest_date = (
            ProjectKPI_Daily.objects
            .filter(project__organization=org)
            .order_by("-date")
            .values_list("date", flat=True)
            .first()
        )

        projects_data = []
        today = date.today()

        for project in projects:
            # Get latest KPI snapshot for this project
            latest_kpi = None
            if latest_date:
                latest_kpi = (
                    ProjectKPI_Daily.objects
                    .filter(project=project, date=latest_date)
                    .first()
                )

            # Extract KPI values
            total_units = int(getattr(latest_kpi, "total_units", 0) or 0) if latest_kpi else 0
            units_sold = int(getattr(latest_kpi, "sold_units", 0) or 0) if latest_kpi else 0
            units_booked = int(getattr(latest_kpi, "booked_units", 0) or 0) if latest_kpi else 0
            units_blocked = int(getattr(latest_kpi, "blocked_units", 0) or 0) if latest_kpi else 0
            units_available = total_units - units_sold - units_booked - units_blocked
            
            construction_percent = float(getattr(latest_kpi, "construction_percent", 0) or 0) if latest_kpi else 0.0
            planned_percent = float(getattr(latest_kpi, "planned_percent", 0) or 0) if latest_kpi else 0.0
            
            budget = float(getattr(latest_kpi, "budget", 0) or 0) if latest_kpi else float(project.budget or 0)
            cost_incurred = float(getattr(latest_kpi, "cost_incurred", 0) or 0) if latest_kpi else 0.0
            
            satisfaction_score = float(getattr(latest_kpi, "satisfaction_avg", 0) or 0) if latest_kpi else 0.0
            
            revenue_booked = float(getattr(latest_kpi, "revenue_booked", 0) or 0) if latest_kpi else 0.0
            revenue_collected = float(getattr(latest_kpi, "revenue_collected", 0) or 0) if latest_kpi else 0.0

            # Calculate sales velocity (units per month)
            # Get the first KPI date for this project to calculate months active
            first_kpi_date = (
                ProjectKPI_Daily.objects
                .filter(project=project)
                .aggregate(first_date=Min("date"))
                .get("first_date")
            )
            
            sales_velocity = 0.0
            velocity_trend = "stable"
            
            if first_kpi_date and units_sold > 0:
                # Calculate months between first KPI date and today
                months_active = max(1, (today.year - first_kpi_date.year) * 12 + (today.month - first_kpi_date.month))
                if months_active > 0:
                    sales_velocity = units_sold / months_active
                    
                    # Calculate trend: compare last 3 months vs previous 3 months
                    three_months_ago = today - relativedelta(months=3)
                    six_months_ago = today - relativedelta(months=6)
                    
                    # Get sold units 3 months ago
                    kpi_3m_ago = (
                        ProjectKPI_Daily.objects
                        .filter(project=project, date__lte=three_months_ago)
                        .order_by("-date")
                        .first()
                    )
                    
                    # Get sold units 6 months ago
                    kpi_6m_ago = (
                        ProjectKPI_Daily.objects
                        .filter(project=project, date__lte=six_months_ago)
                        .order_by("-date")
                        .first()
                    )
                    
                    if kpi_3m_ago and kpi_6m_ago:
                        sold_3m = int(getattr(kpi_3m_ago, "sold_units", 0) or 0)
                        sold_6m = int(getattr(kpi_6m_ago, "sold_units", 0) or 0)
                        
                        if sold_6m > 0:
                            recent_velocity = (units_sold - sold_3m) / 3.0 if (units_sold - sold_3m) > 0 else 0
                            previous_velocity = (sold_3m - sold_6m) / 3.0 if (sold_3m - sold_6m) > 0 else 0
                            
                            if previous_velocity > 0:
                                if recent_velocity > previous_velocity * 1.1:  # 10% increase
                                    velocity_trend = "up"
                                elif recent_velocity < previous_velocity * 0.9:  # 10% decrease
                                    velocity_trend = "down"
                                else:
                                    velocity_trend = "stable"
            else:
                # Fallback: use project start date if available
                if project.planned_start_date:
                    months_active = max(1, (today.year - project.planned_start_date.year) * 12 + 
                                       (today.month - project.planned_start_date.month))
                    if months_active > 0:
                        sales_velocity = units_sold / months_active

            # Format expected completion date
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
                "units_blocked": units_blocked,
                "units_available": max(0, units_available),
                "construction_percent": construction_percent,
                "planned_percent": planned_percent,
                "budget": budget,
                "cost_incurred": cost_incurred,
                "satisfaction_score": satisfaction_score,
                "revenue_booked": revenue_booked,
                "revenue_collected": revenue_collected,
                "expected_completion_date": expected_completion,
                "sales_velocity": round(sales_velocity, 1),
                "velocity_trend": velocity_trend,
            })

        return Response({
            "projects": projects_data
        })
