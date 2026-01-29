"""
Seed Sales Performance data for MICL as per static.
Run after seed_micl_executive and seed_micl_crm. Run: python manage.py seed_micl_sales

KPIs: Total Bookings YTD 349, Revenue 564.38 Cr, Avg Ticket 1.62 Cr, Conversion 24.5%, Top Performer Arjun 9.2 Cr.
Sales by Channel: Digital 35%, Broker 45%, Direct 20%.
Sales team: Arjun, Priya, Rohit, Sneha, Vivek, Ananya (target vs achieved, EmployeeKRA).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Organization, Department, Employee, LeadChannel
from crm.models import Customer, Booking
from people.models import KRA, EmployeeKRA
User = get_user_model()
ORG_CODE = "MICL"

# (first_name, last_name, role, target_cr, achieved_cr)
SALES_TEAM = [
    ("Arjun", "Verma", "sales_manager", 8.5, 9.2),
    ("Priya", "Patel", "sales_executive", 4.5, 3.8),
    ("Rohit", "Kumar", "regional_head", 6.0, 6.2),
    ("Sneha", "Gupta", "sales_manager", 5.0, 4.6),
    ("Vivek", "Sharma", "sales_executive", 5.5, 6.0),
    ("Ananya", "Singh", "sales_executive", 4.0, 3.2),
]

TOTAL_BOOKINGS_YTD = 349
REVENUE_YTD_CR = Decimal("564.38")
CHANNEL_PCT = {"Digital": 35, "Broker": 45, "Direct": 20}


class Command(BaseCommand):
    help = "Seed Sales Performance (employees, KRA, bookings, channel mix) for MICL."

    def add_arguments(self, parser):
        parser.add_argument("--clear-team", action="store_true", help="Delete MICL sales employees (and users) before seeding")

    @transaction.atomic
    def handle(self, *args, **options):
        org = Organization.objects.filter(code=ORG_CODE).first()
        if not org:
            self.stdout.write(self.style.ERROR(f"Organization {ORG_CODE} not found. Run seed_micl_executive first."))
            return

        dept, _ = Department.objects.get_or_create(
            organization=org,
            code="SALES",
            defaults={"name": "Sales", "type": Department.DeptType.SALES},
        )

        kra, _ = KRA.objects.get_or_create(
            organization=org,
            name="Sales",
            defaults={},
        )

        today = date.today()
        y1 = today.year
        m1 = today.month
        year_start = date(y1, 1, 1)

        if options.get("clear_team"):
            to_del = list(Employee.objects.filter(
                organization=org,
                role__in=[
                    Employee.Role.SALES_EXECUTIVE,
                    Employee.Role.SALES_MANAGER,
                    Employee.Role.REGIONAL_HEAD,
                ],
            ).select_related("user"))
            users_to_del = []
            for emp in to_del:
                Booking.objects.filter(sales_executive=emp).update(sales_executive=None)
                if emp.user_id:
                    users_to_del.append(emp.user_id)
                emp.delete()
            User.objects.filter(id__in=users_to_del).delete()
            self.stdout.write(f"Cleared {len(to_del)} MICL sales employees (and users).")

        employees = []
        for i, (first, last, role, target_cr, achieved_cr) in enumerate(SALES_TEAM):
            uname = f"sales.{first.lower()}.{org.code}".replace(" ", ".")
            user, _ = User.objects.get_or_create(
                username=uname,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": f"{uname}@example.com",
                    "is_active": True,
                },
            )
            user.set_password("demo123")
            user.save(update_fields=["password"])
            emp, _ = Employee.objects.update_or_create(
                organization=org,
                employee_code=f"EMP-S{i+1:02d}",
                defaults={
                    "user": user,
                    "department": dept,
                    "role": role,
                    "is_active": True,
                },
            )
            employees.append(emp)

            target_val = Decimal(str(target_cr)) * Decimal("10000000")
            achieved_val = Decimal(str(achieved_cr)) * Decimal("10000000")
            pct = round(float(achieved_val / target_val * 100), 1) if target_val else 0
            pct = min(100, pct)  # model validator caps at 100
            EmployeeKRA.objects.update_or_create(
                organization=org,
                employee=emp,
                kra=kra,
                year=y1,
                month=m1,
                defaults={
                    "target": target_val,
                    "achieved": achieved_val,
                    "achievement_percentage": Decimal(str(pct)),
                },
            )
        self.stdout.write(f"Sales team: {len(employees)} employees, KRA Sales, EmployeeKRA for {y1}-{m1}.")

        bookings_qs = (
            Booking.objects.filter(
                customer__organization=org,
                status=Booking.Status.ACTIVE,
            )
            .select_related("customer", "project", "unit")
            .order_by("id")
        )
        n_existing = bookings_qs.count()
        if n_existing < TOTAL_BOOKINGS_YTD:
            self.stdout.write(
                self.style.WARNING(
                    f"Found {n_existing} active bookings; need {TOTAL_BOOKINGS_YTD}. Run seed_micl_crm first."
                )
            )
            self.stdout.write(self.style.SUCCESS("Sales team + KRA seeded. Bookings/channel not updated."))
            return

        revenue_target = REVENUE_YTD_CR * Decimal("10000000")
        n_per_emp = 4
        rev_assigned = sum(Decimal(str(s[4])) * Decimal("10000000") for s in SALES_TEAM)
        rev_unassigned = revenue_target - rev_assigned

        to_update = list(bookings_qs[:TOTAL_BOOKINGS_YTD])
        days_in_year = 365
        cur = 0
        for ei, emp in enumerate(employees):
            ach_cr = SALES_TEAM[ei][4]
            ach_val = Decimal(str(ach_cr)) * Decimal("10000000")
            for _ in range(n_per_emp):
                if cur >= len(to_update):
                    break
                b = to_update[cur]
                b.booking_value = ach_val / n_per_emp
                d = min(cur * days_in_year // max(1, len(to_update)), days_in_year - 1)
                b.booking_date = year_start + timedelta(days=d)
                b.sales_executive = emp
                b.save(update_fields=["booking_value", "booking_date", "sales_executive"])
                cur += 1
        rem = len(to_update) - cur
        each = rev_unassigned / rem if rem else Decimal(0)
        for i in range(cur, len(to_update)):
            b = to_update[i]
            b.booking_value = each
            d = min(i * days_in_year // max(1, len(to_update)), days_in_year - 1)
            b.booking_date = year_start + timedelta(days=d)
            b.sales_executive = None
            b.save(update_fields=["booking_value", "booking_date", "sales_executive"])

        self.stdout.write(f"Updated {len(to_update)} bookings (YTD, revenue ~564.38 Cr, {len(employees)} with sales_exec).")

        ch_map = {c.label: c for c in LeadChannel.objects.filter(organization=org)}
        total = Customer.objects.filter(organization=org).count()
        if total and ch_map and "Digital" in ch_map and "Broker" in ch_map and "Direct" in ch_map:
            n_d = int(round(total * CHANNEL_PCT["Digital"] / 100))
            n_b = int(round(total * CHANNEL_PCT["Broker"] / 100))
            qs = Customer.objects.filter(organization=org).order_by("id")
            for i, c in enumerate(qs):
                if i < n_d:
                    c.channel = ch_map["Digital"]
                elif i < n_d + n_b:
                    c.channel = ch_map["Broker"]
                else:
                    c.channel = ch_map["Direct"]
                c.save(update_fields=["channel"])
            self.stdout.write(f"Channel distribution: Digital ~{CHANNEL_PCT['Digital']}%, Broker ~{CHANNEL_PCT['Broker']}%, Direct ~{CHANNEL_PCT['Direct']}%.")

        self.stdout.write(self.style.SUCCESS("Sales Performance seed done. Open Sales Performance (org MICL)."))
