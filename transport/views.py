from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.permissions import admin_required
from .forms import BusForm, RouteForm, ScheduleForm
from .models import Bus, Route, Schedule


def _cancel_bookings_note(request, schedule):
    """Cancel (and refund) every booking on a trip the company cancelled, email
    everyone on those bookings, and say what happened."""
    # bookings depends on transport, not the reverse, so import here
    from bookings.emails import send_trip_cancelled_emails
    from bookings.services import cancel_trip_bookings

    cancelled, refunded, ids = cancel_trip_bookings(schedule)
    if not cancelled:
        return "It had no bookings."
    note = (f"{cancelled} booking{'s' if cancelled != 1 else ''} cancelled"
            f"{f', {refunded} marked refunded' if refunded else ''}.")
    sent = send_trip_cancelled_emails(ids, request.build_absolute_uri("/"))
    if sent:
        return note + f" {sent} email{'s' if sent != 1 else ''} sent to the travellers."
    return note + " The emails to the travellers could not be sent (check the email settings)."


# Buses an admin has taken off the road. They can't be given new trips, and the
# app never changes these two statuses itself: only an admin sets or clears them.
OFF_ROAD = (Bus.Status.MAINTENANCE, Bus.Status.UNAVAILABLE)


def _refresh_bus_status(bus):
    """Assigned while the bus has any scheduled trip, Available otherwise.
    A bus in Maintenance or Unavailable keeps that status."""
    if bus.status in OFF_ROAD:
        return
    busy = bus.schedules.filter(status=Schedule.Status.SCHEDULED).exists()
    status = Bus.Status.ASSIGNED if busy else Bus.Status.AVAILABLE
    if bus.status != status:
        bus.status = status
        bus.save(update_fields=["status"])


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
    elif period == "departed":
        # Trips whose day has passed but nobody marked Completed yet: newest first.
        schedules = schedules.filter(departure_date__lt=today, status=Schedule.Status.SCHEDULED).order_by(
            "-departure_date", "-departure_time")
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
    form.fields["bus"].queryset = Bus.objects.filter(is_active=True).exclude(status__in=OFF_ROAD)
    if request.method == "POST" and form.is_valid():
        schedule = form.save(commit=False)
        try:
            schedule.full_clean()
            schedule.save()
        except Exception as exc:
            form.add_error(None, exc)
        else:
            _refresh_bus_status(schedule.bus)
            messages.success(request, "Schedule created.")
            return redirect("transport:schedule_list")
    return render(request, "transport/schedule_form.html", {"form": form, "title": "Create schedule"})


@admin_required
def schedule_edit(request, pk):
    schedule = get_object_or_404(Schedule.objects.select_related("route", "bus"), pk=pk)
    was_status = schedule.status  # the form changes `schedule` in place when it validates
    form = ScheduleForm(request.POST or None, instance=schedule)
    # Keep the trip's own route and bus in the lists even if they were retired
    # since, so an old trip can still be edited (for example marked Completed).
    form.fields["route"].queryset = Route.objects.filter(Q(is_active=True) | Q(pk=schedule.route_id))
    form.fields["bus"].queryset = Bus.objects.filter(
        Q(is_active=True) & ~Q(status__in=OFF_ROAD) | Q(pk=schedule.bus_id))
    old_bus = schedule.bus
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        try:
            updated.full_clean()
            updated.save()
        except Exception as exc:
            form.add_error(None, exc)
        else:
            # the trip may have moved to another bus: both buses' statuses can change
            _refresh_bus_status(old_bus)
            if updated.bus_id != old_bus.pk:
                _refresh_bus_status(updated.bus)
            note = ""
            if was_status != Schedule.Status.CANCELLED and updated.status == Schedule.Status.CANCELLED:
                note = " " + _cancel_bookings_note(request, updated)
            messages.success(request, "Schedule updated." + note)
            return redirect("transport:schedule_list")
    return render(request, "transport/schedule_form.html", {"form": form, "title": "Update schedule", "object": schedule})


@admin_required
def schedule_passengers(request, pk):
    """Everyone travelling on one trip, sorted by seat, for the driver's list."""
    from bookings.models import Booking, PassengerDetail
    from bookings.seats import sort_key

    schedule = get_object_or_404(Schedule.objects.select_related("route", "bus"), pk=pk)
    # Live bookings only: confirmed (still to travel) or completed (already travelled).
    bookings = list(
        Booking.objects.filter(schedule=schedule)
        .exclude(status=Booking.Status.CANCELLED)
        .select_related("passenger")
    )
    travellers = sorted(
        PassengerDetail.objects.filter(booking__in=bookings).select_related("booking", "booking__passenger"),
        # travellers booked before seat selection have no seat: list them last
        key=lambda p: (not p.seat_number, sort_key(p.seat_number) if p.seat_number else (0, ""), p.pk),
    )
    paid = [b for b in bookings if b.payment_status == Booking.PaymentStatus.PAID]
    unpaid = [b for b in bookings if b.payment_status == Booking.PaymentStatus.PENDING]
    seats_taken = sum(b.seats_booked for b in bookings)
    total_seats = schedule.bus.total_seats
    return render(request, "transport/schedule_passengers.html", {
        "schedule": schedule,
        "travellers": travellers,
        "booking_count": len(bookings),
        "seats_taken": seats_taken,
        "fill": round(seats_taken * 100 / total_seats) if total_seats else 0,
        "paid_amount": sum(b.total_amount for b in paid),
        "paid_seats": sum(b.seats_booked for b in paid),
        "unpaid_amount": sum(b.total_amount for b in unpaid),
        "unpaid_seats": sum(b.seats_booked for b in unpaid),
        "unpaid_bookings": len(unpaid),
        "cancelled_bookings": Booking.objects.filter(schedule=schedule, status=Booking.Status.CANCELLED).count(),
    })


@admin_required
def schedule_cancel(request, pk):
    schedule = get_object_or_404(Schedule, pk=pk)
    if request.method == "POST" and schedule.status == Schedule.Status.SCHEDULED:
        schedule.status = Schedule.Status.CANCELLED
        schedule.save(update_fields=["status"])
        _refresh_bus_status(schedule.bus)
        messages.success(request, "Schedule cancelled. " + _cancel_bookings_note(request, schedule))
    return redirect("transport:schedule_list")
