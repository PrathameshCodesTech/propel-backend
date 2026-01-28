"""
API views for multi-tenant: current user (me), CSRF token for session auth, and admin Excel upload.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
import re

from django.middleware.csrf import get_token
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser

from core.models import Organization, LeadChannel
from analytics.models import MarketingCampaign, LocationDemandMonthly, OrgKPI_Daily


class CsrfAPIView(APIView):
    """GET /api/csrf/ - Return CSRF token for session-authenticated POST (e.g. upload)."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrf": get_token(request)})


class MeAPIView(APIView):
    """
    GET /api/me/
    Returns current user and org for multi-tenant frontend.
    When authenticated with employee_profile, org_code is the user's org.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        org_code = None
        is_staff = getattr(user, "is_staff", False)
        emp = getattr(user, "employee_profile", None)
        if emp and emp.organization:
            org_code = emp.organization.code
        return Response({
            "username": getattr(user, "username", None),
            "org_code": org_code,
            "is_staff": is_staff,
        })


def _parse_excel_upload(file, org):
    """
    Parse Excel file and create/update org-scoped data.
    Expected sheets: Organization (code, name), MarketingCampaign, LocationDemandMonthly, OrgKPI_Daily (optional).
    Returns (created_counts, errors).
    """
    try:
        import openpyxl
    except ImportError:
        return {}, ["openpyxl is required. Install: pip install openpyxl"]
    from openpyxl import load_workbook

    created = {"organizations": 0, "marketing_campaigns": 0, "location_demand": 0, "org_kpi": 0}
    errors = []
    wb = load_workbook(file, read_only=True, data_only=True)

    def safe_decimal(value, field_name: str, row_preview) -> Decimal:
        """
        Convert Excel cell value to Decimal safely.
        - Strips currency symbols, commas and other non-numeric characters.
        - Returns Decimal(0) on failure and records a soft warning.
        """
        if value is None or value == "":
            return Decimal(0)
        s = str(value)
        # keep digits, dot and minus
        s = re.sub(r"[^\d\.\-]", "", s)
        if not s:
            return Decimal(0)
        try:
            return Decimal(s)
        except InvalidOperation:
            errors.append(f"Invalid decimal for {field_name} in row {row_preview}: {value!r}")
            return Decimal(0)

    # Sheet "Organization": optional; if present, ensure org exists (code must match request org_code if given)
    if "Organization" in wb.sheetnames:
        ws = wb["Organization"]
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        for row in rows:
            if not row or row[0] is None:
                continue
            code = str(row[0]).strip() if row[0] else None
            name = str(row[1]).strip() if len(row) > 1 and row[1] else (code or "")
            if not code:
                continue
            if org and code != org.code:
                errors.append(f"Organization sheet code '{code}' does not match upload org_code '{org.code}'.")
                break
            if not org:
                org, _ = Organization.objects.get_or_create(code=code, defaults={"name": name or code})
                created["organizations"] += 1
            break
    if not org:
        errors.append("Provide org_code in request or Organization sheet with code, name.")
        return created, errors

    # Ensure at least one LeadChannel for marketing
    channel = LeadChannel.objects.filter(organization=org).first()
    if not channel:
        channel, _ = LeadChannel.objects.get_or_create(
            organization=org, code="DIGITAL", defaults={"label": "Digital", "is_active": True}
        )

    # Sheet "MarketingCampaign"
    if "MarketingCampaign" in wb.sheetnames:
        ws = wb["MarketingCampaign"]
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        for row in rows:
            if not row or row[0] is None:
                continue
            try:
                name = str(row[0]).strip()
                campaign_code = str(row[1]).strip() if len(row) > 1 and row[1] else f"{org.code}-M-{row[0]}"
                # Expected columns:
                # 0: name
                # 1: campaign_code
                # 2: channel_code (optional, currently ignored / mapped to default channel)
                # 3: start_date
                # 4: end_date
                # 5: spend
                # 6: leads
                # 7: bookings
                # 8: cost_per_lead
                # 9: cost_per_booking
                # 10: roi
                # 11: status
                start_date = row[3] if len(row) > 3 else date.today()
                end_date = row[4] if len(row) > 4 else date.today()
                if hasattr(start_date, "date"):
                    start_date = start_date.date()
                if hasattr(end_date, "date"):
                    end_date = end_date.date()
                spend = safe_decimal(row[5] if len(row) > 5 else None, "spend", row[:2])
                leads = int(row[6]) if len(row) > 6 and row[6] is not None else 0
                bookings = int(row[7]) if len(row) > 7 and row[7] is not None else 0
                cost_per_lead = safe_decimal(row[8] if len(row) > 8 else None, "cost_per_lead", row[:2])
                cost_per_booking = safe_decimal(row[9] if len(row) > 9 else None, "cost_per_booking", row[:2])
                roi = safe_decimal(row[10] if len(row) > 10 else None, "roi", row[:2])
                status = "on_track"
                if len(row) > 11 and row[11]:
                    s = str(row[11]).strip().lower()
                    if s in ("on_track", "at_risk", "paused", "completed"):
                        status = s
                MarketingCampaign.objects.update_or_create(
                    organization=org, campaign_code=campaign_code,
                    defaults={
                        "name": name, "channel": channel,
                        "start_date": start_date, "end_date": end_date,
                        "spend": spend, "leads": leads, "bookings": bookings,
                        "cost_per_lead": cost_per_lead, "cost_per_booking": cost_per_booking,
                        "roi": roi, "status": status,
                    }
                )
                created["marketing_campaigns"] += 1
            except Exception as e:
                errors.append(f"MarketingCampaign row {row[:2]}: {e}")

    # Sheet "LocationDemandMonthly"
    if "LocationDemandMonthly" in wb.sheetnames:
        ws = wb["LocationDemandMonthly"]
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        today = date.today()
        for row in rows:
            if not row or row[0] is None:
                continue
            try:
                location = str(row[0]).strip()
                city = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                year = int(row[2]) if len(row) > 2 and row[2] is not None else today.year
                month = int(row[3]) if len(row) > 3 and row[3] is not None else today.month
                enquiries = int(row[4]) if len(row) > 4 and row[4] is not None else 0
                bookings = int(row[5]) if len(row) > 5 and row[5] is not None else 0
                demand_score = Decimal(str(row[6])) if len(row) > 6 and row[6] is not None else Decimal(0)
                LocationDemandMonthly.objects.update_or_create(
                    organization=org, location=location, year=year, month=month,
                    defaults={"city": city, "enquiries": enquiries, "bookings": bookings, "demand_score": demand_score}
                )
                created["location_demand"] += 1
            except Exception as e:
                errors.append(f"LocationDemandMonthly row {row[:2]}: {e}")

    # Sheet "OrgKPI_Daily" (optional): date, total_units, revenue_booked, revenue_collected, outstanding, etc.
    if "OrgKPI_Daily" in wb.sheetnames:
        ws = wb["OrgKPI_Daily"]
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        for row in rows:
            if not row or row[0] is None:
                continue
            try:
                d = row[0]
                if hasattr(d, "date"):
                    d = d.date()
                total_units = int(row[1]) if len(row) > 1 and row[1] is not None else 0
                revenue_booked = Decimal(str(row[2])) if len(row) > 2 and row[2] is not None else Decimal(0)
                revenue_collected = Decimal(str(row[3])) if len(row) > 3 and row[3] is not None else Decimal(0)
                outstanding = Decimal(str(row[4])) if len(row) > 4 and row[4] is not None else Decimal(0)
                OrgKPI_Daily.objects.update_or_create(
                    organization=org, date=d,
                    defaults={
                        "total_units": total_units, "revenue_booked": revenue_booked,
                        "revenue_collected": revenue_collected, "outstanding": outstanding,
                    }
                )
                created["org_kpi"] += 1
            except Exception as e:
                errors.append(f"OrgKPI_Daily row {row[:2]}: {e}")

    wb.close()
    return created, errors


class ExcelUploadAPIView(APIView):
    """
    POST /api/admin/upload-excel/
    Admin-only. Expects multipart: file (Excel), org_code (optional if Organization sheet has code).
    Creates/updates Organization, MarketingCampaign, LocationDemandMonthly, OrgKPI_Daily for that org.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file = request.FILES.get("file") or request.data.get("file")
        if not file:
            return Response({"error": "No file provided. Use form field 'file'."}, status=400)
        if not file.name.endswith((".xlsx", ".xls")):
            return Response({"error": "File must be .xlsx or .xls"}, status=400)

        org_code = (request.data.get("org_code") or request.POST.get("org_code") or "").strip()
        org = Organization.objects.filter(code=org_code).first() if org_code else None

        created, errors = _parse_excel_upload(file, org)
        if errors and not created.get("organizations") and not org:
            return Response({"error": "Could not determine organization.", "details": errors}, status=400)
        return Response({
            "message": "Upload processed.",
            "created": created,
            "errors": errors[:20],
        }, status=200)
