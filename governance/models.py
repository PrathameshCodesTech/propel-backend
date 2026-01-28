from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from core.models import TimeStampedModel, Organization


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

    def __str__(self):
        return f"{self.organization.code} Q{self.quarter}/{self.year}"


class RevenueTimeline(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="revenue_timeline")

    year = models.IntegerField()
    projected = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    realized = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        unique_together = [("organization", "year")]
        ordering = ["year"]

    def __str__(self):
        return f"{self.organization.code} - {self.year}"


class RiskAssessment(TimeStampedModel):
    """
    Board / Investor risk view
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="risk_assessments")

    risk_type = models.CharField(max_length=60)     # construction/market/regulatory/financial
    impact_level = models.CharField(max_length=30)  # low/medium/high
    description = models.TextField(blank=True)

    assessed_on = models.DateField()

    class Meta:
        indexes = [
            models.Index(fields=["organization", "assessed_on"]),
            models.Index(fields=["risk_type"]),
        ]
        ordering = ["-assessed_on"]

    def __str__(self):
        return f"{self.organization.code} - {self.risk_type} ({self.assessed_on})"


class KeyHighlight(TimeStampedModel):
    """
    Key highlights for board deck / investor updates
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="key_highlights")

    title = models.CharField(max_length=200)
    description = models.TextField()

    highlight_date = models.DateField()

    class Meta:
        indexes = [
            models.Index(fields=["organization", "highlight_date"]),
        ]
        ordering = ["-highlight_date"]

    def __str__(self):
        return f"{self.organization.code} - {self.title}"
