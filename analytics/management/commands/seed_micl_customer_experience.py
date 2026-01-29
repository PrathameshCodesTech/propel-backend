"""
Seed Customer Experience data for MICL as per static.
Run after seed_micl_executive, seed_micl_crm. Run: python manage.py seed_micl_customer_experience

KPIs: Avg Satisfaction 4.3 (3.2% vs LQ), Open Complaints 8 (-12.5% vs LM), Escalated 17,
  Resolution Rate 31% (5.8% vs LM), Referral Bookings 48 (12% of total, 18.5% trend).
Satisfaction by Project: Skyline 4.5, Green 4.8, Urban 4.6, Sunrise 4.7, Coastal 4.4.
Complaint Status: Open 8, In Progress 8, Resolved 15, Escalated 17.
Complaint Categories: Construction Quality 14, Modification Request 12, Customer Service 10, Payment Issues 8, Delay Compensation 6, Amenities 4.
Satisfaction Trend: 12 months (Jan 4.1, Feb 4.0, Mar 4.2, Apr 4.1, May 4.3, Jun 4.2, Jul 4.2, Aug 4.0, Sep 3.9, Oct 4.2, Nov 4.1, Dec 4.4).
At-Risk Customers: 10 customers with satisfaction 3.0-3.4 (High risk).
"""
from datetime import date, timedelta, datetime
from decimal import Decimal
import random

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Avg
from django.utils import timezone

from core.models import Organization, ComplaintCategory
from projects.models import Project
from crm.models import Customer, CustomerSatisfactionSurvey, Complaint, Booking


ORG_CODE = "MICL"

# Project satisfaction scores
PROJECT_SATISFACTION = {
    "SKY001": 4.5,  # Skyline
    "GRV001": 4.8,  # Green Valley
    "URB001": 4.6,  # Urban Oasis
    "SUN001": 4.7,  # Sunrise
    "COA001": 4.4,  # Coastal
}

# Monthly satisfaction trend (Jan-Dec)
MONTHLY_SATISFACTION = [
    4.1, 4.0, 4.2, 4.1, 4.3, 4.2, 4.2, 4.0, 3.9, 4.2, 4.1, 4.4,
]

# Complaint status counts
COMPLAINT_STATUS = {
    "open": 8,
    "in_progress": 8,
    "resolved": 15,
    "escalated": 17,
}

# Complaint categories (category_code -> count)
COMPLAINT_CATEGORIES = {
    "construction_quality": 14,
    "modification_request": 12,
    "customer_service": 10,
    "payment_issues": 8,
    "delay_compensation": 6,
    "amenities": 4,
}

# At-risk customers: (customer_code, name, satisfaction_score, status, unit_number)
AT_RISK_CUSTOMERS = [
    ("CUST00005", "Arun Bose", 3.1, "booked", "C-1802"),
    ("CUST00010", "Arun Kumar", 3.0, "possession", "A-301"),
    ("CUST00015", "Jaya Kapoor", 3.4, "booked", "D-204"),
    ("CUST00023", "Uma Joshi", 3.0, "applied", "A-1203"),
    ("CUST00024", "Sunita Agarwal", 3.0, "booked", "D-2104"),
    ("CUST00028", "Jaya Verma", 3.0, "walk_in", "A-1302"),
    ("CUST00037", "Amit Kapoor", 3.2, "applied", "B-1003"),
    ("CUST00038", "Rajesh Verma", 3.1, "booked", "D-1302"),
    ("CUST00043", "Sanjay Mehta", 3.3, "booked", "C-304"),
    ("CUST00045", "Arun Patel", 3.3, "booked", "B-2103"),
]


class Command(BaseCommand):
    help = "Seed Customer Experience (satisfaction surveys, complaints, at-risk customers) for MICL."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Delete MICL satisfaction surveys and complaints before seeding")

    @transaction.atomic
    def handle(self, *args, **options):
        org = Organization.objects.filter(code=ORG_CODE).first()
        if not org:
            self.stdout.write(self.style.ERROR(f"Organization {ORG_CODE} not found. Run seed_micl_executive first."))
            return

        projects = {p.project_code: p for p in Project.objects.filter(organization=org)}
        if not projects:
            self.stdout.write(self.style.ERROR("No projects found. Run seed_micl_executive first."))
            return

        if options.get("clear"):
            CustomerSatisfactionSurvey.objects.filter(organization=org).delete()
            Complaint.objects.filter(project__organization=org).delete()
            self.stdout.write("Cleared MICL satisfaction surveys and complaints.")

        today = date.today()
        y1, m1 = today.year, today.month

        # ----- 1) Complaint Categories -----
        cat_map = {}
        for code, label in [
            ("construction_quality", "Construction Quality"),
            ("modification_request", "Modification Request"),
            ("customer_service", "Customer Service"),
            ("payment_issues", "Payment Issues"),
            ("delay_compensation", "Delay Compensation"),
            ("amenities", "Amenities"),
        ]:
            cat, _ = ComplaintCategory.objects.get_or_create(
                organization=org,
                code=code,
                defaults={"label": label, "is_active": True},
            )
            cat_map[code] = cat

        # ----- 2) Complaints -----
        all_customers = list(Customer.objects.filter(organization=org).select_related("project")[:100])
        total_needed = sum(COMPLAINT_STATUS.values())
        if len(all_customers) < total_needed:
            self.stdout.write(
                self.style.WARNING(f"Only {len(all_customers)} customers found; need {total_needed} for complaints.")
            )
            return

        # Create complaints: first assign categories, then statuses
        cat_list = []
        for cat_code, count in COMPLAINT_CATEGORIES.items():
            cat = cat_map.get(cat_code)
            if cat:
                cat_list.extend([cat] * count)
        random.shuffle(cat_list)

        status_list = []
        for status, count in COMPLAINT_STATUS.items():
            status_list.extend([status] * count)
        random.shuffle(status_list)

        idx = 0
        for i in range(total_needed):
            if idx >= len(all_customers):
                idx = 0
            cust = all_customers[idx]
            idx += 1
            proj = cust.project or list(projects.values())[0]
            cat = cat_list[i] if i < len(cat_list) else random.choice(list(cat_map.values()))
            stat = status_list[i] if i < len(status_list) else random.choice(list(COMPLAINT_STATUS.keys()))
            Complaint.objects.create(
                customer=cust,
                project=proj,
                category=cat,
                description=f"Sample complaint for {cust.name} - {cat.label}",
                status=stat,
            )
        self.stdout.write(f"Complaints: {total_needed} created (status and category distribution).")

        # ----- 3) Customer Satisfaction Scores (project-wise) -----
        for proj_code, target_score in PROJECT_SATISFACTION.items():
            proj = projects.get(proj_code)
            if not proj:
                continue
            proj_customers = Customer.objects.filter(organization=org, project=proj)
            n = proj_customers.count()
            if n == 0:
                continue
            # Set scores around target (slight variation)
            scores = [target_score + random.uniform(-0.2, 0.2) for _ in range(n)]
            scores = [max(3.0, min(5.0, round(s, 1))) for s in scores]
            for cust, score in zip(proj_customers, scores):
                cust.satisfaction_score_cached = Decimal(str(score))
                cust.save(update_fields=["satisfaction_score_cached"])

        # Overall average should be ~4.3
        all_cust = list(Customer.objects.filter(organization=org))
        n_all = len(all_cust)
        if n_all > 0:
            avg_target = 4.3
            current_avg = float(
                Customer.objects.filter(organization=org).aggregate(
                    avg=Avg("satisfaction_score_cached")
                )["avg"] or 0
            )
            if abs(current_avg - avg_target) > 0.1:
                # Adjust scores to hit 4.3 average
                diff = avg_target - current_avg
                for cust in all_cust:
                    current = float(cust.satisfaction_score_cached or 0)
                    if current > 0:
                        new_score = current + diff
                        new_score = max(3.0, min(5.0, round(new_score, 1)))
                        cust.satisfaction_score_cached = Decimal(str(new_score))
                        cust.save(update_fields=["satisfaction_score_cached"])

        self.stdout.write("Customer satisfaction_score_cached updated (project-wise + overall ~4.3).")

        # ----- 4) At-Risk Customers (low satisfaction) -----
        sky = projects.get("SKY001")
        if sky:
            from core.models import LeadChannel, UnitType
            from projects.models import Unit
            ch = LeadChannel.objects.filter(organization=org).first()
            ut = UnitType.objects.filter(organization=org).first()
            for cust_code, name, score, status, unit_num in AT_RISK_CUSTOMERS:
                # Ensure unit exists
                unit, _ = Unit.objects.get_or_create(
                    project=sky,
                    unit_number=unit_num,
                    defaults={
                        "unit_type": ut,
                        "tower": unit_num.split("-")[0] if "-" in unit_num else "A",
                        "floor": int(unit_num.split("-")[1][:2]) if "-" in unit_num and len(unit_num.split("-")[1]) >= 2 else 1,
                    },
                )
                # Find or create customer
                cust = Customer.objects.filter(organization=org, customer_code=cust_code).first()
                if not cust:
                    cust = Customer.objects.create(
                        organization=org,
                        customer_code=cust_code,
                        name=name,
                        email=f"{cust_code.lower()}@example.com",
                        phone=f"98765{cust_code[-3:]}",
                        project=sky,
                        unit=unit,
                        channel=ch,
                        status=status,
                        satisfaction_score_cached=Decimal(str(score)),
                    )
                else:
                    cust.name = name
                    cust.satisfaction_score_cached = Decimal(str(score))
                    cust.status = status
                    cust.project = sky
                    cust.unit = unit
                    cust.save(update_fields=["name", "satisfaction_score_cached", "status", "project", "unit"])
        self.stdout.write(f"At-risk customers: {len(AT_RISK_CUSTOMERS)} created/updated (satisfaction 3.0-3.4).")

        # ----- 5) CustomerSatisfactionSurvey (monthly trend) -----
        # Generate surveys for last 12 months
        month_customers = list(Customer.objects.filter(organization=org)[:50])
        for i, score in enumerate(MONTHLY_SATISFACTION):
            d = today - relativedelta(months=11 - i)
            month_start = date(d.year, d.month, 1)
            # Create ~10 surveys per month
            for j in range(10):
                if j >= len(month_customers):
                    break
                cust = month_customers[j % len(month_customers)]
                proj = cust.project or list(projects.values())[0]
                survey_date = month_start + timedelta(days=random.randint(0, 27))
                CustomerSatisfactionSurvey.objects.create(
                    organization=org,
                    customer=cust,
                    project=proj,
                    score=Decimal(str(round(score + random.uniform(-0.1, 0.1), 1))),
                    surveyed_at=timezone.make_aware(
                        datetime.combine(survey_date, datetime.min.time())
                    ),
                )
        self.stdout.write("CustomerSatisfactionSurvey: 12 months trend seeded (~120 surveys).")

        # ----- 6) Referral Bookings (48 bookings, 12% of total) -----
        # Ensure some bookings have referral/broker channel
        total_bookings = Booking.objects.filter(project__organization=org, status=Booking.Status.ACTIVE).count()
        referral_target = 48
        referral_percent = (referral_target / total_bookings * 100) if total_bookings > 0 else 0
        if referral_percent < 11 or referral_percent > 13:
            # Update some customers to have referral/broker channel
            from core.models import LeadChannel
            referral_ch = LeadChannel.objects.filter(organization=org, code__in=["broker", "referral"]).first()
            if not referral_ch:
                referral_ch, _ = LeadChannel.objects.get_or_create(
                    organization=org,
                    code="referral",
                    defaults={"label": "Referral", "is_active": True},
                )
            # Get customers with bookings
            booked_customers = Customer.objects.filter(
                organization=org,
                bookings__status=Booking.Status.ACTIVE,
            ).distinct()[:referral_target]
            for cust in booked_customers:
                cust.channel = referral_ch
                cust.save(update_fields=["channel"])
        self.stdout.write(f"Referral bookings: ~{referral_target} (via channel assignment).")

        self.stdout.write(self.style.SUCCESS("Customer Experience seed done. Open Customer Experience (org MICL)."))
