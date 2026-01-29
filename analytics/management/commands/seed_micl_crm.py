"""
Seed CRM & Customer Funnel data for MICL (Skyline) as per static.
Run after seed_micl_executive. Run: python manage.py seed_micl_crm

KPIs: Total 1368, Walk-ins MTD 59, Conversions MTD 270, Cancelled 51, Possession 79.
Funnel: Walk-ins 474, Applied 415, Booked 349, Possession 79, Cancelled 51.
Cancellation reasons: Price Concerns, Location Issues, Loan Rejection, Better Offer, Construction Delay.
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Organization, LeadChannel, CancellationReason, UnitType
from projects.models import Project, Unit
from crm.models import Customer, Booking, CustomerPayment


ORG_CODE = "MICL"

CHANNELS = [("digital", "Digital"), ("direct", "Direct"), ("broker", "Broker")]
CANCELLATION_REASONS = [
    ("price_concerns", "Price Concerns"),
    ("location_issues", "Location Issues"),
    ("loan_rejection", "Loan Rejection"),
    ("better_offer", "Better Offer"),
    ("construction_delay", "Construction Delay"),
]
UNIT_TYPES = [("1bhk", "1BHK"), ("2bhk", "2BHK"), ("3bhk", "3BHK"), ("4bhk", "4BHK")]

# Funnel: walk_in 474, applied 415, booked 349, possession 79, cancelled 51. MTD walk-ins 59, MTD conversions 270.
FUNNEL = {"walk_in": 474, "applied": 415, "booked": 349, "possession": 79, "cancelled": 51}
WALK_INS_MTD = 59
CONVERSIONS_MTD = 270

# Cancellation split (51 total): Price 14, Location 10, Loan 9, Better 8, Construction 10
CANCEL_SPLIT = {"price_concerns": 14, "location_issues": 10, "loan_rejection": 9, "better_offer": 8, "construction_delay": 10}

SAMPLE_NAMES = [
    "Suresh Shah", "Arun Joshi", "Priya Reddy", "Vikram Singh", "Anita Desai",
    "Rajesh Kumar", "Meera Nair", "Karan Patel", "Deepa Iyer", "Sanjay Verma",
    "Lakshmi Rao", "Aditya Menon", "Kavita Pillai", "Rahul Nambiar", "Neha Gupta",
]


def make_units(project, unit_types_map, n):
    out = []
    towers = ["A", "B", "C", "D"]
    ut_list = list(unit_types_map.values())
    for i in range(n):
        t = towers[i % 4]
        fl = (i // 4) % 50 + 1
        un = f"{t}-{fl}{(i % 1000):03d}"
        ut = ut_list[i % len(ut_list)]
        u, _ = Unit.objects.get_or_create(project=project, unit_number=un, defaults={"unit_type": ut})
        out.append(u)
    return out


class Command(BaseCommand):
    help = "Seed CRM & Customer Funnel (customers, funnel, cancellation reasons, sample list) for MICL Skyline."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Delete existing org customers (and related bookings/payments) before seeding")

    @transaction.atomic
    def handle(self, *args, **options):
        org = Organization.objects.filter(code=ORG_CODE).first()
        if not org:
            self.stdout.write(self.style.ERROR(f"Organization {ORG_CODE} not found. Run seed_micl_executive first."))
            return

        proj = Project.objects.filter(organization=org, project_code="SKY001").first()
        if not proj:
            self.stdout.write(self.style.ERROR("Project SKY001 (Skyline Heights) not found. Run seed_micl_executive first."))
            return

        today = date.today()
        current_month = today.replace(day=1)

        # LeadChannel, CancellationReason, UnitType
        channels = {}
        for code, label in CHANNELS:
            c, _ = LeadChannel.objects.get_or_create(organization=org, code=code, defaults={"label": label})
            channels[code] = c
        reasons = {}
        for code, label in CANCELLATION_REASONS:
            r, _ = CancellationReason.objects.get_or_create(organization=org, code=code, defaults={"label": label})
            reasons[code] = r
        ut_map = {}
        for code, label in UNIT_TYPES:
            u, _ = UnitType.objects.get_or_create(organization=org, code=code, defaults={"label": label})
            ut_map[code] = u

        # Units for Skyline (for booked/possession)
        n_units = FUNNEL["booked"] + FUNNEL["possession"] + 100
        units = make_units(proj, ut_map, n_units)
        self.stdout.write(f"Channels, cancellation reasons, unit types, {len(units)} units.")

        if options.get("clear"):
            bk_ids = list(Booking.objects.filter(customer__organization=org).values_list("id", flat=True))
            CustomerPayment.objects.filter(booking_id__in=bk_ids).delete()
            Booking.objects.filter(customer__organization=org).delete()
            n = Customer.objects.filter(organization=org).delete()[0]
            self.stdout.write(f"Cleared {n} customers (and related bookings/payments).")

        # Customers
        idx = 0
        cancel_queue = []
        for code, count in CANCEL_SPLIT.items():
            cancel_queue.extend([code] * count)
        random.shuffle(cancel_queue)

        def add_walkins():
            nonlocal idx
            base = date(2024, 1, 1)
            for i in range(FUNNEL["walk_in"]):
                idx += 1
                code = f"CUST{88880 + idx}"
                name = SAMPLE_NAMES[(idx - 1) % len(SAMPLE_NAMES)] if idx <= len(SAMPLE_NAMES) else f"Customer {idx}"
                in_mtd = i < WALK_INS_MTD
                d = current_month + timedelta(days=i % 20) if in_mtd else base + timedelta(days=(i * 7) % 300)
                ch = list(channels.values())[i % 3]
                Customer.objects.create(
                    organization=org,
                    customer_code=code,
                    name=name,
                    email=f"{code}@example.com",
                    phone=f"98765{idx:05d}",
                    project=proj,
                    unit=None,
                    channel=ch,
                    status="walk_in",
                    walk_in_date=d,
                    satisfaction_score_cached=Decimal(str(round(3.5 + (i % 5) * 0.1, 1))),
                )

        add_walkins()
        # Applied: 415
        base = date(2024, 2, 1)
        for i in range(FUNNEL["applied"]):
            idx += 1
            code = f"CUST{88880 + idx}"
            name = SAMPLE_NAMES[(idx - 1) % len(SAMPLE_NAMES)] if idx <= len(SAMPLE_NAMES) else f"Customer {idx}"
            d = base + timedelta(days=(i * 5) % 350)
            ch = list(channels.values())[i % 3]
            Customer.objects.create(
                organization=org,
                customer_code=code,
                name=name,
                email=f"{code}@example.com",
                phone=f"98765{idx:05d}",
                project=proj,
                unit=None,
                channel=ch,
                status="applied",
                walk_in_date=d - timedelta(days=7),
                application_date=d,
                satisfaction_score_cached=Decimal(str(round(3.5 + (i % 5) * 0.1, 1))),
            )
        # Booked: 349, 270 MTD; Possession: 79
        unit_off = FUNNEL["walk_in"] + FUNNEL["applied"]
        for status, n, mtd in [("booked", FUNNEL["booked"], CONVERSIONS_MTD), ("possession", FUNNEL["possession"], 0)]:
            base = date(2024, 3, 1)
            for i in range(n):
                idx += 1
                code = f"CUST{88880 + idx}"
                name = SAMPLE_NAMES[(idx - 1) % len(SAMPLE_NAMES)] if idx <= len(SAMPLE_NAMES) else f"Customer {idx}"
                in_mtd = status == "booked" and i < mtd
                bd = current_month + timedelta(days=i % 20) if in_mtd else base + timedelta(days=(i * 7) % 320)
                ch = list(channels.values())[i % 3]
                u = units[(idx - 1 - unit_off) % len(units)]
                cust = Customer.objects.create(
                    organization=org,
                    customer_code=code,
                    name=name,
                    email=f"{code}@example.com",
                    phone=f"98765{idx:05d}",
                    project=proj,
                    unit=u,
                    channel=ch,
                    status=status,
                    walk_in_date=bd - timedelta(days=14),
                    application_date=bd - timedelta(days=7),
                    booking_date=bd,
                    possession_date=bd + timedelta(days=90) if status == "possession" else None,
                    satisfaction_score_cached=Decimal(str(round(3.5 + (i % 5) * 0.1, 1))),
                )
                bval = Decimal(str(round(85 + (i % 40) * 0.5, 2))) * Decimal("100000")  # 85.5L–105L
                book = Booking.objects.create(
                    customer=cust,
                    project=proj,
                    unit=u,
                    booking_value=bval,
                    booking_date=bd,
                    status="active",
                )
                paid_pct = 0.7 if status == "possession" else (0.5 + (i % 5) * 0.1)
                paid = round(float(bval) * paid_pct, 0)
                if paid > 0:
                    CustomerPayment.objects.create(booking=book, amount=Decimal(paid), paid_on=bd + timedelta(days=1), reference=f"PMT-{idx}")
        # Cancelled: 51
        base = date(2024, 4, 1)
        for i in range(FUNNEL["cancelled"]):
            idx += 1
            code = f"CUST{88880 + idx}"
            name = SAMPLE_NAMES[(idx - 1) % len(SAMPLE_NAMES)] if idx <= len(SAMPLE_NAMES) else f"Customer {idx}"
            d = base + timedelta(days=(i * 11) % 280)
            r = reasons[cancel_queue[i]] if i < len(cancel_queue) else reasons["price_concerns"]
            ch = list(channels.values())[i % 3]
            Customer.objects.create(
                organization=org,
                customer_code=code,
                name=name,
                email=f"{code}@example.com",
                phone=f"98765{idx:05d}",
                project=proj,
                unit=None,
                channel=ch,
                status="cancelled",
                cancellation_reason=r,
                walk_in_date=d - timedelta(days=30),
                application_date=d - timedelta(days=14),
                cancellation_date=d,
                satisfaction_score_cached=Decimal("0"),
            )

        total = sum(FUNNEL.values())
        self.stdout.write(
            f"Customers: {total} (walk_in {FUNNEL['walk_in']}, applied {FUNNEL['applied']}, "
            f"booked {FUNNEL['booked']}, possession {FUNNEL['possession']}, cancelled {FUNNEL['cancelled']})."
        )
        self.stdout.write(f"Walk-ins MTD {WALK_INS_MTD}, Conversions MTD {CONVERSIONS_MTD}.")
        self.stdout.write(self.style.SUCCESS("CRM seed done. Open CRM & Customer Funnel (org MICL)."))
