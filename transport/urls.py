from django.urls import path

from . import views

app_name = "transport"

urlpatterns = [
    path("manage/", views.manage_index, name="manage"),
    # Planned (Daniel): manage/routes/, manage/buses/, manage/schedules/ (+ create/edit/deactivate)
]
