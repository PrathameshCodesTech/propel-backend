from datetime import date, timedelta
from decimal import Decimal
import random

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from core.models import (
    Organization, Department, Employee,
    UnitType, LeadChannel, CancellationReason,
    ComplaintCategory, MilestonePhase,
)

from projects.models import Project, Unit

from crm.models import (
    Customer, CustomerStageEvent, Booking, CustomerPayment,
    CustomerSatisfactionSurvey, Complaint
)

from construction.models import (
    Contractor, Milestone, DailyProgress, DelayPenalty, DelayPrediction
)

from finance.models import (
    Vendor, VendorBill, VendorPayment, CashFlowEntry, CashFlowForecast
)

from analytics.models import (
    ProjectKPI_Daily, OrgKPI_Daily, OrgMonthlySnapshot, ProjectMonthlySnapshot
)

from compliance.models import LegalCase, ComplianceItem, RERARegistration
from governance.models import QuarterlyPerformance, RevenueTimeline, RiskAssessment, KeyHighlight
from people.models import KRA, EmployeeKRA, EmployeeStatusEvent, HiringGap, CriticalAttention
from alerts.models import Alert


User = get_user_model()


class Command(BaseCommand):
    help = "Seed demo data for Propel Insights (all apps)"

    def add_arguments(self, parser):
        parser.add_argument("--org", default="PROPEL", help="Organization code")
        parser.add_argument("--users", type=int, default=8, help="How many demo users")
        parser.add_argument("--projects", type=int, default=3, help="How many projects")
        parser.add_argument("--units_per_project", type=int, default=25, help="Units per project")
        parser.add_argument("--reset", action="store_true", help="Delete existing demo org data first")

    @transaction.atomic
    def handle(self, *args, **opts):
        org_code = opts["org"]
        users_n = opts["users"]
        projects_n = opts["projects"]
        units_per_project = opts["units_per_project"]
        reset = opts["reset"]

        if reset:
            # Safe delete only org-specific data
            Organization.objects.filter(code=org_code).delete()

        org, _ = Organization.objects.get_or_create(
            code=org_code,
            defaults=dict(
                name="Propel Demo Organization",
                phone="9999999999",
                email="demo@propel.local",
                currency="INR",
                address="Mumbai, India",
                website="https://example.com",
            )
        )

        # --- Lookups (custom choices) ---
        dept_sales, _ = Department.objects.get_or_create(
            organization=org, code="SALES",
            defaults={"name": "Sales", "type": Department.DeptType.SALES}
        )
        dept_construction, _ = Department.objects.get_or_create(
            organization=org, code="CONST",
            defaults={"name": "Construction", "type": Department.DeptType.CONSTRUCTION}
        )
        dept_finance, _ = Department.objects.get_or_create(
            organization=org, code="FIN",
            defaults={"name": "Finance", "type": Department.DeptType.FINANCE}
        )
        dept_marketing, _ = Department.objects.get_or_create(
            organization=org, code="MKT",
            defaults={"name": "Marketing", "type": Department.DeptType.MARKETING}
        )

        unit_types = []
        for code, label in [("1bhk", "1BHK"), ("2bhk", "2BHK"), ("3bhk", "3BHK"), ("studio", "Studio"), ("shop", "Shop")]:
            ut, _ = UnitType.objects.get_or_create(organization=org, code=code, defaults={"label": label, "is_active": True})
            unit_types.append(ut)

        channels = []
        for code, label in [("digital", "Digital"), ("broker", "Broker"), ("direct", "Direct"), ("referral", "Referral")]:
            ch, _ = LeadChannel.objects.get_or_create(organization=org, code=code, defaults={"label": label, "is_active": True})
            channels.append(ch)

        for code, label in [("loan_rejection", "Loan Rejection"), ("price", "Price too High"), ("location", "Location")]:
            CancellationReason.objects.get_or_create(organization=org, code=code, defaults={"label": label, "is_active": True})

        complaint_cats = []
        for code, label in [("quality", "Quality"), ("documentation", "Documentation"), ("payment", "Payment Issues"), ("delay", "Construction Delay")]:
            cc, _ = ComplaintCategory.objects.get_or_create(organization=org, code=code, defaults={"label": label, "is_active": True})
            complaint_cats.append(cc)

        phases = []
        for i, name in enumerate(["Foundation", "Structure", "MEP", "Finishing", "Handover"], start=1):
            ph, _ = MilestonePhase.objects.get_or_create(organization=org, name=name, defaults={"order": i, "is_active": True})
            phases.append(ph)

        # --- Users + Employees ---
        employees = []
        # Admin user
        admin_user, _ = User.objects.get_or_create(
            username=f"{org_code.lower()}_admin",
            defaults={"email": "admin@propel.local", "first_name": "Admin", "last_name": "User"}
        )
        admin_user.set_password("Admin@123")
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

        admin_emp, _ = Employee.objects.get_or_create(
            user=admin_user,
            organization=org,
            defaults={"employee_code": "E000", "role": Employee.Role.CEO, "department": dept_sales, "phone": "9000000000"}
        )
        employees.append(admin_emp)

        roles = [
            (Employee.Role.SALES_MANAGER, dept_sales),
            (Employee.Role.SALES_EXECUTIVE, dept_sales),
            (Employee.Role.PROJECT_MANAGER, dept_construction),
            (Employee.Role.SITE_ENGINEER, dept_construction),
            (Employee.Role.FINANCE_MANAGER, dept_finance),
            (Employee.Role.MARKETING_MANAGER, dept_marketing),
            (Employee.Role.CUSTOMER_SERVICE, dept_sales),
        ]

        for i in range(1, users_n + 1):
            u, _ = User.objects.get_or_create(
                username=f"{org_code.lower()}_user{i}",
                defaults={"email": f"user{i}@propel.local", "first_name": f"User{i}", "last_name": "Demo"}
            )
            u.set_password("User@123")
            u.save()

            role, dept = roles[(i - 1) % len(roles)]
            emp, _ = Employee.objects.get_or_create(
                user=u,
                organization=org,
                defaults={"employee_code": f"E{100+i}", "role": role, "department": dept, "phone": f"9000000{100+i}"}
            )
            employees.append(emp)

        sales_execs = [e for e in employees if e.role in [Employee.Role.SALES_EXECUTIVE, Employee.Role.SALES_MANAGER]]

        # --- Contractors ---
        contractors = []
        for name in ["ABC Infra", "Skyline Builders", "Omega MEP"]:
            c, _ = Contractor.objects.get_or_create(organization=org, name=name, defaults={"specialization": "Civil", "performance_score": Decimal("82.5")})
            contractors.append(c)

        # --- Projects + Units ---
        projects = []
        for p in range(1, projects_n + 1):
            pr, _ = Project.objects.get_or_create(
                organization=org,
                project_code=f"P{p:03d}",
                defaults={
                    "name": f"Propel Heights {p}",
                    "location": f"Location {p}",
                    "city": "Mumbai",
                    "status": Project.Status.ON_TRACK if p % 2 else Project.Status.AT_RISK,
                    "planned_start_date": date.today() - timedelta(days=180),
                    "planned_completion_date": date.today() + timedelta(days=365),
                    "expected_completion_date": date.today() + timedelta(days=420),
                    "budget": Decimal("250000000.00") + Decimal(p * 10000000),
                    "rera_registration_number": f"RERA-{org_code}-{p}",
                    "rera_valid_until": date.today() + timedelta(days=900),
                }
            )
            projects.append(pr)

            # Units
            for u in range(1, units_per_project + 1):
                ut = random.choice(unit_types)
                status = random.choice([Unit.Status.AVAILABLE, Unit.Status.BOOKED, Unit.Status.SOLD, Unit.Status.BLOCKED])
                Unit.objects.get_or_create(
                    project=pr,
                    unit_number=f"{p}-{u:03d}",
                    defaults={
                        "unit_type": ut,
                        "floor": (u % 20) + 1,
                        "tower": f"T{(u % 3) + 1}",
                        "carpet_area": Decimal("450.0") + Decimal((u % 5) * 50),
                        "built_up_area": Decimal("600.0") + Decimal((u % 5) * 60),
                        "base_price": Decimal("8000000.00") + Decimal(u * 50000),
                        "final_price": Decimal("8500000.00") + Decimal(u * 55000),
                        "status": status,
                        "listed_date": date.today() - timedelta(days=random.randint(10, 200)),
                    }
                )

        # --- Customers + Funnel + Bookings + Payments + Complaints ---
        for pr in projects:
            units = list(Unit.objects.filter(project=pr)[:max(10, units_per_project // 2)])
            for i in range(1, 11):
                channel = random.choice(channels)
                cust, _ = Customer.objects.get_or_create(
                    organization=org,
                    customer_code=f"{pr.project_code}-C{i:03d}",
                    defaults={
                        "name": f"Customer {i} ({pr.project_code})",
                        "email": f"cust{i}_{pr.project_code.lower()}@mail.com",
                        "phone": f"91{random.randint(7000000000, 9999999999)}",
                        "project": pr,
                        "unit": random.choice(units) if units else None,
                        "channel": channel,
                        "status": random.choice([Customer.Status.WALK_IN, Customer.Status.APPLIED, Customer.Status.BOOKED]),
                        "assigned_to": random.choice(sales_execs) if sales_execs else None,
                        "walk_in_date": date.today() - timedelta(days=random.randint(1, 60)),
                    }
                )

                CustomerStageEvent.objects.get_or_create(
                    organization=org, customer=cust,
                    stage="walk_in",
                    defaults={"notes": "Walk-in created"}
                )

                # Create booking for few customers
                if i % 3 == 0 and cust.unit:
                    b = Booking.objects.create(
                        customer=cust,
                        project=pr,
                        unit=cust.unit,
                        sales_executive=cust.assigned_to,
                        booking_value=cust.unit.final_price,
                        booking_date=date.today() - timedelta(days=random.randint(1, 30)),
                        status=Booking.Status.ACTIVE,
                    )
                    cust.status = Customer.Status.BOOKED
                    cust.booking_date = b.booking_date
                    cust.save(update_fields=["status", "booking_date", "updated_at"])

                    CustomerStageEvent.objects.create(
                        organization=org, customer=cust, stage="booked", notes="Auto-booked in seed"
                    )

                    # Payments
                    CustomerPayment.objects.create(booking=b, amount=Decimal("200000.00"), paid_on=b.booking_date, reference="BK-ADV")
                    CustomerPayment.objects.create(booking=b, amount=Decimal("150000.00"), paid_on=b.booking_date + timedelta(days=10), reference="BK-INST")

                # Complaint for few customers
                if i % 4 == 0:
                    Complaint.objects.create(
                        customer=cust,
                        project=pr,
                        category=random.choice(complaint_cats),
                        description="Sample complaint created by seed",
                        status=random.choice([Complaint.Status.OPEN, Complaint.Status.IN_PROGRESS]),
                        assigned_to=random.choice(employees),
                        risk_score=Decimal(str(random.randint(10, 90))),
                    )

                # Satisfaction survey
                if i % 2 == 0:
                    CustomerSatisfactionSurvey.objects.create(
                        organization=org,
                        customer=cust,
                        project=pr,
                        score=Decimal(str(random.randint(2, 5))),
                        feedback="Demo feedback",
                    )

        # --- Construction: milestones + daily progress + delay widgets ---
        for pr in projects:
            for idx, ph in enumerate(phases, start=1):
                ms = Milestone.objects.create(
                    project=pr,
                    phase=ph,
                    name=f"{ph.name} - {pr.project_code}",
                    planned_start=date.today() - timedelta(days=160 - idx * 20),
                    planned_end=date.today() - timedelta(days=120 - idx * 20),
                    status=random.choice([Milestone.Status.IN_PROGRESS, Milestone.Status.COMPLETED, Milestone.Status.DELAYED]),
                    completion_percent=Decimal(str(random.randint(20, 100))),
                    contractor=random.choice(contractors),
                    contractor_score=Decimal("8.0"),
                    order=idx,
                )

                if ms.status == Milestone.Status.DELAYED:
                    DelayPenalty.objects.create(
                        project=pr, milestone=ms, contractor=ms.contractor,
                        delay_days=random.randint(5, 30),
                        penalty_per_day=Decimal("15000.00"),
                        penalty_amount=Decimal("15000.00") * Decimal(random.randint(5, 30)),
                        pending_recovery=Decimal("50000.00"),
                        critical_escalations=random.randint(0, 2),
                        escalation_level=random.choice([DelayPenalty.Escalation.LOW, DelayPenalty.Escalation.MEDIUM, DelayPenalty.Escalation.HIGH]),
                        recorded_on=date.today(),
                    )

            # last 14 days progress
            for d in range(14):
                dt = date.today() - timedelta(days=14 - d)
                DailyProgress.objects.get_or_create(
                    project=pr, date=dt,
                    defaults={
                        "planned_percent": Decimal(str(40 + d)),
                        "actual_percent": Decimal(str(35 + d)),
                        "workers_present": random.randint(40, 120),
                        "equipment_deployed": random.randint(3, 12),
                        "notes": "Demo daily progress",
                    }
                )

            DelayPrediction.objects.update_or_create(
                project=pr, prediction_date=date.today(),
                defaults=dict(
                    model_version="v1.0",
                    predicted_delay_days=random.randint(0, 45),
                    model_confidence=Decimal("76.5"),
                    weather_risk=Decimal("20"),
                    material_risk=Decimal("30"),
                    contractor_risk=Decimal("25"),
                    financial_risk=Decimal("15"),
                    regulatory_risk=Decimal("10"),
                    ai_insight_summary="Demo AI insight",
                    recommendations=["Increase manpower", "Lock material contracts"],
                )
            )

        # --- Finance: vendors, bills, cashflow, forecast ---
        vendor1, _ = Vendor.objects.get_or_create(organization=org, name="Cement Supplier")
        vendor2, _ = Vendor.objects.get_or_create(organization=org, name="Steel Supplier")

        for pr in projects:
            b1, _ = VendorBill.objects.update_or_create(
                vendor=vendor1, bill_no=f"{pr.project_code}-B001",
                defaults=dict(
                    project=pr,
                    bill_date=date.today()-timedelta(days=20),
                    due_date=date.today()+timedelta(days=10),
                    amount=Decimal("1200000.00"),
                    status=VendorBill.Status.PARTIAL,
                )
            )
            VendorPayment.objects.update_or_create(
                bill=b1, reference="VP-001",
                defaults=dict(amount=Decimal("500000.00"), paid_on=date.today()-timedelta(days=10))
            )

            b2, _ = VendorBill.objects.update_or_create(
                vendor=vendor2, bill_no=f"{pr.project_code}-B002",
                defaults=dict(
                    project=pr,
                    bill_date=date.today()-timedelta(days=15),
                    due_date=date.today()+timedelta(days=15),
                    amount=Decimal("900000.00"),
                    status=VendorBill.Status.UNPAID,
                )
            )

            # CashFlow entries
            CashFlowEntry.objects.create(organization=org, project=pr, flow_type=CashFlowEntry.FlowType.INFLOW, amount=Decimal("2500000.00"),
                                         date=date.today()-timedelta(days=5), category="Collections", description="Demo inflow")
            CashFlowEntry.objects.create(organization=org, project=pr, flow_type=CashFlowEntry.FlowType.OUTFLOW, amount=Decimal("1200000.00"),
                                         date=date.today()-timedelta(days=3), category="Vendors", description="Demo outflow")

        # 6 months forecast
        base = date.today().replace(day=1)
        cumulative = Decimal("0")
        for m in range(6):
            dt = (base + timedelta(days=31*m)).replace(day=1)
            inflow = Decimal(str(4000000 + m*250000))
            outflow = Decimal(str(3200000 + m*200000))
            net = inflow - outflow
            cumulative += net
            CashFlowForecast.objects.update_or_create(
                organization=org, year=dt.year, month=dt.month,
                defaults=dict(projected_inflow=inflow, projected_outflow=outflow, net_cashflow=net, cumulative=cumulative,
                              confidence=CashFlowForecast.Confidence.MEDIUM, key_risks="Interest rate risk")
            )

        # --- Marketing (analytics.models) ---
        try:
            from analytics.models import MarketingCampaign, LocationDemandMonthly
            for code, name, spend, leads, bookings, cpl, cpb, roi in [
                (f"{org_code}-M001", "Google Ads - Q1", "500000", 320, 18, "1562.50", "27777.78", "3.2"),
                (f"{org_code}-M002", "Facebook - Q1", "280000", 180, 12, "1555.56", "23333.33", "2.8"),
                (f"{org_code}-M003", "LinkedIn - Q1", "150000", 95, 8, "1578.95", "18750.00", "2.1"),
            ]:
                MarketingCampaign.objects.get_or_create(
                    organization=org,
                    campaign_code=code,
                    defaults=dict(
                        name=name, channel=random.choice(channels),
                        start_date=date.today()-timedelta(days=45), end_date=date.today()+timedelta(days=15),
                        spend=Decimal(spend), leads=leads, bookings=bookings,
                        cost_per_lead=Decimal(cpl), cost_per_booking=Decimal(cpb), roi=Decimal(roi),
                    )
                )
            for loc, city, enq, book, score in [
                ("Andheri", "Mumbai", 420, 26, "8.4"),
                ("Bandra", "Mumbai", 380, 22, "7.8"),
                ("Powai", "Mumbai", 290, 18, "7.2"),
            ]:
                LocationDemandMonthly.objects.get_or_create(
                    organization=org, location=loc, city=city, year=date.today().year, month=date.today().month,
                    defaults=dict(enquiries=enq, bookings=book, demand_score=Decimal(score))
                )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Marketing seed skipped: {e}"))

        # --- Analytics snapshots (today) ---
        today = date.today()
        OrgKPI_Daily.objects.update_or_create(
            organization=org, date=today,
            defaults=dict(
                total_units=projects_n * units_per_project,
                revenue_booked=Decimal("50000000.00"),
                revenue_collected=Decimal("12000000.00"),
                outstanding=Decimal("38000000.00"),
                avg_construction=Decimal("56.2"),
                satisfaction_avg=Decimal("4.1"),
                ring_alerts=2, stalled_projects=1, at_risk_projects=1, active_complaints=4, compliance_alerts=1,
                net_cashflow_mtd=Decimal("1300000.00"),
            )
        )

        for pr in projects:
            ProjectKPI_Daily.objects.update_or_create(
                project=pr, date=today,
                defaults=dict(
                    total_units=units_per_project,
                    sold_units=Unit.objects.filter(project=pr, status=Unit.Status.SOLD).count(),
                    booked_units=Unit.objects.filter(project=pr, status=Unit.Status.BOOKED).count(),
                    blocked_units=Unit.objects.filter(project=pr, status=Unit.Status.BLOCKED).count(),
                    unsold_units=Unit.objects.filter(project=pr, status=Unit.Status.AVAILABLE).count(),
                    revenue_booked=Decimal("15000000.00"),
                    revenue_collected=Decimal("3500000.00"),
                    outstanding=Decimal("11500000.00"),
                    construction_percent=Decimal("55.5"),
                    satisfaction_avg=Decimal("4.0"),
                    budget=pr.budget,
                    cost_incurred=Decimal("82000000.00"),
                    margin_percent=Decimal("18.5"),
                )
            )

        OrgMonthlySnapshot.objects.update_or_create(
            organization=org, year=today.year, month=today.month,
            defaults=dict(
                total_units=projects_n * units_per_project,
                revenue_booked=Decimal("52000000.00"),
                revenue_collected=Decimal("13000000.00"),
                outstanding=Decimal("39000000.00"),
                cash_inflow=Decimal("9000000.00"),
                cash_outflow=Decimal("7700000.00"),
                net_cashflow=Decimal("1300000.00"),
                avg_satisfaction=Decimal("4.1"),
                bookings_count=24,
                avg_ticket_size=Decimal("9500000.00"),
            )
        )

        for pr in projects:
            ProjectMonthlySnapshot.objects.update_or_create(
                project=pr, organization=org, year=today.year, month=today.month,
                defaults=dict(
                    units_sold=Unit.objects.filter(project=pr, status=Unit.Status.SOLD).count(),
                    units_available=Unit.objects.filter(project=pr, status=Unit.Status.AVAILABLE).count(),
                    construction_percentage=Decimal("55.5"),
                    revenue_booked=Decimal("15000000.00"),
                    revenue_collected=Decimal("3500000.00"),
                    budget=pr.budget,
                    cost_incurred=Decimal("82000000.00"),
                    margin_percentage=Decimal("18.5"),
                    unsold_units=Unit.objects.filter(project=pr, status=Unit.Status.AVAILABLE).count(),
                    avg_unsold_age=120,
                )
            )

        # --- Compliance ---
        for pr in projects:
            LegalCase.objects.get_or_create(
                project=pr, case_id=f"{pr.project_code}-LC01",
                defaults=dict(case_type="consumer-complaint", description="Demo legal case", severity="medium", status="open",
                              filing_date=today - timedelta(days=60))
            )
            ComplianceItem.objects.get_or_create(
                project=pr, item_name="Fire NOC",
                defaults=dict(status=ComplianceItem.Status.PENDING, due_date=today + timedelta(days=30))
            )
            RERARegistration.objects.update_or_create(
                project=pr,
                defaults=dict(status=RERARegistration.Status.COMPLIANT, registration_number=pr.rera_registration_number or "RERA-DEMO",
                              valid_until=pr.rera_valid_until or (today + timedelta(days=800)))
            )

        # --- Governance / Board ---
        QuarterlyPerformance.objects.update_or_create(
            organization=org, year=today.year, quarter=((today.month - 1)//3) + 1,
            defaults=dict(target=Decimal("100000000.00"), booked=Decimal("52000000.00"), realized=Decimal("13000000.00"))
        )
        RevenueTimeline.objects.update_or_create(
            organization=org, year=today.year,
            defaults=dict(projected=Decimal("300000000.00"), realized=Decimal("120000000.00"))
        )
        RiskAssessment.objects.create(
            organization=org, risk_type="construction", impact_level="medium",
            description="Demo risk for board view", assessed_on=today
        )
        KeyHighlight.objects.create(
            organization=org, title="Bookings Momentum", description="Strong pipeline this month", highlight_date=today
        )

        # --- People ---
        kra1, _ = KRA.objects.get_or_create(organization=org, name="Bookings", department=dept_sales)
        for emp in employees[:5]:
            EmployeeKRA.objects.update_or_create(
                organization=org, employee=emp, kra=kra1, year=today.year, month=today.month,
                defaults=dict(target=Decimal("10"), achieved=Decimal(str(random.randint(2, 10))), achievement_percentage=Decimal("0"))
            )
            EmployeeStatusEvent.objects.get_or_create(
                organization=org, employee=emp, event="joined",
                defaults=dict(effective_date=today - timedelta(days=200), reason="Seed data")
            )

        for pr in projects:
            HiringGap.objects.get_or_create(
                organization=org, project=pr, department=dept_construction, role="Site Engineer",
                defaults=dict(required=5, current=3, gap=2, impact="high")
            )

        CriticalAttention.objects.get_or_create(
            organization=org, employee=random.choice(employees),
            defaults=dict(task_area="sales", reason="Pipeline dropping", action="Review leads quality", is_resolved=False)
        )

        # --- Alerts ---
        Alert.objects.get_or_create(
            organization=org, title="Compliance pending", message="Fire NOC pending for one project",
            defaults=dict(alert_type=Alert.AlertType.COMPLIANCE, priority=Alert.Priority.HIGH, is_resolved=False)
        )

        # Avoid unicode symbols that fail on cp1252 terminals
        self.stdout.write(self.style.SUCCESS("Demo seed completed!"))
        self.stdout.write(self.style.WARNING("Login: admin username = %s_admin, password = Admin@123" % org_code.lower()))
