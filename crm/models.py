from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import (
    TimeStampedModel, Organization, LeadChannel, Employee,
    CancellationReason, ComplaintCategory
)
from projects.models import Project, Unit


class Customer(TimeStampedModel):
    class Status(models.TextChoices):
        WALK_IN = "walk_in", "Walk-in"
        APPLIED = "applied", "Applied"
        BOOKED = "booked", "Booked"
        POSSESSION = "possession", "Possession"
        CANCELLED = "cancelled", "Cancelled"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="customers")

    customer_code = models.CharField(max_length=50)
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
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="customer_stage_events")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="stage_events")

    stage = models.CharField(max_length=30)
    happened_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "stage"]),
            models.Index(fields=["happened_at"]),
        ]
        ordering = ["-happened_at"]


class Booking(TimeStampedModel):
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
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=18, decimal_places=2, validators=[MinValueValidator(0)])
    paid_on = models.DateField()
    reference = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-paid_on"]
        indexes = [models.Index(fields=["paid_on"])]


class CustomerSatisfactionSurvey(TimeStampedModel):
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
