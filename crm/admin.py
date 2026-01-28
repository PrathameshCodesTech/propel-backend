from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import (
    Customer, CustomerStageEvent, Booking, CustomerPayment,
    CustomerSatisfactionSurvey, Complaint
)


@admin.register(Customer)
class CustomerAdmin(ModelAdmin):
    list_display = ['customer_code', 'name', 'email', 'phone', 'organization', 'project', 
                    'status', 'channel', 'assigned_to', 'walk_in_date', 'created_at']
    list_filter = ['status', 'organization', 'channel', 'created_at']
    search_fields = ['customer_code', 'name', 'email', 'phone', 'project__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['project', 'unit', 'channel', 'assigned_to', 'cancellation_reason']
    date_hierarchy = 'walk_in_date'


@admin.register(CustomerStageEvent)
class CustomerStageEventAdmin(ModelAdmin):
    list_display = ['customer', 'stage', 'organization', 'happened_at', 'created_at']
    list_filter = ['stage', 'organization', 'happened_at']
    search_fields = ['customer__name', 'customer__customer_code', 'notes']
    readonly_fields = ['created_at', 'updated_at', 'happened_at']
    date_hierarchy = 'happened_at'


@admin.register(Booking)
class BookingAdmin(ModelAdmin):
    list_display = ['customer', 'project', 'unit', 'sales_executive', 'booking_value', 
                    'booking_date', 'status', 'created_at']
    list_filter = ['status', 'project', 'sales_executive', 'booking_date']
    search_fields = ['customer__name', 'customer__customer_code', 'project__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['customer', 'project', 'unit', 'sales_executive']
    date_hierarchy = 'booking_date'


@admin.register(CustomerPayment)
class CustomerPaymentAdmin(ModelAdmin):
    list_display = ['booking', 'amount', 'paid_on', 'reference', 'created_at']
    list_filter = ['paid_on', 'created_at']
    search_fields = ['booking__customer__name', 'reference']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'paid_on'


@admin.register(CustomerSatisfactionSurvey)
class CustomerSatisfactionSurveyAdmin(ModelAdmin):
    list_display = ['customer', 'project', 'organization', 'score', 'surveyed_at', 'created_at']
    list_filter = ['organization', 'project', 'surveyed_at']
    search_fields = ['customer__name', 'customer__customer_code', 'feedback']
    readonly_fields = ['created_at', 'updated_at', 'surveyed_at']
    date_hierarchy = 'surveyed_at'


@admin.register(Complaint)
class ComplaintAdmin(ModelAdmin):
    list_display = ['customer', 'project', 'category', 'status', 'assigned_to', 
                    'risk_score', 'created_at', 'resolved_at']
    list_filter = ['status', 'category', 'project', 'created_at']
    search_fields = ['customer__name', 'customer__customer_code', 'description']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['customer', 'project', 'category', 'assigned_to']
    date_hierarchy = 'created_at'
