"""
Seed MICL Executive Overview data exactly as per the dashboard image.
Organization MICL, 5 projects, ProjectKPI_Daily, OrgMonthlySnapshot, OrgKPI_Daily.
Run: python manage.py seed_micl_executive
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from core.models import Organization
from projects.models import Project
from analytics.models import ProjectKPI_Daily, OrgMonthlySnapshot, OrgKPI_Daily


ORG_CODE = "MICL"
ORG_NAME = "MICL Realty"
KPI_DATE = date(2025, 1, 27)

PROJECTS = [
    {"code": "SKY001", "name": "Skyline Heights", "location": "Mumbai", "city": "Mumbai", "status": "at_risk"},
    {"code": "GRV001", "name": "Green Valley Residency", "location": "Pune", "city": "Pune", "status": "on_track"},
    {"code": "URB001", "name": "Urban Oasis", "location": "Bangalore", "city": "Bangalore", "status": "delayed"},
    {"code": "SUN001", "name": "Sunrise Towers", "location": "Hyderabad", "city": "Hyderabad", "status": "on_track"},
    {"code": "COA001", "name": "Coastal Paradise", "location": "Chennai", "city": "Chennai", "status": "at_risk"},
]

# project_code -> (total, sold, booked, blocked, unsold, rev_booked, rev_collected, outstanding, construction%, satisfaction, budget, cost_incurred, margin%)
PROJECT_KPI = {
    "SKY001": (248, 189, 32, 8, 19, 425_000_000, 312_000_000, 113_000_000, 78, 4.2, 1_200_000_000, 218_000_000, 48.7),
    "GRV001": (220, 198, 14, 4, 4, 352_000_000, 298_000_000, 54_000_000, 92, 4.5, 800_000_000, 178_000_000, 49.4),
    "URB001": (235, 156, 42, 10, 27, 512_000_000, 285_000_000, 227_000_000, 45, 4.0, 1_500_000_000, 144_000_000, 71.9),
    "SUN001": (212, 178, 20, 6, 8, 298_000_000, 215_000_000, 83_000_000, 84, 4.4, 600_000_000, 114_000_000, 61.7),
    "COA001": (205, 142, 44, 10, 9, 385_000_000, 178_000_000, 207_000_000, 55, 4.1, 500_000_000, 86_000_000, 77.7),
}

# (year, month, total_units, revenue_booked, revenue_collected, outstanding, cash_inflow, cash_outflow, net_cashflow, avg_satisfaction, bookings_count, avg_ticket_size)
# First 6 months: keep revenue/etc; cash kept for chart shape.
# Last 6 months (Aug 2024-Jan 2025): cash set to match static 6M totals (91.60 Cr inflow, 69.30 Cr outflow, 22.30 Cr net, 3.72 Cr avg); Jan net = 4.70 Cr.
MONTHLY_SNAPSHOTS = [
    (2024, 2, 950, 1_420_000_000, 980_000_000, 440_000_000, 1_150_000_000, 980_000_000, 170_000_000, 4.1, 42, 2_333_333),
    (2024, 3, 980, 1_520_000_000, 1_050_000_000, 470_000_000, 1_380_000_000, 1_020_000_000, 360_000_000, 4.2, 48, 2_187_500),
    (2024, 4, 1010, 1_620_000_000, 1_120_000_000, 500_000_000, 1_480_000_000, 1_120_000_000, 360_000_000, 4.2, 52, 2_153_846),
    (2024, 5, 1040, 1_680_000_000, 1_160_000_000, 520_000_000, 1_550_000_000, 1_180_000_000, 370_000_000, 4.25, 55, 2_109_091),
    (2024, 6, 1070, 1_750_000_000, 1_200_000_000, 550_000_000, 1_620_000_000, 1_220_000_000, 400_000_000, 4.3, 58, 2_068_966),
    (2024, 7, 1090, 1_820_000_000, 1_240_000_000, 580_000_000, 1_680_000_000, 1_280_000_000, 400_000_000, 4.3, 62, 2_000_000),
    (2024, 8, 1100, 1_880_000_000, 1_260_000_000, 620_000_000, 152_800_000, 117_600_000, 35_200_000, 4.35, 65, 1_938_462),
    (2024, 9, 1110, 1_920_000_000, 1_275_000_000, 645_000_000, 152_800_000, 117_600_000, 35_200_000, 4.35, 68, 1_875_000),
    (2024, 10, 1115, 1_950_000_000, 1_285_000_000, 665_000_000, 152_800_000, 117_600_000, 35_200_000, 4.35, 70, 1_857_143),
    (2024, 11, 1120, 1_965_000_000, 1_288_000_000, 677_000_000, 152_800_000, 117_600_000, 35_200_000, 4.35, 72, 1_805_556),
    (2024, 12, 1120, 1_972_000_000, 1_288_000_000, 684_000_000, 152_800_000, 117_600_000, 35_200_000, 4.3, 74, 1_740_541),
    (2025, 1, 1120, 1_972_000_000, 1_288_000_000, 684_000_000, 152_000_000, 105_000_000, 47_000_000, 4.3, 75, 1_710_667),
]


class Command(BaseCommand):
    help = "Seed MICL Executive Overview (org, projects, ProjectKPI_Daily, OrgMonthlySnapshot, OrgKPI_Daily) as per dashboard image."

    def handle(self, *args, **options):
        org, _ = Organization.objects.update_or_create(
            code=ORG_CODE,
            defaults={"name": ORG_NAME},
        )
        self.stdout.write(f"Organization: {org.code} ({org.name})")

        projects = {}
        for p in PROJECTS:
            proj, _ = Project.objects.update_or_create(
                organization=org,
                project_code=p["code"],
                defaults={
                    "name": p["name"],
                    "location": p["location"],
                    "city": p["city"],
                    "status": p["status"],
                },
            )
            projects[p["code"]] = proj
            self.stdout.write(f"  Project: {proj.project_code} {proj.name} ({proj.status})")

        for code, row in PROJECT_KPI.items():
            t, s, b, bl, u, rb, rc, out, const, sat, budget, cost, margin = row
            ProjectKPI_Daily.objects.update_or_create(
                project=projects[code],
                date=KPI_DATE,
                defaults={
                    "total_units": t,
                    "sold_units": s,
                    "booked_units": b,
                    "blocked_units": bl,
                    "unsold_units": u,
                    "revenue_booked": Decimal(rb),
                    "revenue_collected": Decimal(rc),
                    "outstanding": Decimal(out),
                    "construction_percent": Decimal(str(const)),
                    "satisfaction_avg": Decimal(str(sat)),
                    "budget": Decimal(budget),
                    "cost_incurred": Decimal(cost),
                    "margin_percent": Decimal(str(margin)),
                },
            )
        self.stdout.write(f"ProjectKPI_Daily: 5 rows for date {KPI_DATE}")

        for y, m, tu, rb, rc, out, cin, cout, net, sat, bc, ats in MONTHLY_SNAPSHOTS:
            OrgMonthlySnapshot.objects.update_or_create(
                organization=org,
                year=y,
                month=m,
                defaults={
                    "total_units": tu,
                    "revenue_booked": Decimal(rb),
                    "revenue_collected": Decimal(rc),
                    "outstanding": Decimal(out),
                    "cash_inflow": Decimal(cin),
                    "cash_outflow": Decimal(cout),
                    "net_cashflow": Decimal(net),
                    "avg_satisfaction": Decimal(str(sat)),
                    "bookings_count": bc,
                    "avg_ticket_size": Decimal(ats),
                },
            )
        self.stdout.write("OrgMonthlySnapshot: 12 months (Feb 2024 - Jan 2025)")

        # Org-level KPI so Executive Overview KPI cards show (Total Units, Revenue Booked, etc.)
        total_units = 1120
        revenue_booked = Decimal("1972000000")
        revenue_collected = Decimal("1288000000")
        outstanding = Decimal("684000000")
        avg_construction = Decimal("63.0")  # static: 63.0%
        satisfaction_avg = Decimal("4.3")
        net_cashflow_mtd = Decimal("47000000")  # static: 4.70 Cr
        at_risk_projects = 2
        stalled_projects = 0
        ring_alerts = 0
        active_complaints = 0
        compliance_alerts = 0

        OrgKPI_Daily.objects.update_or_create(
            organization=org,
            date=KPI_DATE,
            defaults={
                "total_units": total_units,
                "revenue_booked": revenue_booked,
                "revenue_collected": revenue_collected,
                "outstanding": outstanding,
                "avg_construction": avg_construction,
                "satisfaction_avg": satisfaction_avg,
                "net_cashflow_mtd": net_cashflow_mtd,
                "at_risk_projects": at_risk_projects,
                "stalled_projects": stalled_projects,
                "ring_alerts": ring_alerts,
                "active_complaints": active_complaints,
                "compliance_alerts": compliance_alerts,
            },
        )
        self.stdout.write(f"OrgKPI_Daily: 1 row for {KPI_DATE} (Total Units {total_units}, Revenue Booked 19.72 Cr, etc.)")

        self.stdout.write(self.style.SUCCESS("Done. Executive Overview for MICL seeded as per image."))
