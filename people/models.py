from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from core.models import TimeStampedModel, Organization, Department, Employee
from projects.models import Project


class KRA(TimeStampedModel):
    """
    Key Result Area master (per organization).
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="kras")
    name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = [("organization", "name")]
        ordering = ["name"]

    def __str__(self):
        return f"{self.organization.code} - {self.name}"


class EmployeeKRA(TimeStampedModel):
    """
    Monthly KRA target vs achieved per employee.
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="employee_kras")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="kras")
    kra = models.ForeignKey(KRA, on_delete=models.CASCADE, related_name="employee_kras")

    year = models.IntegerField()
    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])

    target = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    achieved = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    achievement_percentage = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    class Meta:
        unique_together = [("employee", "kra", "year", "month")]
        indexes = [
            models.Index(fields=["organization", "year", "month"]),
            models.Index(fields=["employee", "year", "month"]),
        ]
        ordering = ["-year", "-month"]

    def __str__(self):
        return f"{self.employee} - {self.kra.name} ({self.month}/{self.year})"


class EmployeeStatusEvent(TimeStampedModel):
    """
    Attrition tracking (joined/resigned/terminated/rejoined etc.)
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="employee_status_events")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="status_events")

    event = models.CharField(max_length=30)  # joined/resigned/terminated/rejoined
    effective_date = models.DateField()
    reason = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "effective_date"]),
            models.Index(fields=["employee", "effective_date"]),
        ]
        ordering = ["-effective_date"]

    def __str__(self):
        return f"{self.employee} - {self.event} ({self.effective_date})"


class HiringGap(TimeStampedModel):
    """
    Hiring gaps impacting delivery (screen table).
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="hiring_gaps")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="hiring_gaps")
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="hiring_gaps"
    )

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

    def __str__(self):
        return f"{self.organization.code} - {self.role} gap {self.gap}"


class CriticalAttention(TimeStampedModel):
    """
    Critical attention tracking (employee, reason, action).
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="critical_attentions")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="critical_attentions")

    task_area = models.CharField(max_length=50)  # sales/construction/finance etc
    reason = models.TextField()
    action = models.CharField(max_length=200)
    is_resolved = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "is_resolved"]),
            models.Index(fields=["task_area"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee} - {self.task_area}"
