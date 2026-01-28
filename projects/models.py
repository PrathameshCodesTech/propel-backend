from django.db import models
from core.models import TimeStampedModel, Organization, UnitType


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

    budget = models.DecimalField(max_digits=18, decimal_places=2, default=0)

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
        indexes = [models.Index(fields=["project", "status"])]
        ordering = ["project", "tower", "floor", "unit_number"]

    def __str__(self):
        return f"{self.project.name} - {self.unit_number}"
