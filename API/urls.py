"""
URL configuration for API project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Swagger Schema View
schema_view = get_schema_view(
    openapi.Info(
        title="WeDesignz API",
        default_version='v1',
        description="API documentation for WeDesignz platform",
        terms_of_service="https://www.wedesignz.com/terms/",
        contact=openapi.Contact(email="contact@wedesignz.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API Endpoints
    path('api/auth/', include('Authentication.urls')),
    path('api/coreadmin/', include('CoreAdmin.urls')),
    path('api/admin-analytics/', include('AdminAnalytics.urls')),
    path('api/catalog/', include('Catalog.urls')),
    path('api/orders/', include('Orders.urls')),
    path('api/plans/', include('Plans.urls')),
    path('api/profiles/', include('Profiles.urls')),
    path('api/razorpay/', include('Razorpay.urls')),
    path('api/wallet/', include('Wallet.urls')),
    path('api/coupons/', include('Coupons.urls')),
    path('api/custom-requests/', include('CustomRequests.urls')),
    path('api/feedback/', include('Feedback.urls')),
    path('api/media/', include('MediaFiles.urls')),
    path('api/accounts/', include('Accounts.urls')),
    path('api/pinterest/', include('common.urls')),  # Pinterest integration endpoints
    path('api/common/', include('common.urls')),  # Common endpoints (Instagram, etc.)
    
    # Notifications endpoints (separate from feedback)
    path('api/notifications/', include('Feedback.urls')),  # Reuse Feedback views for notifications
    
    # Swagger Documentation URLs
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    re_path(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    re_path(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

# Serve media and static files in development
if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    # Only mount local media serving routes when MEDIA_URL is a local path.
    if settings.MEDIA_URL.startswith('/'):
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()
