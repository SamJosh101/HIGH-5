from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.admin_home, name="home"),
    # Planned (Daniel): bookings/, revenue/, reports/
]
