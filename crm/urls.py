from django.urls import path
from .views import CRMCustomersAPIView

urlpatterns = [
    path("customers/", CRMCustomersAPIView.as_view(), name="crm-customers"),
]
