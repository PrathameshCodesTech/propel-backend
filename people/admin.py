from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import KRA, EmployeeKRA, EmployeeStatusEvent, HiringGap, CriticalAttention


@admin.register(KRA)
class KRAAdmin(ModelAdmin):
    list_display = ['name', 'organization', 'department', 'created_at']
    list_filter = ['organization', 'department', 'created_at']
    search_fields = ['name', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['department']


@admin.register(EmployeeKRA)
class EmployeeKRAAdmin(ModelAdmin):
    list_display = ['employee', 'kra', 'organization', 'year', 'month', 
                    'target', 'achieved', 'achievement_percentage', 'created_at']
    list_filter = ['organization', 'kra', 'year', 'month']
    search_fields = ['employee__user__username', 'kra__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['employee', 'kra']


@admin.register(EmployeeStatusEvent)
class EmployeeStatusEventAdmin(ModelAdmin):
    list_display = ['employee', 'organization', 'event', 'effective_date', 'created_at']
    list_filter = ['event', 'organization', 'effective_date']
    search_fields = ['employee__user__username', 'reason']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['employee']
    date_hierarchy = 'effective_date'


@admin.register(HiringGap)
class HiringGapAdmin(ModelAdmin):
    list_display = ['organization', 'project', 'department', 'role', 'required', 
                    'current', 'gap', 'impact', 'created_at']
    list_filter = ['impact', 'organization', 'project', 'department']
    search_fields = ['role', 'project__name', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['organization', 'project', 'department']


@admin.register(CriticalAttention)
class CriticalAttentionAdmin(ModelAdmin):
    list_display = ['employee', 'organization', 'task_area', 'is_resolved', 'created_at']
    list_filter = ['is_resolved', 'task_area', 'organization', 'created_at']
    search_fields = ['employee__user__username', 'reason', 'action']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['employee']
