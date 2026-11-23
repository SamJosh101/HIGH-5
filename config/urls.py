"""
HIGH 5 root URL configuration.

Each app owns its own urls.py and URL namespace:
    accounts:   /accounts/...   (Sam)    – auth, profile
    bookings:   /bookings/...   (Raheem) – search, seats, bookings, passenger dashboard
    transport:  /transport/...  (Daniel) – routes, buses, schedules, fares (admin only)
    dashboard:  /dashboard/...  (Daniel) – administrator dashboard and reports

Always link with {% url 'namespace:name' %} in templates, never hardcoded paths.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from config.views import HomeView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("accounts/", include("accounts.urls")),
    path("bookings/", include("bookings.urls")),
    path("transport/", include("transport.urls")),
    path("dashboard/", include("dashboard.urls")),
    # Django's built-in admin site, for superusers/maintenance only.
    # The HIGH 5 administrator interface is /dashboard/.
    path("django-admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "HIGH 5 – System Administration"
admin.site.site_title = "HIGH 5 Admin"