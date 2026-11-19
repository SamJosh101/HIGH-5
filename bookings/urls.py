from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    path("search/", views.trip_search, name="search"),
    path("dashboard/", views.passenger_dashboard, name="dashboard"),
    # Planned (Raheem): schedule/<int:schedule_id>/seats/, book/, my/, <str:booking_ref>/, <str:booking_ref>/cancel/
]
