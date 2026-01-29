"""
Management command to populate FieldCatalog from Django models.
Scans all models and creates FieldCatalog entries for queryable fields.
"""
from django.core.management.base import BaseCommand
from django.db import models
from django.apps import apps
from analytics.models import FieldCatalog

# Models to scan (dataset_name: model_class)
DATASET_MODELS = {
    "marketing_campaign": ("analytics", "MarketingCampaign"),
    "location_demand": ("analytics", "LocationDemandMonthly"),
    "org_kpi": ("analytics", "OrgKPI_Daily"),
    "project_kpi": ("analytics", "ProjectKPI_Daily"),
    "org_snapshot": ("analytics", "OrgMonthlySnapshot"),
    "project_snapshot": ("analytics", "ProjectMonthlySnapshot"),
    "customer": ("crm", "Customer"),
    "booking": ("crm", "Booking"),
    "project": ("projects", "Project"),
    "unit": ("projects", "Unit"),
    "employee": ("core", "Employee"),
}


def get_field_type(field):
    """Infer data type from Django field."""
    if isinstance(field, (models.DecimalField, models.FloatField)):
        return "decimal"
    elif isinstance(field, (models.IntegerField, models.BigIntegerField, models.PositiveIntegerField)):
        return "integer"
    elif isinstance(field, (models.DateField, models.DateTimeField)):
        return "date"
    elif isinstance(field, models.BooleanField):
        return "boolean"
    elif isinstance(field, models.ForeignKey):
        return "foreign_key"
    else:
        return "string"


def get_field_label(field):
    """Get human-readable label for field."""
    if hasattr(field, "verbose_name") and field.verbose_name:
        return field.verbose_name
    return field.name.replace("_", " ").title()


class Command(BaseCommand):
    help = "Seed FieldCatalog from Django models"

    def add_arguments(self, parser):
        parser.add_argument(
            "--truncate",
            action="store_true",
            help="Delete all existing FieldCatalog entries before seeding",
        )

    def handle(self, *args, **options):
        if options["truncate"]:
            FieldCatalog.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Truncated FieldCatalog"))

        total_count = 0

        for dataset_name, (app_label, model_name) in DATASET_MODELS.items():
            try:
                model = apps.get_model(app_label, model_name)
            except LookupError:
                self.stdout.write(self.style.WARNING(f"Model {app_label}.{model_name} not found, skipping"))
                continue

            self.stdout.write(f"Processing {dataset_name} ({model.__name__})...")

            # Process direct fields
            for field in model._meta.get_fields():
                if isinstance(field, models.ManyToManyField):
                    continue
                
                if isinstance(field, models.ForeignKey):
                    # Add FK field itself (for filtering)
                    key = f"{dataset_name}.{field.name}"
                    label = get_field_label(field)
                    data_type = "foreign_key"
                    orm_path = field.name
                    
                    obj, created = FieldCatalog.objects.update_or_create(
                        key=key,
                        defaults={
                            "label": label,
                            "dataset": dataset_name,
                            "orm_path": orm_path,
                            "data_type": data_type,
                            "is_enabled": True,
                        }
                    )
                    total_count += 1
                    
                    # Add FK relation fields (e.g., channel__label)
                    try:
                        related_model = field.related_model
                        for related_field in related_model._meta.get_fields():
                            if isinstance(related_field, (models.CharField, models.TextField)):
                                rel_key = f"{dataset_name}.{field.name}__{related_field.name}"
                                rel_label = f"{label} - {get_field_label(related_field)}"
                                rel_orm_path = f"{field.name}__{related_field.name}"
                                
                                FieldCatalog.objects.update_or_create(
                                    key=rel_key,
                                    defaults={
                                        "label": rel_label,
                                        "dataset": dataset_name,
                                        "orm_path": rel_orm_path,
                                        "data_type": "string",
                                        "is_enabled": True,
                                    }
                                )
                                total_count += 1
                    except:
                        pass
                else:
                    # Regular field
                    key = f"{dataset_name}.{field.name}"
                    label = get_field_label(field)
                    data_type = get_field_type(field)
                    orm_path = field.name
                    
                    obj, created = FieldCatalog.objects.update_or_create(
                        key=key,
                        defaults={
                            "label": label,
                            "dataset": dataset_name,
                            "orm_path": orm_path,
                            "data_type": data_type,
                            "is_enabled": True,
                        }
                    )
                    total_count += 1

        self.stdout.write(self.style.SUCCESS(f"FieldCatalog seeded: {total_count} fields created/updated"))
