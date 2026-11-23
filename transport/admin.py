from django.contrib import admin

from django.contrib import admin

from .models import Bus, Route, Schedule


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("origin", "destination", "distance_km", "duration_estimate", "is_active")
    list_filter = ("is_active",)
    search_fields = ("origin", "destination")


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ("name_or_plate", "bus_type", "total_seats", "status", "is_active")
    list_filter = ("bus_type", "status", "is_active")
    search_fields = ("name_or_plate",)


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ("route", "bus", "departure_date", "departure_time", "arrival_time", "fare", "status")
    list_filter = ("status", "departure_date")
