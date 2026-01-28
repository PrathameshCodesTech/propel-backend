from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import QuarterlyPerformance, RevenueTimeline, RiskAssessment, KeyHighlight


@admin.register(QuarterlyPerformance)
class QuarterlyPerformanceAdmin(ModelAdmin):
    list_display = ['organization', 'year', 'quarter', 'target', 'booked', 
                    'realized', 'created_at']
    list_filter = ['organization', 'year', 'quarter']
    search_fields = ['organization__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(RevenueTimeline)
class RevenueTimelineAdmin(ModelAdmin):
    list_display = ['organization', 'year', 'projected', 'realized', 'created_at']
    list_filter = ['organization', 'year']
    search_fields = ['organization__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(RiskAssessment)
class RiskAssessmentAdmin(ModelAdmin):
    list_display = ['organization', 'risk_type', 'impact_level', 'assessed_on', 'created_at']
    list_filter = ['risk_type', 'impact_level', 'organization', 'assessed_on']
    search_fields = ['risk_type', 'description', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'assessed_on'


@admin.register(KeyHighlight)
class KeyHighlightAdmin(ModelAdmin):
    list_display = ['organization', 'title', 'highlight_date', 'created_at']
    list_filter = ['organization', 'highlight_date']
    search_fields = ['title', 'description', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'highlight_date'
