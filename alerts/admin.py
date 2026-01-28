from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import Alert


@admin.register(Alert)
class AlertAdmin(ModelAdmin):
    list_display = ['title', 'organization', 'alert_type', 'priority', 
                    'is_resolved', 'related_project', 'created_at', 'resolved_at']
    list_filter = ['alert_type', 'priority', 'is_resolved', 'organization', 'created_at']
    search_fields = ['title', 'message', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['organization', 'related_project']
    date_hierarchy = 'created_at'
