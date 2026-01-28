from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import (
    Organization, Department, Employee,
    UnitType, LeadChannel, CancellationReason,
    ComplaintCategory, MilestonePhase
)


@admin.register(Organization)
class OrganizationAdmin(ModelAdmin):
    list_display = ['name', 'code', 'email', 'phone', 'currency', 'created_at']
    list_filter = ['currency', 'created_at']
    search_fields = ['name', 'code', 'email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Department)
class DepartmentAdmin(ModelAdmin):
    list_display = ['name', 'code', 'organization', 'type', 'created_at']
    list_filter = ['type', 'organization', 'created_at']
    search_fields = ['name', 'code', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Employee)
class EmployeeAdmin(ModelAdmin):
    list_display = ['user', 'employee_code', 'organization', 'department', 'role', 'is_active', 'created_at']
    list_filter = ['role', 'organization', 'department', 'is_active', 'created_at']
    search_fields = ['user__username', 'user__email', 'employee_code', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['user']


@admin.register(UnitType)
class UnitTypeAdmin(ModelAdmin):
    list_display = ['label', 'code', 'organization', 'is_active', 'created_at']
    list_filter = ['is_active', 'organization', 'created_at']
    search_fields = ['label', 'code', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(LeadChannel)
class LeadChannelAdmin(ModelAdmin):
    list_display = ['label', 'code', 'organization', 'is_active', 'created_at']
    list_filter = ['is_active', 'organization', 'created_at']
    search_fields = ['label', 'code', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CancellationReason)
class CancellationReasonAdmin(ModelAdmin):
    list_display = ['label', 'code', 'organization', 'is_active', 'created_at']
    list_filter = ['is_active', 'organization', 'created_at']
    search_fields = ['label', 'code', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ComplaintCategory)
class ComplaintCategoryAdmin(ModelAdmin):
    list_display = ['label', 'code', 'organization', 'is_active', 'created_at']
    list_filter = ['is_active', 'organization', 'created_at']
    search_fields = ['label', 'code', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(MilestonePhase)
class MilestonePhaseAdmin(ModelAdmin):
    list_display = ['name', 'organization', 'order', 'is_active', 'created_at']
    list_filter = ['is_active', 'organization', 'created_at']
    search_fields = ['name', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
