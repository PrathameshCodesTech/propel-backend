from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import Vendor, VendorBill, VendorPayment, CashFlowEntry, CashFlowForecast


@admin.register(Vendor)
class VendorAdmin(ModelAdmin):
    list_display = ['name', 'organization', 'created_at']
    list_filter = ['organization', 'created_at']
    search_fields = ['name', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(VendorBill)
class VendorBillAdmin(ModelAdmin):
    list_display = ['bill_no', 'vendor', 'project', 'bill_date', 'due_date', 
                    'amount', 'status', 'created_at']
    list_filter = ['status', 'vendor', 'project', 'bill_date']
    search_fields = ['bill_no', 'vendor__name', 'project__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['vendor', 'project']
    date_hierarchy = 'bill_date'


@admin.register(VendorPayment)
class VendorPaymentAdmin(ModelAdmin):
    list_display = ['bill', 'amount', 'paid_on', 'reference', 'created_at']
    list_filter = ['paid_on', 'created_at']
    search_fields = ['bill__bill_no', 'reference']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['bill']
    date_hierarchy = 'paid_on'


@admin.register(CashFlowEntry)
class CashFlowEntryAdmin(ModelAdmin):
    list_display = ['organization', 'project', 'flow_type', 'amount', 'date', 
                    'category', 'created_at']
    list_filter = ['flow_type', 'organization', 'project', 'date', 'category']
    search_fields = ['description', 'category', 'project__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['organization', 'project']
    date_hierarchy = 'date'


@admin.register(CashFlowForecast)
class CashFlowForecastAdmin(ModelAdmin):
    list_display = ['organization', 'year', 'month', 'projected_inflow', 
                    'projected_outflow', 'net_cashflow', 'cumulative', 'confidence', 'created_at']
    list_filter = ['confidence', 'organization', 'year', 'month']
    search_fields = ['organization__name', 'key_risks']
    readonly_fields = ['created_at', 'updated_at']
