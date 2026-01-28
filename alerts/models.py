from django.db import models

from core.models import TimeStampedModel, Organization
from projects.models import Project


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

    related_project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="alerts"
    )

    class Meta:
        indexes = [
            models.Index(fields=["organization", "is_resolved"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["alert_type"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organization.code} - {self.alert_type} - {self.title}"
