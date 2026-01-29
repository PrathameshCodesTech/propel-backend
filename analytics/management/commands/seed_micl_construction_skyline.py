"""
Seed Construction dashboard data for Skyline Heights (and penalty tracker) as per static.
Run after seed_micl_executive. Run: python manage.py seed_micl_construction_skyline
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Organization
from projects.models import Project
from construction.models import Contractor, Milestone, DailyProgress, DelayPenalty, DelayPrediction
from analytics.models import ProjectKPI_Daily


ORG_CODE = "MICL"

# Project summary: 78% actual, 82% planned, 4% behind, expected 2025-06-30
SKYLINE_PLANNED_START = date(2022, 3, 15)
SKYLINE_PLANNED_END = date(2025, 9, 15)   # yields ~82% planned on 2025-01-27
SKYLINE_EXPECTED_END = date(2025, 6, 30)

CONTRACTORS = [
    "BuildMax Construction",
    "SteelCore Structures",
    "ElectraTech Systems",
    "PremiumFinish Interiors",
    "LandscapePro",
    "FoundationGrind",
    "StructureMax",
    "PowerGrid",
    "DeepFoundation Corp.",
    "MetroStructures",
    "CoastalFoundations",
    "ChennaiStructures",
]

# (name, planned_start, planned_end, actual_start, actual_end, status, contractor_name, contractor_score)
# actual_end None => "In Progress"
SKYLINE_MILESTONES = [
    ("Foundation & Excavation", date(2022, 3, 15), date(2022, 7, 30), date(2022, 3, 20), date(2022, 8, 15), "completed", "BuildMax Construction", 4.2),
    ("Structural Work - Tower A", date(2022, 8, 1), date(2023, 6, 30), date(2022, 8, 20), date(2023, 8, 10), "completed", "SteelCore Structures", 3.8),
    ("Structural Work - Tower B", date(2023, 1, 1), date(2023, 12, 31), date(2023, 2, 15), date(2024, 2, 28), "completed", "SteelCore Structures", 3.5),
    ("MEP Installation", date(2023, 9, 1), date(2024, 6, 30), date(2023, 10, 15), None, "in_progress", "ElectraTech Systems", 4.0),
    ("Interior Finishing", date(2024, 4, 1), date(2025, 3, 31), date(2024, 6, 1), None, "in_progress", "PremiumFinish Interiors", 4.3),
    ("External Development", date(2024, 10, 1), date(2025, 5, 30), date(2024, 11, 15), None, "delayed", "LandscapePro", 3.9),
]

# Delay penalty tracker: Total 1.67 Cr, Pending 96.45 L, Critical 1, Avg 64 days
# (project_code, contractor_name, milestone_name, delay_days, penalty_amount, pending_recovery, escalation)
# Sum penalty 16.7e6, pending 9.645e6. One critical for "Critical Escalations: 1"
PENALTIES = [
    ("SKY001", "SteelCore Structures", "Structural Work - Tower B", 58, 2_900_000, 0, "critical"),
    ("URB001", "DeepFoundation Corp.", "Foundation & Excavation", 46, 2_300_000, 2_300_000, "low"),
    ("URB001", "MetroStructures", "Structural Work - Phase 1", 92, 5_200_000, 5_200_000, "high"),
    ("COA001", "CoastalFoundations", "Foundation & Excavation", 51, 2_550_000, 2_145_000, "high"),
    ("COA001", "ChennaiStructures", "Structural Work - Phase 1", 75, 3_750_000, 0, "low"),
]

# AI Delay Prediction (ML Model v2.1): Skyline +45d 87%, Urban +85d 92%, Coastal +62d 78%
# (project_code, delay_days, confidence, weather, material, contractor, financial, regulatory, insight, recommendations)
PREDICTIONS = [
    (
        "SKY001",
        45,
        87,
        25, 75, 72, 20, 30,  # Labor/Material high -> contractor+material
        "Based on historical patterns and current velocity, project is likely to experience 45 days delay primarily due to MEP installation bottleneck. Labor productivity has dropped 12% in the last month.",
        [
            "Increase labor force by 15% for MEP work",
            "Pre-order finishing materials to avoid supply chain delays",
            "Schedule contractor review meetings bi-weekly",
        ],
    ),
    (
        "URB001",
        85,
        92,
        40, 78, 85, 35, 45,
        "Critical: Multiple high-risk factors detected. Current trajectory shows 85 days delay with 92% confidence. Immediate intervention required on contractor performance and labor allocation.",
        [
            "Consider contractor replacement for structural work",
            "Implement parallel workstreams to recover schedule",
            "Escalate material procurement to management",
            "Add night shifts for critical path activities",
        ],
    ),
    (
        "COA001",
        62,
        78,
        80, 45, 35, 25, 88,  # Regulatory + Weather high
        "Regulatory delays due to CRZ clearance are the primary concern. Weather patterns suggest monsoon will impact Q2-Q3 2025. Recommend accelerating current phase work.",
        [
            "Expedite CRZ clearance resolution",
            "Plan construction schedule around monsoon season",
            "Engage backup contractors for structural work",
        ],
    ),
]

# Urban / Coastal milestones for penalty linkage (minimal)
EXTRA_MILESTONES = [
    ("URB001", "Foundation & Excavation", date(2022, 1, 1), date(2022, 6, 30), "DeepFoundation Corp.", 4.0),
    ("URB001", "Structural Work - Phase 1", date(2022, 7, 1), date(2023, 12, 31), "MetroStructures", 3.5),
    ("COA001", "Foundation & Excavation", date(2022, 2, 1), date(2022, 7, 31), "CoastalFoundations", 4.0),
    ("COA001", "Structural Work - Phase 1", date(2022, 8, 1), date(2024, 3, 31), "ChennaiStructures", 3.8),
]


class Command(BaseCommand):
    help = "Seed Construction data for Skyline (milestones, contractors, daily progress, delay penalties) as per static."

    def add_arguments(self, parser):
        parser.add_argument("--clear-penalties", action="store_true", help="Delete org delay penalties before seeding (avoids dupes on re-run)")

    @transaction.atomic
    def handle(self, *args, **options):
        org = Organization.objects.filter(code=ORG_CODE).first()
        if not org:
            self.stdout.write(self.style.ERROR(f"Organization {ORG_CODE} not found. Run seed_micl_executive first."))
            return

        projects = {p.project_code: p for p in Project.objects.filter(organization=org)}
        for code in ["SKY001", "URB001", "COA001"]:
            if code not in projects:
                self.stdout.write(self.style.ERROR(f"Project {code} not found. Run seed_micl_executive first."))
                return

        sky = projects["SKY001"]
        urb = projects["URB001"]
        coa = projects["COA001"]

        # Update Skyline project dates
        sky.planned_start_date = SKYLINE_PLANNED_START
        sky.planned_completion_date = SKYLINE_PLANNED_END
        sky.expected_completion_date = SKYLINE_EXPECTED_END
        sky.save(update_fields=["planned_start_date", "planned_completion_date", "expected_completion_date"])
        self.stdout.write("Skyline project dates updated (planned start/end, expected completion 2025-06-30)")

        # Contractors
        contractors = {}
        for name in CONTRACTORS:
            c, _ = Contractor.objects.get_or_create(organization=org, name=name, defaults={"is_active": True})
            contractors[name] = c
        self.stdout.write(f"Contractors: {len(CONTRACTORS)}")

        # Skyline milestones
        for idx, (name, ps, pe, ast, aen, status, cname, score) in enumerate(SKYLINE_MILESTONES):
            m, _ = Milestone.objects.update_or_create(
                project=sky,
                name=name,
                defaults={
                    "planned_start": ps,
                    "planned_end": pe,
                    "actual_start": ast,
                    "actual_end": aen,
                    "status": status,
                    "contractor": contractors.get(cname),
                    "contractor_score": Decimal(str(score)),
                    "order": idx,
                    "completion_percent": 100 if status == "completed" else 65,
                },
            )
        self.stdout.write(f"Skyline milestones: {len(SKYLINE_MILESTONES)}")

        # Urban / Coastal milestones for penalties
        code_proj = {"URB001": urb, "COA001": coa}
        for code, mname, ps, pe, cname, score in EXTRA_MILESTONES:
            p = code_proj[code]
            Milestone.objects.update_or_create(
                project=p,
                name=mname,
                defaults={
                    "planned_start": ps,
                    "planned_end": pe,
                    "actual_start": ps,
                    "actual_end": pe,
                    "status": "completed",
                    "contractor": contractors.get(cname),
                    "contractor_score": Decimal(str(score)),
                    "order": 0,
                    "completion_percent": 100,
                },
            )
        self.stdout.write("Urban/Coastal milestones for penalty linkage created")

        # Daily progress (Skyline, last 30 days). Actual below planned, ~40-45% at end
        today = date.today()
        thirty_days_ago = today - timedelta(days=30)
        DailyProgress.objects.filter(project=sky, date__gte=thirty_days_ago, date__lte=today).delete()
        for i in range(31):
            d = thirty_days_ago + timedelta(days=i)
            if d > today:
                break
            t = (i + 1) / 30.0
            planned = min(82, round(82 * t * 1.05, 2))
            actual = min(78, round(78 * t * 0.95, 2))
            DailyProgress.objects.create(
                project=sky,
                date=d,
                planned_percent=Decimal(str(planned)),
                actual_percent=Decimal(str(actual)),
            )
        self.stdout.write("Daily progress (Skyline, last 30 days) seeded")

        # Delay penalties
        if options.get("clear_penalties"):
            n = DelayPenalty.objects.filter(project__organization=org).delete()[0]
            self.stdout.write(f"Deleted {n} existing delay penalties")

        penalty_per_day = Decimal("50000")
        recorded = date(2024, 3, 1)
        for tup in PENALTIES:
            pcode, cname, mname, ddays, amount, pending, esc = tup
            proj = projects[pcode]
            contract = contractors.get(cname)
            mile = Milestone.objects.filter(project=proj, name=mname).first()
            if not mile:
                self.stdout.write(self.style.WARNING(f"Milestone {mname} not found for {pcode}; skip penalty"))
                continue
            DelayPenalty.objects.create(
                project=proj,
                milestone=mile,
                contractor=contract,
                delay_days=ddays,
                penalty_per_day=penalty_per_day,
                penalty_amount=Decimal(amount),
                pending_recovery=Decimal(pending),
                escalation_level=esc,
                recorded_on=recorded,
            )
            recorded = recorded + timedelta(days=1)
        self.stdout.write("Delay penalties seeded (Total 1.67 Cr, Pending 96.45 L, Critical 1, Avg 64 days)")

        # AI Delay Prediction (ML Model v2.1)
        pred_date = date(2025, 1, 27)
        for tup in PREDICTIONS:
            pcode, ddays, conf, weather, material, contractor, financial, regulatory, insight, recs = tup
            proj = projects[pcode]
            DelayPrediction.objects.update_or_create(
                project=proj,
                prediction_date=pred_date,
                defaults={
                    "model_version": "v2.1",
                    "predicted_delay_days": ddays,
                    "model_confidence": Decimal(conf),
                    "weather_risk": Decimal(weather),
                    "material_risk": Decimal(material),
                    "contractor_risk": Decimal(contractor),
                    "financial_risk": Decimal(financial),
                    "regulatory_risk": Decimal(regulatory),
                    "ai_insight_summary": insight,
                    "recommendations": recs,
                },
            )
        self.stdout.write("AI Delay Prediction seeded (Skyline +45d 87%, Urban +85d 92%, Coastal +62d 78%; High Risk 2, Avg 64d, Confidence 86%, Recs 10)")

        self.stdout.write(self.style.SUCCESS("Construction (Skyline) seed done. Open Construction & Site Tracker, select Skyline."))
