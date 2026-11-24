from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.permissions import admin_required
from .forms import BusForm, RouteForm, ScheduleForm
from .models import Bus, Route, Schedule


@admin_required
def manage_index(request):
    today = timezone.localdate()
    context = {
        "route_count": Route.objects.count(),
        "bus_count": Bus.objects.count(),
        "schedule_count": Schedule.objects.count(),
        "today_departures": Schedule.objects.filter(departure_date=today).exclude(status=Schedule.Status.CANCELLED).count(),
        "available_buses": Bus.objects.filter(status=Bus.Status.AVAILABLE, is_active=True).count(),
    }
    return render(request, "transport/manage_index.html", context)


@admin_required
def route_list(request):
    routes = Route.objects.all()
    query = request.GET.get("q", "").strip()
    active = request.GET.get("active", "")
    if query:
        routes = routes.filter(Q(origin__icontains=query) | Q(destination__icontains=query))
    if active:
        routes = routes.filter(is_active=active == "active")
    return render(request, "transport/routes.html", {
        "routes": Paginator(routes, 20).get_page(request.GET.get("page")),
        "q": query,
        "active": active,
    })


@admin_required
def route_create(request):
    form = RouteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Route added.")
        return redirect("transport:route_list")
    return render(request, "transport/route_form.html", {"form": form, "title": "Add route"})


@admin_required
def route_edit(request, pk):
    route = get_object_or_404(Route, pk=pk)
    form = RouteForm(request.POST or None, instance=route)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Route updated.")
        return redirect("transport:route_list")
    return render(request, "transport/route_form.html", {"form": form, "title": "Edit route", "object": route})


@admin_required
def route_delete(request, pk):
    route = get_object_or_404(Route, pk=pk)
    if request.method != "POST":
        return redirect("transport:route_list")
    if route.schedules.exists():
        messages.error(request, "Route cannot be deleted because schedules are linked to it.")
    else:
        route.delete()
        messages.success(request, "Route deleted.")
    return redirect("transport:route_list")


@admin_required
def bus_list(request):
    buses = Bus.objects.all()
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if query:
        buses = buses.filter(name_or_plate__icontains=query)
    if status:
        buses = buses.filter(status=status)
    return render(request, "transport/buses.html", {
        "buses": Paginator(buses, 20).get_page(request.GET.get("page")),
        "q": query,
        "status": status,
        "statuses": Bus.Status.choices,
    })


@admin_required
def bus_create(request):
    form = BusForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Bus registered.")
        return redirect("transport:bus_list")
    return render(request, "transport/bus_form.html", {"form": form, "title": "Register bus"})


@admin_required
def bus_edit(request, pk):
    bus = get_object_or_404(Bus, pk=pk)
    form = BusForm(request.POST or None, instance=bus)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Bus updated.")
        return redirect("transport:bus_list")
    return render(request, "transport/bus_form.html", {"form": form, "title": "Edit bus", "object": bus})


@admin_required
def bus_delete(request, pk):
    bus = get_object_or_404(Bus, pk=pk)
    if request.method != "POST":
        return redirect("transport:bus_list")
    # Any schedule (also cancelled or completed ones) keeps its bus: Schedule.bus is
    # on_delete=PROTECT, so deleting would raise ProtectedError (a 500 page).
    # Such buses are deactivated instead (Edit -> untick "Is active").
    if bus.schedules.exists():
        messages.error(request, "This bus has schedules, so it cannot be deleted. Deactivate it instead.")
    else:
        bus.delete()
        messages.success(request, "Bus deleted.")
    return redirect("transport:bus_list")


@admin_required
def schedule_list(request):
    schedules = Schedule.objects.select_related("route", "bus")
    period = request.GET.get("period", "upcoming")
    query = request.GET.get("q", "").strip()
    today = timezone.localdate()
    if period == "completed":
        schedules = schedules.filter(status=Schedule.Status.COMPLETED)
    elif period == "cancelled":
        schedules = schedules.filter(status=Schedule.Status.CANCELLED)
    else:
        schedules = schedules.filter(departure_date__gte=today, status=Schedule.Status.SCHEDULED)
    if query:
        schedules = schedules.filter(
            Q(route__origin__icontains=query)
            | Q(route__destination__icontains=query)
            | Q(bus__name_or_plate__icontains=query)
        )
    return render(request, "transport/schedules.html", {
        "schedules": Paginator(schedules, 20).get_page(request.GET.get("page")),
        "period": period,
        "q": query,
    })


@admin_required
def schedule_create(request):
    form = ScheduleForm(request.POST or None)
    form.fields["route"].queryset = Route.objects.filter(is_active=True)
    form.fields["bus"].queryset = Bus.objects.filter(is_active=True).exclude(status=Bus.Status.MAINTENANCE)
    if request.method == "POST" and form.is_valid():
        schedule = form.save(commit=False)
        try:
            schedule.full_clean()
            schedule.save()
        except Exception as exc:
            form.add_error(None, exc)
        else:
            schedule.bus.status = Bus.Status.ASSIGNED
            schedule.bus.save(update_fields=["status"])
            messages.success(request, "Schedule created.")
            return redirect("transport:schedule_list")
    return render(request, "transport/schedule_form.html", {"form": form, "title": "Create schedule"})


@admin_required
def schedule_edit(request, pk):
    schedule = get_object_or_404(Schedule.objects.select_related("route", "bus"), pk=pk)
    form = ScheduleForm(request.POST or None, instance=schedule)
    form.fields["route"].queryset = Route.objects.filter(is_active=True)
    form.fields["bus"].queryset = Bus.objects.filter(is_active=True).exclude(status=Bus.Status.MAINTENANCE)
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        try:
            updated.full_clean()
            updated.save()
        except Exception as exc:
            form.add_error(None, exc)
        else:
            schedule.bus.status = Bus.Status.AVAILABLE
            schedule.bus.save(update_fields=["status"])
            updated.bus.status = Bus.Status.ASSIGNED if updated.status == Schedule.Status.SCHEDULED else Bus.Status.AVAILABLE
            updated.bus.save(update_fields=["status"])
            messages.success(request, "Schedule updated.")
            return redirect("transport:schedule_list")
    return render(request, "transport/schedule_form.html", {"form": form, "title": "Update schedule", "object": schedule})


@admin_required
def schedule_cancel(request, pk):
    schedule = get_object_or_404(Schedule, pk=pk)
    if request.method == "POST" and schedule.status == Schedule.Status.SCHEDULED:
        schedule.status = Schedule.Status.CANCELLED
        schedule.save(update_fields=["status"])
        if not schedule.bus.schedules.filter(status=Schedule.Status.SCHEDULED).exists():
            schedule.bus.status = Bus.Status.AVAILABLE
            schedule.bus.save(update_fields=["status"])
        messages.success(request, "Schedule cancelled.")
    return redirect("transport:schedule_list")
