from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import Project, Unit


@admin.register(Project)
class ProjectAdmin(ModelAdmin):
    list_display = ['name', 'project_code', 'organization', 'location', 'city', 'status', 
                    'planned_start_date', 'planned_completion_date', 'budget', 'created_at']
    list_filter = ['status', 'organization', 'city', 'created_at']
    search_fields = ['name', 'project_code', 'location', 'city', 'rera_registration_number']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'planned_start_date'


@admin.register(Unit)
class UnitAdmin(ModelAdmin):
    list_display = ['unit_number', 'project', 'unit_type', 'floor', 'tower', 'status', 
                    'base_price', 'final_price', 'carpet_area', 'created_at']
    list_filter = ['status', 'project', 'unit_type', 'tower', 'created_at']
    search_fields = ['unit_number', 'project__name', 'project__project_code']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['project', 'unit_type']
