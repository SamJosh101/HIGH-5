from django import forms

from accounts.forms import BootstrapFormMixin
from .models import Bus, Route, Schedule


class RouteForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Route
        fields = ("origin", "destination", "distance_km", "duration_estimate", "description", "is_active")


class BusForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Bus
        fields = ("name_or_plate", "bus_type", "total_seats", "status", "is_active")


class ScheduleForm(BootstrapFormMixin, forms.ModelForm):
    departure_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    departure_time = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))

    class Meta:
        model = Schedule
        fields = ("route", "bus", "departure_date", "departure_time", "fare", "status")
