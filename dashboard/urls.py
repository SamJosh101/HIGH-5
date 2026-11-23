from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.admin_home, name="home"),
    path("bookings/", views.booking_list, name="bookings"),
    path("bookings/<int:pk>/", views.booking_detail, name="booking_detail"),
    path("reports/", views.reports, name="reports"),
]
