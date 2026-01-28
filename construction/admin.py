from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import Contractor, Milestone, DailyProgress, DelayPenalty, DelayPrediction


@admin.register(Contractor)
class ContractorAdmin(ModelAdmin):
    list_display = ['name', 'organization', 'specialization', 'performance_score', 
                    'is_active', 'created_at']
    list_filter = ['is_active', 'organization', 'created_at']
    search_fields = ['name', 'specialization', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Milestone)
class MilestoneAdmin(ModelAdmin):
    list_display = ['name', 'project', 'phase', 'status', 'completion_percent', 
                    'planned_start', 'planned_end', 'contractor', 'order', 'created_at']
    list_filter = ['status', 'project', 'phase', 'contractor', 'created_at']
    search_fields = ['name', 'project__name', 'project__project_code']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['project', 'phase', 'contractor']
    date_hierarchy = 'planned_start'


@admin.register(DailyProgress)
class DailyProgressAdmin(ModelAdmin):
    list_display = ['project', 'date', 'planned_percent', 'actual_percent', 
                    'workers_present', 'equipment_deployed', 'created_at']
    list_filter = ['project', 'date', 'created_at']
    search_fields = ['project__name', 'project__project_code', 'notes']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['project']
    date_hierarchy = 'date'


@admin.register(DelayPenalty)
class DelayPenaltyAdmin(ModelAdmin):
    list_display = ['project', 'milestone', 'contractor', 'delay_days', 'penalty_amount', 
                    'pending_recovery', 'escalation_level', 'recorded_on', 'created_at']
    list_filter = ['escalation_level', 'project', 'contractor', 'recorded_on']
    search_fields = ['project__name', 'project__project_code']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['project', 'milestone', 'contractor']
    date_hierarchy = 'recorded_on'


@admin.register(DelayPrediction)
class DelayPredictionAdmin(ModelAdmin):
    list_display = ['project', 'prediction_date', 'predicted_delay_days', 'model_confidence', 
                    'model_version', 'created_at']
    list_filter = ['model_version', 'project', 'prediction_date']
    search_fields = ['project__name', 'project__project_code', 'ai_insight_summary']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['project']
    date_hierarchy = 'prediction_date'
