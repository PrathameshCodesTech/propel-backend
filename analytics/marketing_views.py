from datetime import date
from django.db.models import Sum, Avg
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.conf import settings

from analytics.models import MarketingCampaign, LocationDemandMonthly
from .views import get_org, calculate_trend


def normalize_marketing_status(status):
    """Map backend status to frontend display (On Track, At Risk, Delayed)."""
    status_map = {
        "on_track": "On Track",
        "at_risk": "At Risk",
        "paused": "Delayed",
        "completed": "On Track",
    }
    return status_map.get(status, status or "On Track")


class MarketingROIAPIView(APIView):
    """
    API endpoint for Marketing & ROI page.
    Returns campaign KPIs, campaign list, channel spend, and location demand.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            org = get_org(request)
            if not org:
                return Response({"detail": "No organization mapped to user."}, status=400)

            today = date.today()
            year_start = date(today.year, 1, 1)

            campaigns_qs = (
                MarketingCampaign.objects.filter(organization=org)
                .select_related("channel")
                .order_by("-spend")
            )

            total_spend = 0.0
            total_leads = 0
            total_bookings = 0
            roi_sum = 0.0
            roi_count = 0
            campaigns_data = []

            for c in campaigns_qs:
                spend = float(c.spend or 0)
                leads = int(c.leads or 0)
                bookings = int(c.bookings or 0)
                cost_per_lead = float(c.cost_per_lead or 0)
                cost_per_booking = float(c.cost_per_booking or 0)
                roi = float(c.roi or 0)

                total_spend += spend
                total_leads += leads
                total_bookings += bookings
                if roi is not None and roi > 0:
                    roi_sum += roi
                    roi_count += 1

                channel_label = c.channel.label if c.channel else "Other"

                campaigns_data.append({
                    "campaign": c.name,
                    "campaign_code": c.campaign_code,
                    "channel": channel_label,
                    "spend": spend,
                    "leads": leads,
                    "bookings": bookings,
                    "cost_per_lead": cost_per_lead,
                    "cost_per_booking": cost_per_booking,
                    "roi": roi,
                    "status": normalize_marketing_status(c.status),
                    "start_date": c.start_date.strftime("%Y-%m-%d") if c.start_date else None,
                    "end_date": c.end_date.strftime("%Y-%m-%d") if c.end_date else None,
                })

            avg_cost_per_lead = total_spend / total_leads if total_leads else 0.0
            avg_cost_per_booking = total_spend / total_bookings if total_bookings else 0.0
            avg_roi = roi_sum / roi_count if roi_count else 0.0

            last_year_start = date(today.year - 1, 1, 1)
            last_year_end = date(today.year - 1, today.month, today.day)
            campaigns_ly = MarketingCampaign.objects.filter(
                organization=org,
                start_date__gte=last_year_start,
                start_date__lte=last_year_end,
            )
            spend_ly = sum(float(c.spend or 0) for c in campaigns_ly)
            leads_ly = sum(int(c.leads or 0) for c in campaigns_ly)

            spend_trend = calculate_trend(total_spend, spend_ly) if spend_ly else None
            leads_trend = calculate_trend(total_leads, leads_ly) if leads_ly else None

            kpis = {
                "total_spend_ytd": total_spend,
                "total_leads": total_leads,
                "total_bookings": total_bookings,
                "cost_per_lead": round(avg_cost_per_lead, 2),
                "cost_per_booking": round(avg_cost_per_booking, 2),
                "avg_roi": round(avg_roi, 1),
                "spend_trend": spend_trend,
                "leads_trend": leads_trend,
            }

            channel_spend_raw = {}
            for c in campaigns_data:
                ch = c["channel"]
                channel_spend_raw[ch] = channel_spend_raw.get(ch, 0) + c["spend"]
            channel_spend = [{"channel": ch, "spend": s} for ch, s in channel_spend_raw.items()]
            channel_spend.sort(key=lambda x: -x["spend"])

            location_agg = (
                LocationDemandMonthly.objects.filter(
                    organization=org,
                    year=today.year,
                )
                .values("location")
                .annotate(
                    enquiries=Sum("enquiries"),
                    bookings=Sum("bookings"),
                )
            )
            location_demand = []
            for row in location_agg:
                loc = row["location"]
                enq = row["enquiries"] or 0
                book = row["bookings"] or 0
                score_row = LocationDemandMonthly.objects.filter(
                    organization=org,
                    location=loc,
                    year=today.year,
                ).aggregate(avg_score=Avg("demand_score"))
                score = float(score_row.get("avg_score") or 0)
                location_demand.append({
                    "location": loc,
                    "enquiries": enq,
                    "bookings": book,
                    "demand_score": round(score, 1),
                })
            location_demand.sort(key=lambda x: -x["enquiries"])

            return Response({
                "kpis": kpis,
                "campaigns": campaigns_data,
                "channel_spend": channel_spend,
                "location_demand": location_demand,
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
