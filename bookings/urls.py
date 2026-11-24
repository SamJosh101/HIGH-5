from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    # Existing website pages
    path("search/", views.trip_search, name="search"),
    path("dashboard/", views.passenger_dashboard, name="dashboard"),

    # Booking API endpoints
    path(
        "api/create/",
        views.BookingCreateAPIView.as_view(),
        name="booking-create",
    ),
    path(
        "api/history/",
        views.BookingHistoryAPIView.as_view(),
        name="booking-history",
    ),
    path(
        "api/<str:booking_ref>/",
        views.BookingDetailAPIView.as_view(),
        name="booking-detail",
    ),
    path(
        "api/<str:booking_ref>/cancel/",
        views.BookingCancelAPIView.as_view(),
        name="booking-cancel",
    ),
    path(
    "ticket/<str:booking_ref>/",
    views.ticket_detail,
    name="ticket-detail",
    ),
]
