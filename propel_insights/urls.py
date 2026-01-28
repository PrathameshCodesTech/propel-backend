"""
URL configuration for propel_insights project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

from core.api_views import MeAPIView, CsrfAPIView, ExcelUploadAPIView
from core.auth_views import LoginAPIView, LogoutAPIView


urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/auth/login/", LoginAPIView.as_view(), name="api-login"),
    path("api/auth/logout/", LogoutAPIView.as_view(), name="api-logout"),
    path("api/csrf/", CsrfAPIView.as_view(), name="api-csrf"),
    path("api/me/", MeAPIView.as_view(), name="api-me"),
    path("api/admin/upload-excel/", ExcelUploadAPIView.as_view(), name="api-upload-excel"),
    path("api/analytics/", include("analytics.urls")),
    path("api/crm/", include("crm.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
