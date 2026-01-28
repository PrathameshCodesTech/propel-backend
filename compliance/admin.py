from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import LegalCase, ComplianceItem, RERARegistration


@admin.register(LegalCase)
class LegalCaseAdmin(ModelAdmin):
    list_display = ['case_id', 'project', 'case_type', 'severity', 'status', 
                    'filing_date', 'created_at']
    list_filter = ['severity', 'status', 'case_type', 'project', 'filing_date']
    search_fields = ['case_id', 'case_type', 'description', 'project__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['project']
    date_hierarchy = 'filing_date'


@admin.register(ComplianceItem)
class ComplianceItemAdmin(ModelAdmin):
    list_display = ['item_name', 'project', 'status', 'due_date', 'completed_date', 'created_at']
    list_filter = ['status', 'project', 'due_date']
    search_fields = ['item_name', 'description', 'project__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['project']
    date_hierarchy = 'due_date'


@admin.register(RERARegistration)
class RERARegistrationAdmin(ModelAdmin):
    list_display = ['project', 'registration_number', 'status', 'valid_until', 'created_at']
    list_filter = ['status', 'valid_until']
    search_fields = ['registration_number', 'project__name', 'project__project_code']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['project']
    date_hierarchy = 'valid_until'
