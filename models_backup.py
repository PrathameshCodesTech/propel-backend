from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


# =============================================================================
# BASE / MULTI-TENANT
# =============================================================================

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True


class Organization(TimeStampedModel):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)

    logo = models.ImageField(upload_to="org_logos/", null=True, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)

    currency = models.CharField(max_length=3, default="INR")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


# =============================================================================
# ORG LOOKUPS (DB-DRIVEN "CHOICES" - CUSTOMIZABLE PER ORG)
# =============================================================================

class Department(TimeStampedModel):
    class DeptType(models.TextChoices):
        SALES = "sales", "Sales"
        CONSTRUCTION = "construction", "Construction"
        FINANCE = "finance", "Finance"
        MARKETING = "marketing", "Marketing"
        CUSTOMER_SERVICE = "customer_service", "Customer Service"
        LEGAL = "legal", "Legal"
        HR = "hr", "HR"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    type = models.CharField(max_length=50, choices=DeptType.choices)

    class Meta:
        unique_together = [("organization", "code")]
        ordering = ["name"]

    def __str__(self):
        return f"{self.organization.code} - {self.name}"


class Employee(TimeStampedModel):
    """
    User is global; employee profile is tenant-aware by organization.
    """
    class Role(models.TextChoices):
        CEO = "ceo", "CEO"
        REGIONAL_HEAD = "regional_head", "Regional Head"
        SALES_MANAGER = "sales_manager", "Sales Manager"
        SALES_EXECUTIVE = "sales_executive", "Sales Executive"
        PROJECT_MANAGER = "project_manager", "Project Manager"
        SITE_ENGINEER = "site_engineer", "Site Engineer"
        FINANCE_MANAGER = "finance_manager", "Finance Manager"
        MARKETING_MANAGER = "marketing_manager", "Marketing Manager"
        HR_MANAGER = "hr_manager", "HR Manager"
        LEGAL_HEAD = "legal_head", "Legal Head"
        CUSTOMER_SERVICE = "customer_service", "Customer Service"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employee_profile")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="employees")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="employees")

    employee_code = models.CharField(max_length=50)
    role = models.CharField(max_length=50, choices=Role.choices)

    phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("organization", "employee_code")]
        indexes = [
            models.Index(fields=["organization", "role"]),
        ]
        ordering = ["user__first_name", "user__last_name"]

    def __str__(self):
        return f"{self.user} ({self.organization.code})"


class UnitType(TimeStampedModel):
    """
    Replaces hardcoded 1BHK/2BHK... Admin can add custom types per org.
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="unit_types")
    code = models.CharField(max_length=50)      # e.g. "2bhk"
    label = models.CharField(max_length=100)    # e.g. "2BHK"
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("organization", "code")]
        ordering = ["label"]

    def __str__(self):
        return f"{self.label} ({self.organization.code})"


class LeadChannel(TimeStampedModel):
    """
    Replaces digital/broker/direct/referral choices. Customizable per org.
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="lead_channels")
    code = models.CharField(max_length=50)      # "digital"
    label = models.CharField(max_length=100)    # "Digital"
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("organization", "code")]
        ordering = ["label"]

    def __str__(self):
        return f"{self.label} ({self.organization.code})"


class CancellationReason(TimeStampedModel):
    """
    Replaces free-text cancellation_reason.
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="cancellation_reasons")
    code = models.CharField(max_length=50)     # "loan_rejection"
    label = models.CharField(max_length=120)   # "Loan Rejection"
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("organization", "code")]
        ordering = ["label"]

    def __str__(self):
        return f"{self.label} ({self.organization.code})"


class ComplaintCategory(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="complaint_categories")
    code = models.CharField(max_length=50)      # "documentation"
    label = models.CharField(max_length=120)    # "Documentation"
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("organization", "code")]
        ordering = ["label"]

    def __str__(self):
        return f"{self.label} ({self.organization.code})"


class MilestonePhase(TimeStampedModel):
    """
    Custom construction phases per org.
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="milestone_phases")
    name = models.CharField(max_length=200)  # "Foundation"
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("organization", "name")]
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.name} ({self.organization.code})"


# =============================================================================
# PROJECT / INVENTORY
# =============================================================================

class Project(TimeStampedModel):
    class Status(models.TextChoices):
        ON_TRACK = "on_track", "On Track"
        AT_RISK = "at_risk", "At Risk"
        DELAYED = "delayed", "Delayed"
        STALLED = "stalled", "Stalled"
        COMPLETED = "completed", "Completed"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="projects")

    name = models.CharField(max_length=200)
    project_code = models.CharField(max_length=50)
    location = models.CharField(max_length=200)
    city = models.CharField(max_length=100, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ON_TRACK)

    planned_start_date = models.DateField(null=True, blank=True)
    actual_start_date = models.DateField(null=True, blank=True)
    planned_completion_date = models.DateField(null=True, blank=True)
    expected_completion_date = models.DateField(null=True, blank=True)
    actual_completion_date = models.DateField(null=True, blank=True)

    # Finance
    budget = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    # Compliance
    rera_registration_number = models.CharField(max_length=120, blank=True)
    rera_valid_until = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = [("organization", "project_code")]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "location"]),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.organization.code})"


class Unit(TimeStampedModel):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        BLOCKED = "blocked", "Blocked"
        BOOKED = "booked", "Booked"
        SOLD = "sold", "Sold"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="units")
    unit_type = models.ForeignKey(UnitType, on_delete=models.SET_NULL, null=True, blank=True, related_name="units")

    unit_number = models.CharField(max_length=50)
    floor = models.IntegerField(default=0)
    tower = models.CharField(max_length=50, blank=True)

    carpet_area = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    built_up_area = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    base_price = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    final_price = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    listed_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = [("project", "unit_number")]
        indexes = [
            models.Index(fields=["project", "status"]),
        ]
        ordering = ["project", "tower", "floor", "unit_number"]

    def __str__(self):
        return f"{self.project.name} - {self.unit_number}"


# =============================================================================
# CRM / CUSTOMERS
# =============================================================================

class Customer(TimeStampedModel):
    class Status(models.TextChoices):
        WALK_IN = "walk_in", "Walk-in"
        APPLIED = "applied", "Applied"
        BOOKED = "booked", "Booked"
        POSSESSION = "possession", "Possession"
        CANCELLED = "cancelled", "Cancelled"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="customers")

    customer_code = models.CharField(max_length=50)  # internal id
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30)

    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="customers")
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True, related_name="customers")

    channel = models.ForeignKey(LeadChannel, on_delete=models.SET_NULL, null=True, blank=True, related_name="customers")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.WALK_IN)

    assigned_to = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_customers")

    cancellation_reason = models.ForeignKey(CancellationReason, on_delete=models.SET_NULL, null=True, blank=True, related_name="customers")

    walk_in_date = models.DateField(null=True, blank=True)
    application_date = models.DateField(null=True, blank=True)
    booking_date = models.DateField(null=True, blank=True)
    possession_date = models.DateField(null=True, blank=True)
    cancellation_date = models.DateField(null=True, blank=True)

    # This is cached (optional). Real truth can come from surveys table.
    satisfaction_score_cached = models.DecimalField(
        max_digits=3, decimal_places=1, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )

    class Meta:
        unique_together = [("organization", "customer_code")]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["project"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer_code} - {self.name}"


class CustomerStageEvent(TimeStampedModel):
    """
    Funnel movement timeline (Walk-in → Applied → Booked → Possession → Cancelled).
    Best for funnel charts + conversion calculations.
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="customer_stage_events")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="stage_events")

    stage = models.CharField(max_length=30)  # walk_in/applied/booked/possession/cancelled
    happened_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "stage"]),
            models.Index(fields=["happened_at"]),
        ]
        ordering = ["-happened_at"]


class Booking(TimeStampedModel):
    """
    Transactional booking (source of truth).
    """
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="bookings")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="bookings")
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="bookings")

    sales_executive = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="bookings")

    booking_value = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    booking_date = models.DateField()

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CANCELLED = "cancelled", "Cancelled"

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        indexes = [
            models.Index(fields=["project", "booking_date"]),
            models.Index(fields=["sales_executive", "booking_date"]),
        ]
        ordering = ["-booking_date"]


class CustomerPayment(TimeStampedModel):
    """
    Collections (Revenue collected).
    """
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=18, decimal_places=2, validators=[MinValueValidator(0)])
    paid_on = models.DateField()
    reference = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-paid_on"]
        indexes = [
            models.Index(fields=["paid_on"]),
        ]


class CustomerSatisfactionSurvey(TimeStampedModel):
    """
    Source of truth for satisfaction trend & at-risk customers.
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="satisfaction_surveys")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="satisfaction_surveys")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="satisfaction_surveys")

    score = models.DecimalField(max_digits=3, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(5)])
    feedback = models.TextField(blank=True)
    surveyed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "surveyed_at"]),
            models.Index(fields=["project", "surveyed_at"]),
        ]
        ordering = ["-surveyed_at"]


class Complaint(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"
        ESCALATED = "escalated", "Escalated"

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="complaints")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="complaints")
    category = models.ForeignKey(ComplaintCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="complaints")

    description = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)

    assigned_to = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="complaints")
    resolution_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    # for "At-risk customers" logic
    risk_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    class Meta:
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]
        ordering = ["-created_at"]


# =============================================================================
# CONSTRUCTION
# =============================================================================

class Contractor(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="contractors")
    name = models.CharField(max_length=200)
    specialization = models.CharField(max_length=200, blank=True)

    performance_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("organization", "name")]
        ordering = ["name"]


class Milestone(TimeStampedModel):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not Started"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        DELAYED = "delayed", "Delayed"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="milestones")
    phase = models.ForeignKey(MilestonePhase, on_delete=models.SET_NULL, null=True, blank=True, related_name="milestones")
    name = models.CharField(max_length=200)

    planned_start = models.DateField()
    planned_end = models.DateField()
    actual_start = models.DateField(null=True, blank=True)
    actual_end = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    completion_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    contractor = models.ForeignKey(Contractor, on_delete=models.SET_NULL, null=True, blank=True, related_name="milestones")
    contractor_score = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )

    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "planned_start"]
        indexes = [
            models.Index(fields=["project", "status"]),
        ]


class DailyProgress(TimeStampedModel):
    """
    For "Daily Progress Chart" (last 30 days).
    """
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="daily_progress")
    date = models.DateField()

    planned_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    actual_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    workers_present = models.IntegerField(default=0)
    equipment_deployed = models.IntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [("project", "date")]
        indexes = [models.Index(fields=["date"])]
        ordering = ["date"]


class DelayPenalty(TimeStampedModel):
    """
    Delay Penalty Tracker cards: total penalties, pending recovery, escalations etc.
    """
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="delay_penalties")
    milestone = models.ForeignKey(Milestone, on_delete=models.SET_NULL, null=True, blank=True, related_name="delay_penalties")
    contractor = models.ForeignKey(Contractor, on_delete=models.SET_NULL, null=True, blank=True, related_name="delay_penalties")

    delay_days = models.IntegerField(default=0)
    penalty_per_day = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    penalty_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    pending_recovery = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    critical_escalations = models.IntegerField(default=0)

    class Escalation(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    escalation_level = models.CharField(max_length=20, choices=Escalation.choices, default=Escalation.LOW)

    recorded_on = models.DateField()

    class Meta:
        indexes = [
            models.Index(fields=["project", "recorded_on"]),
            models.Index(fields=["escalation_level"]),
        ]
        ordering = ["-recorded_on"]


class DelayPrediction(TimeStampedModel):
    """
    AI Delay Prediction widget.
    Keep predictions per project per date.
    """
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="delay_predictions")
    model_version = models.CharField(max_length=50, default="v1.0")

    predicted_delay_days = models.IntegerField(default=0)
    model_confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # optional risk factors
    weather_risk = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    material_risk = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    contractor_risk = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    financial_risk = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    regulatory_risk = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    ai_insight_summary = models.TextField(blank=True)
    recommendations = models.JSONField(default=list, blank=True)

    prediction_date = models.DateField()

    class Meta:
        unique_together = [("project", "prediction_date")]
        indexes = [models.Index(fields=["prediction_date"])]
        ordering = ["-prediction_date"]


# =============================================================================
# FINANCE (CASHFLOW + VENDORS + FORECAST)
# =============================================================================

class Vendor(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="vendors")
    name = models.CharField(max_length=200)

    class Meta:
        unique_together = [("organization", "name")]
        ordering = ["name"]


class VendorBill(TimeStampedModel):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="bills")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="vendor_bills")

    bill_no = models.CharField(max_length=100)
    bill_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)

    amount = models.DecimalField(max_digits=18, decimal_places=2, validators=[MinValueValidator(0)])

    class Status(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIAL = "partial", "Partial"
        PAID = "paid", "Paid"

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNPAID)

    class Meta:
        unique_together = [("vendor", "bill_no")]
        indexes = [
            models.Index(fields=["project", "due_date"]),
            models.Index(fields=["status"]),
        ]


class VendorPayment(TimeStampedModel):
    bill = models.ForeignKey(VendorBill, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=18, decimal_places=2, validators=[MinValueValidator(0)])
    paid_on = models.DateField()
    reference = models.CharField(max_length=100, blank=True)


class CashFlowEntry(TimeStampedModel):
    """
    Monthly Cash inflow/outflow chart. Store granular entries (optional).
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="cashflow_entries")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="cashflow_entries")

    class FlowType(models.TextChoices):
        INFLOW = "inflow", "Inflow"
        OUTFLOW = "outflow", "Outflow"

    flow_type = models.CharField(max_length=20, choices=FlowType.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=2, validators=[MinValueValidator(0)])
    date = models.DateField()
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "date"]),
            models.Index(fields=["project", "date"]),
        ]
        ordering = ["-date"]


class CashFlowForecast(TimeStampedModel):
    """
    6-month cash flow forecast table.
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="cashflow_forecasts")

    year = models.IntegerField()
    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])

    projected_inflow = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    projected_outflow = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    net_cashflow = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cumulative = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Confidence(models.TextChoices):
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    confidence = models.CharField(max_length=20, choices=Confidence.choices, default=Confidence.MEDIUM)
    key_risks = models.TextField(blank=True)

    class Meta:
        unique_together = [("organization", "year", "month")]
        ordering = ["year", "month"]


# =============================================================================
# MARKETING & ROI
# =============================================================================

class MarketingCampaign(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="campaigns")

    name = models.CharField(max_length=200)
    campaign_code = models.CharField(max_length=50)

    channel = models.ForeignKey(LeadChannel, on_delete=models.SET_NULL, null=True, blank=True, related_name="campaigns")

    start_date = models.DateField()
    end_date = models.DateField()

    spend = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    leads = models.IntegerField(default=0)
    bookings = models.IntegerField(default=0)

    cost_per_lead = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cost_per_booking = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    roi = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Status(models.TextChoices):
        ON_TRACK = "on_track", "On Track"
        AT_RISK = "at_risk", "At Risk"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ON_TRACK)

    class Meta:
        unique_together = [("organization", "campaign_code")]
        indexes = [models.Index(fields=["organization", "status"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.organization.code})"


class LocationDemandMonthly(TimeStampedModel):
    """
    Location-wise demand table (Enquiries, Bookings, Demand Score).
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="location_demand_monthly")
    location = models.CharField(max_length=200)
    city = models.CharField(max_length=100, blank=True)

    year = models.IntegerField()
    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])

    enquiries = models.IntegerField(default=0)
    bookings = models.IntegerField(default=0)
    demand_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        unique_together = [("organization", "location", "year", "month")]
        ordering = ["-year", "-month", "-demand_score"]


# =============================================================================
# INVENTORY ANALYSIS (screens: price band analysis, inventory aging)
# =============================================================================

class PriceBandAnalysis(TimeStampedModel):
    """
    Price band table (per project).
    """
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="price_band_analysis")

    price_range_label = models.CharField(max_length=80)  # e.g. "₹80L - ₹1Cr"
    unsold_units = models.IntegerField(default=0)

    class DemandLevel(models.TextChoices):
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    demand_level = models.CharField(max_length=20, choices=DemandLevel.choices, default=DemandLevel.MEDIUM)

    class Action(models.TextChoices):
        MAINTAIN = "maintain", "Maintain Pricing"
        REVISE = "revise", "Consider Price Revision"
        PROMO = "promo", "Run Promotions"

    action = models.CharField(max_length=20, choices=Action.choices, default=Action.MAINTAIN)

    year = models.IntegerField()
    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])

    class Meta:
        unique_together = [("project", "price_range_label", "year", "month")]
        ordering = ["-year", "-month", "price_range_label"]


class InventoryAgingMonthly(TimeStampedModel):
    """
    Inventory aging bar chart.
    """
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="inventory_aging_monthly")
    year = models.IntegerField()
    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])

    unsold_units = models.IntegerField(default=0)
    avg_unsold_age_days = models.IntegerField(default=0)

    class Meta:
        unique_together = [("project", "year", "month")]
        ordering = ["-year", "-month"]


# =============================================================================
# LEGAL & COMPLIANCE
# =============================================================================

class LegalCase(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="legal_cases")

    case_id = models.CharField(max_length=60)
    case_type = models.CharField(max_length=60)  # keep string, can be upgraded to lookup later
    description = models.TextField()

    severity = models.CharField(max_length=20)   # critical/high/medium/low
    status = models.CharField(max_length=30)     # open/pending/closed/etc

    filing_date = models.DateField()

    class Meta:
        unique_together = [("project", "case_id")]
        ordering = ["-filing_date"]
        indexes = [
            models.Index(fields=["project", "status"]),
        ]


class ComplianceItem(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="compliance_items")

    item_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    class Status(models.TextChoices):
        COMPLIANT = "compliant", "Compliant"
        PENDING = "pending", "Pending"
        NON_COMPLIANT = "non_compliant", "Non-Compliant"

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    due_date = models.DateField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["due_date"]
        indexes = [
            models.Index(fields=["project", "status"]),
        ]


class RERARegistration(TimeStampedModel):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="rera_registration")

    class Status(models.TextChoices):
        COMPLIANT = "compliant", "Compliant"
        PENDING = "pending", "Pending"
        EXPIRED = "expired", "Expired"

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    registration_number = models.CharField(max_length=120)
    valid_until = models.DateField()

    class Meta:
        ordering = ["valid_until"]


# =============================================================================
# BOARD & INVESTOR
# =============================================================================

class QuarterlyPerformance(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="quarterly_performance")

    year = models.IntegerField()
    quarter = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)])

    target = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    booked = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    realized = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        unique_together = [("organization", "year", "quarter")]
        ordering = ["-year", "-quarter"]


class RevenueTimeline(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="revenue_timeline")

    year = models.IntegerField()
    projected = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    realized = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        unique_together = [("organization", "year")]
        ordering = ["year"]


class RiskAssessment(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="risk_assessments")
    risk_type = models.CharField(max_length=60)     # construction/market/regulatory/financial
    impact_level = models.CharField(max_length=30)  # low/medium/high
    description = models.TextField(blank=True)
    assessed_on = models.DateField()

    class Meta:
        ordering = ["-assessed_on"]


class KeyHighlight(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="key_highlights")
    title = models.CharField(max_length=200)
    description = models.TextField()
    highlight_date = models.DateField()

    class Meta:
        ordering = ["-highlight_date"]


# =============================================================================
# PEOPLE & PERFORMANCE
# =============================================================================

class KRA(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="kras")
    name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = [("organization", "name")]
        ordering = ["name"]


class EmployeeKRA(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="employee_kras")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="kras")
    kra = models.ForeignKey(KRA, on_delete=models.CASCADE, related_name="employee_kras")

    year = models.IntegerField()
    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])

    target = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    achieved = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    achievement_percentage = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        unique_together = [("employee", "kra", "year", "month")]
        ordering = ["-year", "-month"]


class EmployeeStatusEvent(TimeStampedModel):
    """
    Attrition tracking (joined/resigned/terminated/rejoined).
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="employee_status_events")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="status_events")

    event = models.CharField(max_length=30)
    effective_date = models.DateField()
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-effective_date"]


class HiringGap(TimeStampedModel):
    """
    Hiring gaps impacting delivery (screen table).
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="hiring_gaps")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="hiring_gaps")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="hiring_gaps")

    role = models.CharField(max_length=100)
    required = models.IntegerField(default=0)
    current = models.IntegerField(default=0)
    gap = models.IntegerField(default=0)
    impact = models.CharField(max_length=20)  # critical/high/medium/low

    class Meta:
        indexes = [
            models.Index(fields=["organization", "impact"]),
            models.Index(fields=["project"]),
        ]
        ordering = ["-gap"]


class CriticalAttention(TimeStampedModel):
    """
    Critical attention tracking (employee, reason, action).
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="critical_attention")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="critical_attention")

    task_area = models.CharField(max_length=50)  # sales/construction/finance etc
    reason = models.TextField()
    action = models.CharField(max_length=200)
    is_resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]


# =============================================================================
# ALERTS / NOTIFICATIONS (EXEC OVERVIEW counters etc)
# =============================================================================

class Alert(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="alerts")

    class AlertType(models.TextChoices):
        COMPLIANCE = "compliance", "Compliance"
        FINANCIAL = "financial", "Financial"
        CONSTRUCTION = "construction", "Construction"
        CUSTOMER = "customer", "Customer"
        LEGAL = "legal", "Legal"

    class Priority(models.TextChoices):
        CRITICAL = "critical", "Critical"
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    alert_type = models.CharField(max_length=20, choices=AlertType.choices)
    priority = models.CharField(max_length=20, choices=Priority.choices)

    title = models.CharField(max_length=200)
    message = models.TextField()

    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    related_project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="alerts")

    class Meta:
        indexes = [
            models.Index(fields=["organization", "is_resolved"]),
            models.Index(fields=["priority"]),
        ]
        ordering = ["-created_at"]


# =============================================================================
# SNAPSHOTS (FAST DASHBOARD LOAD) - DAILY + MONTHLY
# =============================================================================

class ProjectKPI_Daily(TimeStampedModel):
    """
    Fast cards + project comparison + inventory summary.
    Populate daily via cron/celery.
    """
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="kpis_daily")
    date = models.DateField()

    total_units = models.IntegerField(default=0)
    sold_units = models.IntegerField(default=0)
    booked_units = models.IntegerField(default=0)
    blocked_units = models.IntegerField(default=0)
    unsold_units = models.IntegerField(default=0)

    revenue_booked = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    revenue_collected = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    outstanding = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    construction_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    satisfaction_avg = models.DecimalField(max_digits=4, decimal_places=2, default=0)

    budget = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cost_incurred = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    margin_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        unique_together = [("project", "date")]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["project", "date"]),
        ]
        ordering = ["-date"]


class OrgKPI_Daily(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="org_kpis_daily")
    date = models.DateField()

    total_units = models.IntegerField(default=0)
    revenue_booked = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    revenue_collected = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    outstanding = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    avg_construction = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    satisfaction_avg = models.DecimalField(max_digits=4, decimal_places=2, default=0)

    ring_alerts = models.IntegerField(default=0)
    stalled_projects = models.IntegerField(default=0)
    at_risk_projects = models.IntegerField(default=0)
    active_complaints = models.IntegerField(default=0)
    compliance_alerts = models.IntegerField(default=0)

    net_cashflow_mtd = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        unique_together = [("organization", "date")]
        indexes = [
            models.Index(fields=["organization", "date"]),
        ]
        ordering = ["-date"]


class OrgMonthlySnapshot(TimeStampedModel):
    """
    Revenue trend line, cash position bars, satisfaction trend etc.
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="monthly_snapshots")
    year = models.IntegerField()
    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])

    total_units = models.IntegerField(default=0)
    revenue_booked = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    revenue_collected = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    outstanding = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    cash_inflow = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cash_outflow = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    net_cashflow = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    avg_satisfaction = models.DecimalField(max_digits=4, decimal_places=2, default=0)

    bookings_count = models.IntegerField(default=0)
    avg_ticket_size = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        unique_together = [("organization", "year", "month")]
        ordering = ["-year", "-month"]


class ProjectMonthlySnapshot(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="monthly_snapshots")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="project_monthly_snapshots")

    year = models.IntegerField()
    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])

    units_sold = models.IntegerField(default=0)
    units_available = models.IntegerField(default=0)
    construction_percentage = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    revenue_booked = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    revenue_collected = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    budget = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cost_incurred = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    margin_percentage = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    unsold_units = models.IntegerField(default=0)
    avg_unsold_age = models.IntegerField(default=0)

    class Meta:
        unique_together = [("project", "year", "month")]
        ordering = ["-year", "-month"]
        indexes = [
            models.Index(fields=["organization", "year", "month"]),
        ]
