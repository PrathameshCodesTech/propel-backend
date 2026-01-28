from django.db import models
from django.conf import settings


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
