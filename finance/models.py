from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel, Organization
from projects.models import Project


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
