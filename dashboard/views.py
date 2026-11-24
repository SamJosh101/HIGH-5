import csv
from collections import defaultdict
from datetime import date as date_type, datetime, time, timedelta
from decimal import Decimal

from django.apps import apps
from django.core.paginator import Paginator
from django.contrib import messages
from django.db import transaction
from django.views.decorators.http import require_POST
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.permissions import admin_required
from transport.models import Bus, Route, Schedule


def get_booking_model():
    try:
        return apps.get_model("bookings", "Booking")
    except LookupError:
        return None


def paid_bookings(queryset):
    if not queryset.exists():
        return queryset.none()
    field_names = {field.name for field in queryset.model._meta.get_fields()}
    if "payment_status" in field_names:
        status_field = queryset.model._meta.get_field("payment_status")
        paid_values = [value for value, label in getattr(status_field, "choices", ()) if str(value).upper() == "PAID"]
        if paid_values:
            return queryset.filter(payment_status__in=paid_values)
    if "status" in field_names:
        return queryset.filter(status="PAID")
    return queryset.none()


def _day_start(day):
    """Midnight at the start of `day` in the site's time zone (Africa/Lagos).

    Date filters use datetime ranges instead of `booked_at__date` / TruncDate:
    those need MySQL's time-zone tables, which a normal MySQL install doesn't
    have loaded, so they silently return nothing.
    """
    return timezone.make_aware(datetime.combine(day, time.min))


def _parse_date(value):
    """'2026-11-24' -> date, or None for an empty or invalid value."""
    try:
        return date_type.fromisoformat(value) if value else None
    except ValueError:
        return None


def _local_day(moment):
    return timezone.localtime(moment).date()


def _percent_change(now, before):
    """+12 means 12% more than before; None when there is nothing to compare with."""
    if not before:
        return None
    return round((now - before) * 100 / before)


def _greeting(hour):
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


ALMOST_FULL_PERCENT = 80  # a departure this full is flagged amber
CHART_DAYS = 14
CHART_MONTHS = 6


@admin_required
def admin_home(request):
    from bookings.models import Booking

    now = timezone.localtime()
    today = now.date()
    month_start = today.replace(day=1)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    # Compare month-to-date with the same number of days last month.
    last_month_end = min(last_month_start + (today - month_start) + timedelta(days=1), month_start)

    live = Booking.objects.exclude(status=Booking.Status.CANCELLED)
    paid = live.filter(payment_status=Booking.PaymentStatus.PAID)

    def in_range(queryset, start, end):
        return queryset.filter(booked_at__gte=_day_start(start), booked_at__lt=_day_start(end))

    tomorrow = today + timedelta(days=1)
    month_revenue = in_range(paid, month_start, tomorrow).aggregate(t=Sum("total_amount"))["t"] or Decimal("0")
    last_revenue = in_range(paid, last_month_start, last_month_end).aggregate(t=Sum("total_amount"))["t"] or Decimal("0")
    month_bookings = in_range(live, month_start, tomorrow).count()
    last_bookings = in_range(live, last_month_start, last_month_end).count()

    # Departures with how full they are (confirmed seats only; cancelled bookings free their seats).
    with_seats = (
        Schedule.objects.filter(status=Schedule.Status.SCHEDULED)
        .select_related("route", "bus")
        .annotate(seats_taken=Coalesce(Sum("bookings__seats_booked", filter=Q(bookings__status=Booking.Status.CONFIRMED)), 0))
    )
    today_departures = list(with_seats.filter(departure_date=today))
    for schedule in today_departures:
        schedule.fill = round(schedule.seats_taken * 100 / schedule.bus.total_seats)
    upcoming = list(
        with_seats.filter(departure_date__gte=today)
        .exclude(departure_date=today, departure_time__lte=now.time())  # already left
        .order_by("departure_date", "departure_time")[:5]
    )
    for schedule in upcoming:
        schedule.fill = round(schedule.seats_taken * 100 / schedule.bus.total_seats)
        schedule.almost_full = schedule.fill >= ALMOST_FULL_PERCENT

    # Chart data, grouped in Python by local date (see _day_start).
    chart_start = today - timedelta(days=CHART_DAYS - 1)
    days = [chart_start + timedelta(days=i) for i in range(CHART_DAYS)]
    daily_revenue = dict.fromkeys(days, Decimal("0"))
    daily_bookings = dict.fromkeys(days, 0)
    for booked_at, amount, payment in in_range(live, chart_start, tomorrow).values_list("booked_at", "total_amount", "payment_status"):
        day = _local_day(booked_at)
        daily_bookings[day] += 1
        if payment == Booking.PaymentStatus.PAID:
            daily_revenue[day] += amount

    months = []
    first = month_start
    for _ in range(CHART_MONTHS):
        months.insert(0, first)
        first = (first - timedelta(days=1)).replace(day=1)
    monthly_revenue = dict.fromkeys(months, Decimal("0"))
    for booked_at, amount in in_range(paid, months[0], tomorrow).values_list("booked_at", "total_amount"):
        monthly_revenue[_local_day(booked_at).replace(day=1)] += amount

    chart = {
        "daily": {"labels": [d.strftime("%d %b") for d in days], "values": [float(v) for v in daily_revenue.values()], "money": True},
        "monthly": {"labels": [m.strftime("%b %Y") for m in months], "values": [float(v) for v in monthly_revenue.values()], "money": True},
        "bookings": {"labels": [d.strftime("%d %b") for d in days], "values": list(daily_bookings.values()), "money": False},
    }

    context = {
        "greeting": _greeting(now.hour),
        "today": today,
        "month_revenue": month_revenue,
        "revenue_change": _percent_change(month_revenue, last_revenue),
        "month_bookings": month_bookings,
        "bookings_change": _percent_change(month_bookings, last_bookings),
        "today_departures_count": len(today_departures),
        "almost_full_today": sum(s.fill >= ALMOST_FULL_PERCENT for s in today_departures),
        "pending_bookings": live.filter(payment_status=Booking.PaymentStatus.PENDING).count(),
        "upcoming_departures": upcoming,
        "recent_bookings": Booking.objects.select_related("schedule__route").order_by("-booked_at")[:5],
        "chart_data": chart,
        # Totals kept for the tests and the Transport overview.
        "total_buses": Bus.objects.count(),
        "total_routes": Route.objects.count(),
        "total_schedules": Schedule.objects.count(),
        "total_bookings": Booking.objects.count(),
    }
    return render(request, "dashboard/home.html", context)


@admin_required
def booking_list(request):
    Booking = get_booking_model()
    bookings = Booking.objects.select_related("schedule__route", "passenger").all() if Booking else Booking
    if Booking:
        query = request.GET.get("q", "").strip()
        date = request.GET.get("date", "")
        route_id = request.GET.get("route", "")
        status = request.GET.get("status", "")
        if query:
            bookings = bookings.filter(booking_ref__icontains=query)
        day = _parse_date(date)
        if day:
            bookings = bookings.filter(booked_at__gte=_day_start(day), booked_at__lt=_day_start(day + timedelta(days=1)))
        if route_id:
            bookings = bookings.filter(schedule__route_id=route_id)
        if status:
            field_names = {field.name for field in Booking._meta.get_fields()}
            if "payment_status" in field_names:
                bookings = bookings.filter(payment_status=status)
            elif "status" in field_names:
                bookings = bookings.filter(status=status)
        page = Paginator(bookings.order_by("-booked_at"), 20).get_page(request.GET.get("page"))
    else:
        query = date = route_id = status = ""
        page = None
    return render(request, "dashboard/bookings.html", {
        "bookings": page,
        "routes": Route.objects.all(),
        "q": query,
        "date": date,
        "route_id": route_id,
        "status": status,
        "booking_model_available": Booking is not None,
    })


@admin_required
def booking_detail(request, pk):
    Booking = get_booking_model()
    if not Booking:
        return render(request, "dashboard/booking_detail.html", {"booking_model_available": False})
    booking = get_object_or_404(Booking.objects.select_related("schedule__route", "schedule__bus", "passenger"), pk=pk)
    return render(request, "dashboard/booking_detail.html", {"booking": booking, "booking_model_available": True})


@admin_required
@require_POST
def mark_booking_paid(request, pk):
    Booking = get_booking_model()

    if not Booking:
        messages.error(request, "Booking records are unavailable.")
        return redirect("dashboard:bookings")

    with transaction.atomic():
        booking = get_object_or_404(
            Booking.objects.select_for_update(),
            pk=pk
        )

        if booking.status == Booking.Status.CANCELLED:
            messages.error(
                request,
                "Cancelled bookings cannot be marked as paid."
            )

        elif booking.payment_status == Booking.PaymentStatus.PAID:
            messages.info(
                request,
                "This booking has already been marked as paid."
            )

        elif booking.payment_status != Booking.PaymentStatus.PENDING:
            messages.error(
                request,
                "Only pending payments can be marked as paid."
            )

        else:
            booking.payment_status = Booking.PaymentStatus.PAID
            booking.save(update_fields=["payment_status"])

            messages.success(
                request,
                f"Booking {booking.booking_ref} has been marked as paid."
            )

    return redirect("dashboard:booking_detail", pk=pk)



@admin_required
def reports(request):
    start = request.GET.get("start", "")
    end = request.GET.get("end", "")
    Booking = get_booking_model()
    booking_queryset = Booking.objects.all() if Booking else None
    paid = paid_bookings(booking_queryset) if booking_queryset is not None else booking_queryset
    start_day, end_day = _parse_date(start), _parse_date(end)
    if paid is not None and start_day:
        paid = paid.filter(booked_at__gte=_day_start(start_day))
    if paid is not None and end_day:
        paid = paid.filter(booked_at__lt=_day_start(end_day + timedelta(days=1)))

    if paid is not None:
        total_revenue = paid.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
        total_bookings = paid.count()
        by_day, by_month = defaultdict(Decimal), defaultdict(Decimal)
        for booked_at, amount in paid.values_list("booked_at", "total_amount"):
            day = _local_day(booked_at)
            by_day[day] += amount
            by_month[day.replace(day=1)] += amount
        daily = [{"day": d, "revenue": by_day[d]} for d in sorted(by_day)]
        monthly = [{"month": m, "revenue": by_month[m]} for m in sorted(by_month)]
    else:
        total_revenue = Decimal("0.00")
        total_bookings = 0
        daily = []
        monthly = []

    if request.GET.get("export") == "csv" and paid is not None:
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="high5-booking-report.csv"'
        writer = csv.writer(response)
        writer.writerow(["Booking reference", "Passenger", "Route", "Departure", "Seats", "Amount", "Payment status", "Status"])
        for booking in paid.select_related("passenger", "schedule", "schedule__route").order_by("-booked_at"):
            writer.writerow([
                getattr(booking, "booking_ref", ""),
                getattr(getattr(booking, "passenger", None), "email", ""),
                str(getattr(getattr(booking, "schedule", None), "route", "")),
                getattr(getattr(booking, "schedule", None), "departure_datetime", ""),
                getattr(booking, "seats_booked", ""),
                getattr(booking, "total_amount", ""),
                getattr(booking, "payment_status", ""),
                getattr(booking, "status", ""),
            ])
        return response

    return render(request, "dashboard/reports.html", {
        "start": start,
        "end": end,
        "total_revenue": total_revenue,
        "total_bookings": total_bookings,
        "daily": daily,
        "monthly": monthly,
        "booking_model_available": Booking is not None,
    })
