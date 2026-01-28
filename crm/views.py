from datetime import date
from dateutil.relativedelta import relativedelta
from django.db.models import Sum, Count, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from crm.models import Customer, Booking, CustomerPayment
from core.models import Organization
from django.conf import settings


def get_org(request):
    """
    Hybrid approach to get organization:
    1. Try authenticated user's employee profile
    2. Try org_code query parameter (for development/testing)
    3. Fall back to first organization if DEBUG=True
    """
    # First, try authenticated user's employee profile
    emp = getattr(request.user, "employee_profile", None)
    if emp and emp.organization:
        return emp.organization
    
    # Second, try org_code query parameter (useful for development/testing)
    org_code = request.query_params.get("org_code")
    if org_code:
        org = Organization.objects.filter(code=org_code).first()
        if org:
            return org
    
    # Third, fallback to first organization if DEBUG mode (development only)
    if settings.DEBUG:
        org = Organization.objects.first()
        if org:
            return org
    
    return None


def normalize_customer_status(status):
    """Normalize customer status from backend format to frontend format."""
    status_map = {
        "walk_in": "Walk-in",
        "applied": "Applied",
        "booked": "Booked",
        "possession": "Possession",
        "cancelled": "Cancelled",
    }
    return status_map.get(status, status)


def calculate_trend(current_value, previous_value):
    """Calculate percentage trend between current and previous value."""
    if not previous_value or previous_value == 0:
        return None
    if current_value is None:
        current_value = 0
    return round(((current_value - previous_value) / previous_value) * 100, 1)


class CRMCustomersAPIView(APIView):
    """
    API endpoint for CRM Customers page.
    Returns:
    - KPIs (total customers, walk-ins MTD, conversions MTD, cancelled, possession)
    - Customer funnel data
    - Cancellation reasons with counts
    - Customer list with booking and payment details
    """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            org = get_org(request)
            if not org:
                return Response({"detail": "No organization mapped to user."}, status=400)
        except Exception as e:
            return Response({"detail": f"Error getting organization: {str(e)}"}, status=500)

        # Get query parameters for filtering
        search_term = request.query_params.get("search", "").strip()
        project_filter = request.query_params.get("project", "all")
        status_filter = request.query_params.get("status", "all")
        limit = int(request.query_params.get("limit", 50))
        offset = int(request.query_params.get("offset", 0))

        # Get current date and calculate MTD range
        today = date.today()
        current_month_start = today.replace(day=1)
        last_month_start = (current_month_start - relativedelta(months=1))
        last_month_end = current_month_start - relativedelta(days=1)

        # Base queryset for customers
        customers_qs = Customer.objects.filter(organization=org).select_related(
            "project", "unit", "unit__unit_type", "channel", "cancellation_reason"
        ).prefetch_related("bookings", "bookings__payments")

        # ----------------------------
        # 1) KPIs
        # ----------------------------
        total_customers = customers_qs.count()
        
        # Walk-ins MTD
        walk_ins_mtd = customers_qs.filter(
            status=Customer.Status.WALK_IN,
            walk_in_date__gte=current_month_start
        ).count()
        
        # Walk-ins Last Month
        walk_ins_lm = customers_qs.filter(
            status=Customer.Status.WALK_IN,
            walk_in_date__gte=last_month_start,
            walk_in_date__lte=last_month_end
        ).count()
        
        # Conversions (Booked) MTD
        conversions_mtd = customers_qs.filter(
            status=Customer.Status.BOOKED,
            booking_date__gte=current_month_start
        ).count()
        
        # Conversions Last Month
        conversions_lm = customers_qs.filter(
            status=Customer.Status.BOOKED,
            booking_date__gte=last_month_start,
            booking_date__lte=last_month_end
        ).count()
        
        # Cancelled
        cancelled = customers_qs.filter(status=Customer.Status.CANCELLED).count()
        
        # Cancelled Last Month (for trend)
        cancelled_lm = customers_qs.filter(
            status=Customer.Status.CANCELLED,
            cancellation_date__gte=last_month_start,
            cancellation_date__lte=last_month_end
        ).count()
        
        # Possession Given
        possession = customers_qs.filter(status=Customer.Status.POSSESSION).count()
        
        # Possession Last Month (for trend)
        possession_lm = customers_qs.filter(
            status=Customer.Status.POSSESSION,
            possession_date__gte=last_month_start,
            possession_date__lte=last_month_end
        ).count()

        # Calculate trends
        walk_ins_trend = calculate_trend(walk_ins_mtd, walk_ins_lm)
        conversions_trend = calculate_trend(conversions_mtd, conversions_lm)
        cancelled_trend = calculate_trend(cancelled, cancelled_lm)
        possession_trend = calculate_trend(possession, possession_lm)

        kpis = {
            "total_customers": total_customers,
            "walk_ins_mtd": walk_ins_mtd,
            "walk_ins_trend": walk_ins_trend,
            "conversions_mtd": conversions_mtd,
            "conversions_trend": conversions_trend,
            "cancelled": cancelled,
            "cancelled_trend": cancelled_trend,
            "possession": possession,
            "possession_trend": possession_trend,
        }

        # ----------------------------
        # 2) Customer Funnel
        # ----------------------------
        walk_ins_count = customers_qs.filter(status=Customer.Status.WALK_IN).count()
        applied_count = customers_qs.filter(status=Customer.Status.APPLIED).count()
        booked_count = customers_qs.filter(status=Customer.Status.BOOKED).count()
        possession_count = customers_qs.filter(status=Customer.Status.POSSESSION).count()
        cancelled_count = customers_qs.filter(status=Customer.Status.CANCELLED).count()

        funnel = {
            "walk_ins": walk_ins_count,
            "applied": applied_count,
            "booked": booked_count,
            "possession": possession_count,
            "cancelled": cancelled_count,
            "total": total_customers,
        }

        # ----------------------------
        # 3) Cancellation Reasons
        # ----------------------------
        try:
            cancellation_reasons = (
                customers_qs
                .filter(status=Customer.Status.CANCELLED)
                .exclude(cancellation_reason__isnull=True)
                .values("cancellation_reason__label")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            cancellation_reasons_data = [
                {"reason": item.get("cancellation_reason__label", "Unknown"), "count": item["count"]}
                for item in cancellation_reasons
                if item.get("cancellation_reason__label")
            ]
        except Exception as e:
            # If cancellation reasons query fails, return empty list
            cancellation_reasons_data = []

        # ----------------------------
        # 4) Customer List
        # ----------------------------
        # Apply filters
        filtered_customers_qs = customers_qs

        if search_term:
            filtered_customers_qs = filtered_customers_qs.filter(
                Q(name__icontains=search_term) |
                Q(customer_code__icontains=search_term) |
                Q(unit__unit_number__icontains=search_term)
            )

        if project_filter != "all":
            try:
                project_id = int(project_filter)
                filtered_customers_qs = filtered_customers_qs.filter(project_id=project_id)
            except (ValueError, TypeError):
                # Invalid project ID, ignore filter
                pass

        if status_filter != "all":
            # Map frontend status to backend status
            status_map = {
                "Walk-in": Customer.Status.WALK_IN,
                "Applied": Customer.Status.APPLIED,
                "Booked": Customer.Status.BOOKED,
                "Possession": Customer.Status.POSSESSION,
                "Cancelled": Customer.Status.CANCELLED,
            }
            backend_status = status_map.get(status_filter)
            if backend_status:
                filtered_customers_qs = filtered_customers_qs.filter(status=backend_status)

        # Get paginated customers
        customers_list = filtered_customers_qs[offset:offset + limit]

        customers_data = []
        for customer in customers_list:
            # Get latest active booking
            latest_booking = (
                Booking.objects
                .filter(customer=customer, status=Booking.Status.ACTIVE)
                .order_by("-booking_date")
                .first()
            )

            booking_value = 0.0
            amount_paid = 0.0
            outstanding_amount = 0.0

            if latest_booking:
                booking_value = float(latest_booking.booking_value or 0)
                # Calculate total payments for this booking
                total_payments = (
                    CustomerPayment.objects
                    .filter(booking=latest_booking)
                    .aggregate(total=Sum("amount"))
                )
                amount_paid = float(total_payments["total"] or 0)
                outstanding_amount = max(0, booking_value - amount_paid)

            # Get unit info (with safe access)
            unit_number = ""
            unit_type = ""
            if customer.unit:
                unit_number = customer.unit.unit_number or ""
                if customer.unit.unit_type:
                    unit_type = customer.unit.unit_type.label or ""

            # Get channel
            sales_channel = ""
            if customer.channel:
                sales_channel = customer.channel.label or ""

            customers_data.append({
                "id": customer.customer_code,
                "name": customer.name,
                "email": customer.email or "",
                "phone": customer.phone or "",
                "project_id": customer.project.id if customer.project else None,
                "project_name": customer.project.name if customer.project else "",
                "unit_number": unit_number,
                "unit_type": unit_type,
                "booking_status": normalize_customer_status(customer.status),
                "booking_value": booking_value,
                "amount_paid": amount_paid,
                "outstanding_amount": outstanding_amount,
                "sales_channel": sales_channel,
                "satisfaction_score": float(customer.satisfaction_score_cached or 0),
                "walk_in_date": customer.walk_in_date.strftime("%Y-%m-%d") if customer.walk_in_date else None,
            })

        try:
            return Response({
                "kpis": kpis,
                "funnel": funnel,
                "cancellation_reasons": cancellation_reasons_data,
                "customers": customers_data,
                "total_count": filtered_customers_qs.count(),
                "limit": limit,
                "offset": offset,
            })
        except Exception as e:
            import traceback
            return Response({
                "detail": f"Error processing request: {str(e)}",
                "traceback": traceback.format_exc() if settings.DEBUG else None
            }, status=500)
