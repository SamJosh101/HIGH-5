from django.urls import path

from . import views

app_name = "transport"

urlpatterns = [
    path("manage/", views.manage_index, name="manage"),
    path("manage/routes/", views.route_list, name="route_list"),
    path("manage/routes/add/", views.route_create, name="route_create"),
    path("manage/routes/<int:pk>/edit/", views.route_edit, name="route_edit"),
    path("manage/routes/<int:pk>/delete/", views.route_delete, name="route_delete"),
    path("manage/buses/", views.bus_list, name="bus_list"),
    path("manage/buses/add/", views.bus_create, name="bus_create"),
    path("manage/buses/<int:pk>/edit/", views.bus_edit, name="bus_edit"),
    path("manage/buses/<int:pk>/delete/", views.bus_delete, name="bus_delete"),
    path("manage/schedules/", views.schedule_list, name="schedule_list"),
    path("manage/schedules/add/", views.schedule_create, name="schedule_create"),
    path("manage/schedules/<int:pk>/edit/", views.schedule_edit, name="schedule_edit"),
    path("manage/schedules/<int:pk>/passengers/", views.schedule_passengers, name="schedule_passengers"),
    path("manage/schedules/<int:pk>/cancel/", views.schedule_cancel, name="schedule_cancel"),
]
