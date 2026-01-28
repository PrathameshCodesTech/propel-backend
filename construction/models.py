from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel, Organization, MilestonePhase
from projects.models import Project


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
        indexes = [models.Index(fields=["project", "status"])]


class DailyProgress(TimeStampedModel):
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
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="delay_predictions")
    model_version = models.CharField(max_length=50, default="v1.0")

    predicted_delay_days = models.IntegerField(default=0)
    model_confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0)

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
