from datetime import date
from dateutil.relativedelta import relativedelta
from django.db.models import Sum, Count
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.conf import settings

from crm.models import Booking, Customer
from projects.models import Project
from core.models import Organization, Employee
from people.models import EmployeeKRA, KRA
from analytics.models import ProjectKPI_Daily

# Import helper functions from views.py
from .views import get_org, calculate_trend


class SalesPerformanceAPIView(APIView):
    """
    API endpoint for Sales Performance page.
    Returns sales KPIs, monthly trends, channel distribution, 
    sales team performance, and project-wise sales.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            org = get_org(request)
            if not org:
                return Response({"detail": "No organization mapped to user."}, status=400)

            today = date.today()
            year_start = date(today.year, 1, 1)

            # Get all active bookings YTD
            bookings_ytd = Booking.objects.filter(
                customer__organization=org,
                booking_date__gte=year_start,
                status=Booking.Status.ACTIVE
            ).select_related("sales_executive", "project", "customer")

            # Get all customers for conversion rate calculation
            all_customers = Customer.objects.filter(organization=org)
            walk_in_customers = all_customers.filter(status=Customer.Status.WALK_IN)
            booked_customers = all_customers.filter(status=Customer.Status.BOOKED)

            # 1. KPIs
            total_bookings_ytd = bookings_ytd.count()
            revenue_ytd = float(bookings_ytd.aggregate(total=Sum("booking_value"))["total"] or 0)
            avg_ticket_size = float(revenue_ytd / total_bookings_ytd) if total_bookings_ytd > 0 else 0.0
            
            # Conversion rate: booked customers / walk-in customers
            conversion_rate = 0.0
            if walk_in_customers.count() > 0:
                conversion_rate = round((booked_customers.count() / walk_in_customers.count()) * 100, 1)

            # Top performer
            top_performer_data = (
                bookings_ytd.values("sales_executive__user__first_name", "sales_executive__user__last_name")
                .annotate(count=Count("id"), revenue=Sum("booking_value"))
                .order_by("-revenue")
                .first()
            )
            
            top_performer = None
            if top_performer_data:
                name = f"{top_performer_data.get('sales_executive__user__first_name', '')} {top_performer_data.get('sales_executive__user__last_name', '')}".strip()
                top_performer = {
                    "name": name or "Unknown",
                    "bookings": top_performer_data.get("count", 0),
                    "revenue": float(top_performer_data.get("revenue", 0) or 0)
                }

            # Last year same period for trend calculation
            last_year_start = date(today.year - 1, 1, 1)
            last_year_end = date(today.year - 1, today.month, today.day)
            
            bookings_last_year = Booking.objects.filter(
                customer__organization=org,
                booking_date__gte=last_year_start,
                booking_date__lte=last_year_end,
                status=Booking.Status.ACTIVE
            )
            
            total_bookings_last_year = bookings_last_year.count()
            revenue_last_year = float(bookings_last_year.aggregate(total=Sum("booking_value"))["total"] or 0)
            
            bookings_trend = calculate_trend(total_bookings_ytd, total_bookings_last_year)
            revenue_trend = calculate_trend(revenue_ytd, revenue_last_year)

            kpis = {
                "total_bookings_ytd": total_bookings_ytd,
                "revenue_ytd": revenue_ytd,
                "avg_ticket_size": round(avg_ticket_size, 2),
                "conversion_rate": conversion_rate,
                "top_performer": top_performer,
                "bookings_trend": bookings_trend,
                "revenue_trend": revenue_trend,
            }

            # 2. Monthly trend data (last 12 months)
            monthly_trend = []
            for i in range(11, -1, -1):
                month_date = today - relativedelta(months=i)
                month_start = date(month_date.year, month_date.month, 1)
                if month_date.month == 12:
                    month_end = date(month_date.year, month_date.month, 31)
                else:
                    month_end = date(month_date.year, month_date.month + 1, 1) - relativedelta(days=1)

                month_bookings = bookings_ytd.filter(
                    booking_date__gte=month_start,
                    booking_date__lte=month_end
                )
                
                month_revenue = float(month_bookings.aggregate(total=Sum("booking_value"))["total"] or 0)
                
                monthly_trend.append({
                    "month": month_date.strftime("%Y-%m"),
                    "bookings": month_bookings.count(),
                    "revenue": month_revenue,
                })

            # 3. Channel distribution
            channel_data = (
                Customer.objects.filter(organization=org)
                .values("channel__label")
                .annotate(count=Count("id"))
                .order_by("-count")
            )
            
            channel_distribution = []
            for item in channel_data:
                channel_label = item.get("channel__label") or "Unknown"
                channel_distribution.append({
                    "channel": channel_label,
                    "count": item.get("count", 0),
                })

            # 4. Sales team performance (from EmployeeKRA)
            current_year = today.year
            current_month = today.month
            
            # Get sales executives
            sales_executives = Employee.objects.filter(
                organization=org,
                role__in=[
                    Employee.Role.SALES_EXECUTIVE,
                    Employee.Role.SALES_MANAGER,
                    Employee.Role.REGIONAL_HEAD,
                ],
                is_active=True
            ).select_related("user")
            
            # Get sales KRA if exists
            sales_kra = KRA.objects.filter(
                organization=org,
                name__icontains="sales"
            ).first()
            
            sales_team_performance = []
            for emp in sales_executives:
                # Get current month KRA
                current_kra = EmployeeKRA.objects.filter(
                    organization=org,
                    employee=emp,
                    year=current_year,
                    month=current_month
                ).first()
                
                # Get bookings for this employee YTD
                emp_bookings = bookings_ytd.filter(sales_executive=emp)
                bookings_count = emp_bookings.count()
                bookings_revenue = float(emp_bookings.aggregate(total=Sum("booking_value"))["total"] or 0)
                
                target = float(current_kra.target) if current_kra else 0.0
                achieved = float(current_kra.achieved) if current_kra else bookings_revenue
                achievement_percentage = float(current_kra.achievement_percentage) if current_kra else (
                    round((achieved / target * 100), 1) if target > 0 else 0.0
                )
                
                sales_team_performance.append({
                    "employee_id": emp.id,
                    "name": f"{emp.user.first_name} {emp.user.last_name}".strip() or "Unknown",
                    "role": emp.role,
                    "target": target,
                    "achieved": achieved,
                    "achievement_percentage": achievement_percentage,
                    "bookings": bookings_count,
                    "revenue": bookings_revenue,
                })
            
            # Sort by achievement percentage descending
            sales_team_performance.sort(key=lambda x: x["achievement_percentage"], reverse=True)

            # 5. Project-wise sales (from ProjectKPI_Daily latest snapshots)
            projects = Project.objects.filter(organization=org).order_by("name")
            
            # Get latest date for ProjectKPI_Daily
            latest_date = (
                ProjectKPI_Daily.objects
                .filter(project__organization=org)
                .order_by("-date")
                .values_list("date", flat=True)
                .first()
            )
            
            project_wise_sales = []
            for project in projects:
                # Get latest KPI
                latest_kpi = None
                if latest_date:
                    latest_kpi = (
                        ProjectKPI_Daily.objects
                        .filter(project=project, date=latest_date)
                        .first()
                    )
                
                # Get bookings for this project YTD
                project_bookings = bookings_ytd.filter(project=project)
                project_revenue = float(project_bookings.aggregate(total=Sum("booking_value"))["total"] or 0)
                
                units_sold = int(getattr(latest_kpi, "sold_units", 0) or 0) if latest_kpi else 0
                units_booked = int(getattr(latest_kpi, "booked_units", 0) or 0) if latest_kpi else 0
                
                project_wise_sales.append({
                    "project_id": project.id,
                    "name": project.name,
                    "units_sold": units_sold,
                    "units_booked": units_booked,
                    "bookings": project_bookings.count(),
                    "revenue": project_revenue,
                })

            return Response({
                "kpis": kpis,
                "monthly_trend": monthly_trend,
                "channel_distribution": channel_distribution,
                "sales_team_performance": sales_team_performance,
                "project_wise_sales": project_wise_sales,
            })

        except Exception as e:
            import traceback
            return Response({
                "detail": f"Error processing request: {str(e)}",
                "traceback": traceback.format_exc() if settings.DEBUG else None
            }, status=500)
