"""
Seed Marketing & ROI data for MICL as per static.
Run after seed_micl_executive and seed_micl_crm. Run: python manage.py seed_micl_marketing

KPIs: Total Spend YTD ₹1.96 Cr, Total Leads 4,880, Cost Per Lead ₹4,006.148, Cost Per Booking ₹58,885.542, Avg ROI 3.0x.
Campaigns: 10 campaigns with exact spend, leads, bookings, ROI, status.
Channel spend: Digital ₹73.50 L, Broker ₹45.00 L, Direct ₹77.00 L.
Location demand: Mumbai-Andheri, Pune-Baner, Bangalore-Whitefield, Hyderabad-Gachibowli, Chennai-OMR.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Organization, LeadChannel
from analytics.models import MarketingCampaign, LocationDemandMonthly


ORG_CODE = "MICL"

# (name, channel_code, spend_lakhs, leads, bookings, cost_per_lead, cost_per_booking, roi, status)
CAMPAIGNS = [
    ("Google Ads - Mumbai", "digital", 25.00, 850, 42, 2941.176, 59523.81, 3.2, "on_track"),
    ("Facebook Campaign Q1", "digital", 18.00, 620, 28, 2903.226, 64285.714, 2.8, "at_risk"),
    ("Broker Network Program", "broker", 45.00, 1200, 96, 3750.0, 46875.0, 4.1, "on_track"),
    ("Property Expo 2024", "direct", 32.00, 480, 35, 6666.667, 91428.571, 2.2, "at_risk"),
    ("LinkedIn B2B Campaign", "digital", 12.00, 180, 12, 6666.667, 100000.0, 1.9, "paused"),
    ("Referral Program", "direct", 8.00, 320, 48, 2500.0, 16666.667, 5.8, "on_track"),
    ("YouTube Video Ads", "digital", 15.00, 420, 22, 3571.429, 68181.818, 2.5, "at_risk"),
    ("Email Marketing", "digital", 3.50, 280, 18, 1250.0, 19444.444, 4.2, "on_track"),
    ("Print Media - TOI", "direct", 28.00, 380, 24, 7368.421, 116666.667, 1.6, "paused"),
    ("Radio Campaign", "direct", 9.00, 150, 8, 6000.0, 112500.0, 1.4, "paused"),
]

# (location, city, enquiries, bookings, demand_score)
LOCATIONS = [
    ("Mumbai - Andheri", "Mumbai", 450, 42, 9.3),
    ("Pune - Baner", "Pune", 380, 38, 8.8),
    ("Bangalore - Whitefield", "Bangalore", 520, 35, 7.5),
    ("Hyderabad - Gachibowli", "Hyderabad", 290, 28, 8.2),
    ("Chennai - OMR", "Chennai", 340, 25, 7.1),
]


class Command(BaseCommand):
    help = "Seed Marketing & ROI (campaigns, location demand) for MICL as per static."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Delete MICL marketing campaigns and location demand before seeding")

    @transaction.atomic
    def handle(self, *args, **options):
        org = Organization.objects.filter(code=ORG_CODE).first()
        if not org:
            self.stdout.write(self.style.ERROR(f"Organization {ORG_CODE} not found. Run seed_micl_executive first."))
            return

        if options.get("clear"):
            MarketingCampaign.objects.filter(organization=org).delete()
            LocationDemandMonthly.objects.filter(organization=org).delete()
            self.stdout.write("Cleared MICL marketing data.")

        # Get or create LeadChannels (should exist from CRM seed)
        channels = {}
        for code, label in [("digital", "Digital"), ("broker", "Broker"), ("direct", "Direct")]:
            ch, _ = LeadChannel.objects.get_or_create(
                organization=org,
                code=code,
                defaults={"label": label, "is_active": True},
            )
            channels[code] = ch

        today = date.today()
        year_start = date(today.year, 1, 1)
        year_end = date(today.year, 12, 31)

        # Seed campaigns
        for i, (name, ch_code, spend_l, leads, bookings, cpl, cpb, roi, status) in enumerate(CAMPAIGNS):
            ch = channels.get(ch_code)
            if not ch:
                self.stdout.write(self.style.WARNING(f"Channel {ch_code} not found; skipping {name}."))
                continue

            spend = Decimal(str(spend_l)) * Decimal("100000")
            cost_per_lead = Decimal(str(cpl))
            cost_per_booking = Decimal(str(cpb))
            roi_val = Decimal(str(roi))

            MarketingCampaign.objects.update_or_create(
                organization=org,
                campaign_code=f"MKT-{i+1:03d}",
                defaults={
                    "name": name,
                    "channel": ch,
                    "start_date": year_start + timedelta(days=i * 30),
                    "end_date": year_start + timedelta(days=(i + 1) * 30),
                    "spend": spend,
                    "leads": leads,
                    "bookings": bookings,
                    "cost_per_lead": cost_per_lead,
                    "cost_per_booking": cost_per_booking,
                    "roi": roi_val,
                    "status": status,
                },
            )
        self.stdout.write(f"MarketingCampaign: {len(CAMPAIGNS)} campaigns seeded.")

        # Seed location demand (current year, current month)
        y1, m1 = today.year, today.month
        for loc_name, city, enq, book, score in LOCATIONS:
            LocationDemandMonthly.objects.update_or_create(
                organization=org,
                location=loc_name,
                year=y1,
                month=m1,
                defaults={
                    "city": city,
                    "enquiries": enq,
                    "bookings": book,
                    "demand_score": Decimal(str(score)),
                },
            )
        self.stdout.write(f"LocationDemandMonthly: {len(LOCATIONS)} locations seeded for {y1}-{m1}.")

        # Calculate totals for verification
        total_spend = sum(Decimal(str(c[2])) * Decimal("100000") for c in CAMPAIGNS)
        total_leads = sum(c[3] for c in CAMPAIGNS)
        total_bookings = sum(c[4] for c in CAMPAIGNS)
        self.stdout.write(
            f"Totals: Spend {total_spend / Decimal('10000000'):.2f} Cr, Leads {total_leads}, Bookings {total_bookings}."
        )

        self.stdout.write(self.style.SUCCESS("Marketing & ROI seed done. Open Marketing & ROI (org MICL)."))
