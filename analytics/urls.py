from django.urls import path
from .views import ExecutiveOverviewAPIView, ExecutiveProjectDetailAPIView
from .comparison_views import ProjectComparisonAPIView
from .sales_views import SalesPerformanceAPIView
from .inventory_views import InventoryAPIView
from .construction_views import ConstructionTrackerAPIView
from .finance_views import FinanceCashflowAPIView
from .customer_views import CustomerExperienceAPIView
from .people_views import PeoplePerformanceAPIView
from .legal_views import LegalComplianceAPIView
from .investor_views import InvestorDashboardAPIView
from .marketing_views import MarketingROIAPIView

urlpatterns = [
    path("executive-overview/", ExecutiveOverviewAPIView.as_view(), name="executive-overview"),
    path("executive-overview/projects/<int:project_id>/", ExecutiveProjectDetailAPIView.as_view(), name="executive-project-detail"),
    path("project-comparison/", ProjectComparisonAPIView.as_view(), name="project-comparison"),
    path("sales-performance/", SalesPerformanceAPIView.as_view(), name="sales-performance"),
    path("inventory/", InventoryAPIView.as_view(), name="inventory"),
    path("construction/", ConstructionTrackerAPIView.as_view(), name="construction"),
    path("finance/", FinanceCashflowAPIView.as_view(), name="finance"),
    path("customer-experience/", CustomerExperienceAPIView.as_view(), name="customer-experience"),
    path("people-performance/", PeoplePerformanceAPIView.as_view(), name="people-performance"),
    path("legal-compliance/", LegalComplianceAPIView.as_view(), name="legal-compliance"),
    path("investor-dashboard/", InvestorDashboardAPIView.as_view(), name="investor-dashboard"),
    path("marketing-roi/", MarketingROIAPIView.as_view(), name="marketing-roi"),
]
