from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel, Organization, LeadChannel
from projects.models import Project


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


class PriceBandAnalysis(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="price_band_analysis")

    price_range_label = models.CharField(max_length=80)
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
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="inventory_aging_monthly")
    year = models.IntegerField()
    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])

    unsold_units = models.IntegerField(default=0)
    avg_unsold_age_days = models.IntegerField(default=0)

    class Meta:
        unique_together = [("project", "year", "month")]
        ordering = ["-year", "-month"]


class ProjectKPI_Daily(TimeStampedModel):
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
        indexes = [models.Index(fields=["organization", "date"])]
        ordering = ["-date"]


class OrgMonthlySnapshot(TimeStampedModel):
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
        indexes = [models.Index(fields=["organization", "year", "month"])]


class FieldCatalog(TimeStampedModel):
    """
    Semantic allowlist for AI analytics queries.
    Maps natural language field names to Django ORM paths.
    Auto-populated from models via seed_field_catalog management command.
    """
    key = models.CharField(max_length=200, unique=True)  # e.g. "marketing_campaign.spend"
    label = models.CharField(max_length=200)  # e.g. "Marketing Spend"
    dataset = models.CharField(max_length=100)  # e.g. "marketing_campaign"
    orm_path = models.CharField(max_length=300)  # e.g. "spend" or "channel__label"
    data_type = models.CharField(max_length=50)  # "decimal", "integer", "string", "date", "boolean"
    synonyms = models.TextField(blank=True, help_text="Comma-separated synonyms for natural language matching")
    is_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["dataset", "label"]
        indexes = [
            models.Index(fields=["dataset", "is_enabled"]),
            models.Index(fields=["is_enabled"]),
        ]

    def __str__(self):
        return f"{self.dataset}.{self.label}"
