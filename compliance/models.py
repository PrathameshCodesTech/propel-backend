from django.db import models
from core.models import TimeStampedModel
from projects.models import Project


class LegalCase(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="legal_cases")

    case_id = models.CharField(max_length=60)
    case_type = models.CharField(max_length=60)
    description = models.TextField()

    severity = models.CharField(max_length=20)
    status = models.CharField(max_length=30)

    filing_date = models.DateField()

    class Meta:
        unique_together = [("project", "case_id")]
        ordering = ["-filing_date"]
        indexes = [models.Index(fields=["project", "status"])]


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
        indexes = [models.Index(fields=["project", "status"])]


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
