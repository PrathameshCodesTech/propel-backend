"""
Quick script to check if OrgMonthlySnapshot data exists for MICL.
Run: python manage.py shell < check_data.py
"""

from core.models import Organization
from analytics.models import OrgMonthlySnapshot

# Get MICL organization
org = Organization.objects.get(code="MICL")

# Check OrgMonthlySnapshot records
snapshots = OrgMonthlySnapshot.objects.filter(organization=org).order_by("year", "month")

print(f"\n{'='*60}")
print(f"OrgMonthlySnapshot records for {org.code} ({org.name}):")
print(f"{'='*60}")
print(f"Total records: {snapshots.count()}\n")

if snapshots.exists():
    print("Records found:")
    for s in snapshots:
        print(f"  {s.year}-{s.month:02d}: revenue_booked={s.revenue_booked}, revenue_collected={s.revenue_collected}, cash_inflow={s.cash_inflow}, cash_outflow={s.cash_outflow}")
else:
    print("❌ No records found!")

# Check date range filter (same as API uses)
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db.models import Q

def month_range(months: int):
    end = date.today().replace(day=1)
    start = (end - relativedelta(months=months - 1))
    return start, end

start, end = month_range(12)
print(f"\n{'='*60}")
print(f"API Date Range Filter (last 12 months):")
print(f"  Start: {start} (year={start.year}, month={start.month})")
print(f"  End: {end} (year={end.year}, month={end.month})")
print(f"{'='*60}\n")

filtered = (
    OrgMonthlySnapshot.objects
    .filter(organization=org)
    .filter(Q(year__gt=start.year) | Q(year=start.year, month__gte=start.month))
    .filter(Q(year__lt=end.year) | Q(year=end.year, month__lte=end.month))
    .order_by("year", "month")
)

print(f"Records matching filter: {filtered.count()}\n")
if filtered.exists():
    print("Filtered records:")
    for s in filtered:
        print(f"  {s.year}-{s.month:02d}: revenue_booked={s.revenue_booked}, cash_inflow={s.cash_inflow}")
