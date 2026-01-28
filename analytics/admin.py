from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import (
    MarketingCampaign, LocationDemandMonthly, PriceBandAnalysis,
    InventoryAgingMonthly, ProjectKPI_Daily, OrgKPI_Daily,
    OrgMonthlySnapshot, ProjectMonthlySnapshot
)


@admin.register(MarketingCampaign)
class MarketingCampaignAdmin(ModelAdmin):
    list_display = ['name', 'campaign_code', 'organization', 'channel', 'start_date', 
                    'end_date', 'spend', 'leads', 'bookings', 'roi', 'status', 'created_at']
    list_filter = ['status', 'organization', 'channel', 'start_date']
    search_fields = ['name', 'campaign_code', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'start_date'


@admin.register(LocationDemandMonthly)
class LocationDemandMonthlyAdmin(ModelAdmin):
    list_display = ['location', 'city', 'organization', 'year', 'month', 
                    'enquiries', 'bookings', 'demand_score', 'created_at']
    list_filter = ['organization', 'city', 'year', 'month']
    search_fields = ['location', 'city', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PriceBandAnalysis)
class PriceBandAnalysisAdmin(ModelAdmin):
    list_display = ['project', 'price_range_label', 'unsold_units', 'demand_level', 
                    'action', 'year', 'month', 'created_at']
    list_filter = ['demand_level', 'action', 'project', 'year', 'month']
    search_fields = ['project__name', 'price_range_label']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['project']


@admin.register(InventoryAgingMonthly)
class InventoryAgingMonthlyAdmin(ModelAdmin):
    list_display = ['project', 'year', 'month', 'unsold_units', 
                    'avg_unsold_age_days', 'created_at']
    list_filter = ['project', 'year', 'month']
    search_fields = ['project__name', 'project__project_code']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['project']


@admin.register(ProjectKPI_Daily)
class ProjectKPI_DailyAdmin(ModelAdmin):
    list_display = ['project', 'date', 'total_units', 'sold_units', 'booked_units', 
                    'revenue_booked', 'revenue_collected', 'construction_percent', 'created_at']
    list_filter = ['project', 'date']
    search_fields = ['project__name', 'project__project_code']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['project']
    date_hierarchy = 'date'


@admin.register(OrgKPI_Daily)
class OrgKPI_DailyAdmin(ModelAdmin):
    list_display = ['organization', 'date', 'total_units', 'revenue_booked', 
                    'revenue_collected', 'ring_alerts', 'stalled_projects', 'created_at']
    list_filter = ['organization', 'date']
    search_fields = ['organization__name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'date'


@admin.register(OrgMonthlySnapshot)
class OrgMonthlySnapshotAdmin(ModelAdmin):
    list_display = ['organization', 'year', 'month', 'total_units', 'revenue_booked', 
                    'revenue_collected', 'net_cashflow', 'avg_satisfaction', 'created_at']
    list_filter = ['organization', 'year', 'month']
    search_fields = ['organization__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ProjectMonthlySnapshot)
class ProjectMonthlySnapshotAdmin(ModelAdmin):
    list_display = ['project', 'organization', 'year', 'month', 'units_sold', 
                    'revenue_booked', 'construction_percentage', 'margin_percentage', 'created_at']
    list_filter = ['organization', 'project', 'year', 'month']
    search_fields = ['project__name', 'project__project_code']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['project', 'organization']
