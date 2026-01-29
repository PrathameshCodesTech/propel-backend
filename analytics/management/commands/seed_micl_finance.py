"""
Seed Finance & Cashflow data for MICL as per static.
Run after seed_micl_executive and seed_micl_crm. Run: python manage.py seed_micl_finance

KPIs: Revenue Booked 197.20 Cr, Revenue Collected 128.80 Cr, Receivables 69 Cr (34% overdue 90+),
  Payables 12 Cr (2.8 Cr Due Now), Net Cashflow MTD 4.70 Cr (8.5% vs LM).
Monthly cashflow chart (Jan–Dec), 6‑month forecast, receivables/payables aging, P&L, budget vs actual, margin alerts.
"""
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce

from core.models import Organization
from projects.models import Project, Unit
from crm.models import Customer, Booking, CustomerPayment
from finance.models import Vendor, VendorBill, CashFlowEntry, CashFlowForecast
from analytics.models import OrgMonthlySnapshot, ProjectKPI_Daily


ORG_CODE = "MICL"

# Finance chart (Jan–Dec): inflow Cr, outflow Cr, net Cr — we map to our 12 months
MONTHLY_CASH_CR = [
    (10, 8, 2), (11, 8.5, 2.5), (12, 9, 3), (10.5, 8.5, 2), (11.5, 9.5, 2),
    (12.5, 10, 2.5), (11.5, 9.5, 2), (12.5, 9.5, 3), (13.5, 10.5, 3), (14.5, 11.5, 3),
    (16.5, 12.5, 4), (17.5, 13.5, 4),
]

# 6‑month forecast (Jan–Jun 2025): inflow Cr, outflow Cr, net Cr, cumulative Cr, confidence, key_risks
FORECAST = [
    (19.5, 14.5, 5.0, 28.5, "high", ""),
    (18.8, 15.2, 3.6, 32.1, "high", "Green Valley OC pending"),
    (21.0, 16.8, 4.2, 36.3, "medium", "Quarterly tax payments due"),
    (17.5, 15.8, 1.7, 38.0, "medium", "Urban Oasis milestone payments"),
    (22.5, 17.2, 5.3, 43.3, "low", "Possession handovers, Market uncertainty"),
    (19.8, 16.5, 3.3, 46.6, "low", "Multiple contractor payments, Monsoon delays possible"),
]

# Receivables: total 69 Cr, 90+ = 23.8 Cr, 34% overdue 90+
RECEIVABLES_TOTAL_CR = Decimal("69")
RECEIVABLES_90_PLUS_CR = Decimal("23.8")
# Payables: total 12 Cr, Due Now 2.8 Cr
PAYABLES_TOTAL_CR = Decimal("12")
PAYABLES_DUE_NOW_CR = Decimal("2.8")
# Net MTD 4.70 Cr, trend 8.5% vs LM
NET_MTD_CR = Decimal("4.70")
TREND_PCT = 8.5

# Project budgets (Cr) for budget vs actual: Skyline, Green, Urban, Sunrise, Coastal. Urban set for 8.2% overrun.
BUDGETS_CR = (28, 19, 13.33, 18, 22)


class Command(BaseCommand):
    help = "Seed Finance & Cashflow (cashflow, forecast, receivables, payables, budgets) for MICL."

    def add_arguments(self, parser):
        parser.add_argument("--clear-forecast", action="store_true", help="Delete MICL CashFlowForecast before seeding")
        parser.add_argument("--clear-receivables", action="store_true", help="Delete finance receivables bookings before seeding")
        parser.add_argument("--clear-payables", action="store_true", help="Delete MICL vendor bills before seeding")

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

        today = date.today()
        y1, m1 = today.year, today.month
        year_start = date(y1, 1, 1)
        mtd_start = date(y1, m1, 1)

        # ----- 1) OrgMonthlySnapshot cash (12 months) -----
        months_qs = (
            OrgMonthlySnapshot.objects.filter(organization=org)
            .order_by("year", "month")
        )
        snapshots = list(months_qs[:12])
        for i, snap in enumerate(snapshots):
            if i >= len(MONTHLY_CASH_CR):
                break
            incr, outcr, netcr = MONTHLY_CASH_CR[i]
            snap.cash_inflow = Decimal(str(incr)) * Decimal("10000000")
            snap.cash_outflow = Decimal(str(outcr)) * Decimal("10000000")
            snap.net_cashflow = Decimal(str(netcr)) * Decimal("10000000")
            snap.save(update_fields=["cash_inflow", "cash_outflow", "net_cashflow"])
        self.stdout.write(f"Updated OrgMonthlySnapshot cash for {len(snapshots)} months.")

        # Last month net for 8.5% trend (MTD net = 4.70 Cr)
        lm_year = y1 if m1 > 1 else y1 - 1
        lm_month = m1 - 1 if m1 > 1 else 12
        lm_net_cr = NET_MTD_CR / (Decimal("1") + Decimal(str(TREND_PCT)) / Decimal("100"))
        OrgMonthlySnapshot.objects.filter(
            organization=org, year=lm_year, month=lm_month
        ).update(net_cashflow=lm_net_cr * Decimal("10000000"))

        # ----- 2) CashFlowEntry MTD -----
        CashFlowEntry.objects.filter(
            organization=org,
            date__gte=mtd_start,
            date__lte=today,
        ).delete()
        net_mtd = NET_MTD_CR * Decimal("10000000")
        # Simple split: inflow 20 Cr, outflow 15.3 Cr -> net 4.7 Cr
        inflow_mtd = Decimal("200000000")
        outflow_mtd = inflow_mtd - net_mtd
        CashFlowEntry.objects.create(
            organization=org,
            flow_type=CashFlowEntry.FlowType.INFLOW,
            amount=inflow_mtd,
            date=mtd_start,
            category="collections",
        )
        CashFlowEntry.objects.create(
            organization=org,
            flow_type=CashFlowEntry.FlowType.OUTFLOW,
            amount=outflow_mtd,
            date=mtd_start,
            category="payments",
        )
        self.stdout.write(f"CashFlowEntry MTD: net {NET_MTD_CR} Cr.")

        # ----- 3) CashFlowForecast (next 6 months from today) -----
        if options.get("clear_forecast"):
            CashFlowForecast.objects.filter(organization=org).delete()
        for i, (incr, outcr, netcr, cumcr, conf, risks) in enumerate(FORECAST):
            d = today + relativedelta(months=i)
            y, m = d.year, d.month
            CashFlowForecast.objects.update_or_create(
                organization=org,
                year=y,
                month=m,
                defaults={
                    "projected_inflow": Decimal(str(incr)) * Decimal("10000000"),
                    "projected_outflow": Decimal(str(outcr)) * Decimal("10000000"),
                    "net_cashflow": Decimal(str(netcr)) * Decimal("10000000"),
                    "cumulative": Decimal(str(cumcr)) * Decimal("10000000"),
                    "confidence": conf,
                    "key_risks": risks or "",
                },
            )
        self.stdout.write("CashFlowForecast: 6 months (next from today).")

        # ----- 4) Receivables -----
        sky = projects.get("SKY001")
        if sky:
            self._seed_receivables(org, sky, options.get("clear_receivables"))
        else:
            self.stdout.write(self.style.WARNING("Skyline project not found; skipping receivables."))

        # ----- 5) Payables -----
        if options.get("clear_payables"):
            VendorBill.objects.filter(project__organization=org).delete()
        self._seed_payables(org, projects, today)

        # ----- 6) Project budgets -----
        codes = ["SKY001", "GRV001", "URB001", "SUN001", "COA001"]
        for idx, code in enumerate(codes):
            proj = projects.get(code)
            if not proj or idx >= len(BUDGETS_CR):
                continue
            proj.budget = Decimal(str(BUDGETS_CR[idx])) * Decimal("10000000")
            proj.save(update_fields=["budget"])
        self.stdout.write("Project budgets updated.")

        self.stdout.write(self.style.SUCCESS("Finance & Cashflow seed done. Open Finance (org MICL)."))

    def _seed_receivables(self, org, project, clear_receivables):
        from crm.models import Customer, Booking, CustomerPayment

        tag = "finance_receivables"
        today = date.today()

        if clear_receivables:
            Booking.objects.filter(
                customer__organization=org,
                customer__customer_code__startswith=tag,
            ).delete()
            Customer.objects.filter(organization=org, customer_code__startswith=tag).delete()

        # Zero out existing org receivables so only our finance bookings contribute
        for b in Booking.objects.filter(
            customer__organization=org,
            status=Booking.Status.ACTIVE,
        ).exclude(customer__customer_code__startswith=tag).select_related("customer"):
            paid = CustomerPayment.objects.filter(booking=b).aggregate(s=Coalesce(Sum("amount"), Decimal("0")))["s"]
            out = (b.booking_value or Decimal("0")) - paid
            if out > 0:
                CustomerPayment.objects.create(
                    booking=b,
                    amount=out,
                    paid_on=today,
                    reference="finance-seed-zero",
                )

        units = list(
            Unit.objects.filter(project=project)
            .exclude(bookings__status=Booking.Status.ACTIVE)
            .distinct()
            .order_by("id")[:120]
        )
        if not units:
            units = list(Unit.objects.filter(project=project).order_by("id")[:120])
        if not units:
            self.stdout.write(self.style.WARNING("No units for receivables; skipping."))
            return

        n90 = RECEIVABLES_90_PLUS_CR * Decimal("10000000")
        n_other = (RECEIVABLES_TOTAL_CR - RECEIVABLES_90_PLUS_CR) * Decimal("10000000")
        n_90 = max(1, min(15, len(units) // 4))
        per_90 = n90 / n_90
        old = today - timedelta(days=120)
        used = 0
        for i in range(n_90):
            u = units[used]
            used += 1
            c, _ = Customer.objects.get_or_create(
                organization=org,
                customer_code=f"{tag}_90_{i}",
                defaults={
                    "name": f"Receivable 90+ {i}",
                    "project": project,
                    "status": Customer.Status.BOOKED,
                    "walk_in_date": old,
                },
            )
            Booking.objects.update_or_create(
                customer=c,
                project=project,
                unit=u,
                defaults={
                    "booking_value": per_90,
                    "booking_date": old,
                    "status": Booking.Status.ACTIVE,
                },
            )
        n_o = max(3, min(30, len(units) - n_90))
        per_bucket = n_other / 3
        n_per_bucket = max(1, n_o // 3)
        per_o = per_bucket / n_per_bucket
        for j, days_ago in enumerate([15, 45, 75]):
            bd = today - timedelta(days=days_ago)
            for i in range(n_per_bucket):
                if used >= len(units):
                    break
                u = units[used]
                used += 1
                idx = n_90 + n_per_bucket * j + i
                c, _ = Customer.objects.get_or_create(
                    organization=org,
                    customer_code=f"{tag}_o_{idx}",
                    defaults={
                        "name": f"Receivable other {idx}",
                        "project": project,
                        "status": Customer.Status.BOOKED,
                        "walk_in_date": bd,
                    },
                )
                Booking.objects.update_or_create(
                    customer=c,
                    project=project,
                    unit=u,
                    defaults={
                        "booking_value": per_o,
                        "booking_date": bd,
                        "status": Booking.Status.ACTIVE,
                    },
                )
        self.stdout.write(f"Receivables: ~{RECEIVABLES_TOTAL_CR} Cr total, 90+ ~{RECEIVABLES_90_PLUS_CR} Cr.")

    def _seed_payables(self, org, projects, today):
        vendor, _ = Vendor.objects.get_or_create(
            organization=org,
            name="MICL Construction Vendor",
            defaults={},
        )
        proj_list = list(projects.values())[:5]
        if not proj_list:
            return
        due_now = PAYABLES_DUE_NOW_CR * Decimal("10000000")
        rest = (PAYABLES_TOTAL_CR - PAYABLES_DUE_NOW_CR) * Decimal("10000000")
        # Due Now
        for i, proj in enumerate(proj_list[:2]):
            amt = due_now / 2
            due = today - timedelta(days=5)
            VendorBill.objects.update_or_create(
                vendor=vendor,
                bill_no=f"FIN-DN-{proj.project_code}-{i}",
                defaults={
                    "project": proj,
                    "bill_date": today - timedelta(days=30),
                    "due_date": due,
                    "amount": amt,
                    "status": VendorBill.Status.UNPAID,
                },
            )
        # 0–30, 31–60, 60+
        for i, (days, _) in enumerate([(15, "0-30"), (45, "31-60"), (75, "60+")]):
            due = today + timedelta(days=days)
            amt = rest / 3
            proj = proj_list[i % len(proj_list)]
            VendorBill.objects.update_or_create(
                vendor=vendor,
                bill_no=f"FIN-{i}-{proj.project_code}",
                defaults={
                    "project": proj,
                    "bill_date": today - timedelta(days=20),
                    "due_date": due,
                    "amount": amt,
                    "status": VendorBill.Status.UNPAID,
                },
            )
        self.stdout.write(f"Payables: total ~{PAYABLES_TOTAL_CR} Cr, Due Now ~{PAYABLES_DUE_NOW_CR} Cr.")
