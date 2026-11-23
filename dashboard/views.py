import csv
import json
from datetime import timedelta
from decimal import Decimal

from django.apps import apps
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponse
from django.shortcuts import render
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


@admin_required
def admin_home(request):
    today = timezone.localdate()
    Booking = get_booking_model()
    bookings = Booking.objects.all() if Booking else None
    paid = paid_bookings(bookings) if bookings is not None else None
    today_departures = Schedule.objects.filter(departure_date=today).exclude(status=Schedule.Status.CANCELLED)
    total_revenue = Decimal("0.00")
    if paid is not None:
        field_names = {field.name for field in paid.model._meta.get_fields()}
        if "total_amount" in field_names:
            total_revenue = paid.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    daily_revenue = []
    monthly_revenue = []
    booking_trends = []
    route_popularity = []
    if paid is not None:
        start = today - timedelta(days=30)
        daily_revenue = list(paid.filter(booked_at__date__gte=start).annotate(day=TruncDate("booked_at")).values("day").annotate(revenue=Sum("total_amount")).order_by("day"))
        monthly_revenue = list(paid.annotate(month=TruncMonth("booked_at")).values("month").annotate(revenue=Sum("total_amount")).order_by("month")[:12])
        booking_field_names = {field.name for field in paid.model._meta.get_fields()}
        if "booked_at" in booking_field_names:
            booking_trends = list(bookings.filter(booked_at__date__gte=start).annotate(day=TruncDate("booked_at")).values("day").annotate(count=Count("id")).order_by("day"))
        route_popularity = list(bookings.filter(schedule__isnull=False).values("schedule__route__origin", "schedule__route__destination").annotate(count=Count("id")).order_by("-count")[:8])
    context = {
        "total_buses": Bus.objects.count(),
        "total_routes": Route.objects.count(),
        "total_schedules": Schedule.objects.count(),
        "total_bookings": bookings.count() if bookings is not None else 0,
        "total_revenue": total_revenue,
        "today_departures_count": today_departures.count(),
        "available_buses": Bus.objects.filter(status=Bus.Status.AVAILABLE, is_active=True).count(),
        "pending_bookings": 0,
        "recent_bookings": bookings.select_related("schedule", "passenger").order_by("-booked_at")[:8] if bookings is not None and hasattr(Booking, "objects") else [],
        "upcoming_departures": Schedule.objects.filter(departure_date__gte=today, status=Schedule.Status.SCHEDULED).select_related("route", "bus").order_by("departure_date", "departure_time")[:8],
        "daily_revenue_json": json.dumps([{"day": str(row["day"]), "revenue": str(row["revenue"])} for row in daily_revenue]),
        "monthly_revenue_json": json.dumps([{"month": str(row["month"]), "revenue": str(row["revenue"])} for row in monthly_revenue]),
        "booking_trends_json": json.dumps([{"day": str(row["day"]), "count": row["count"]} for row in booking_trends]),
        "route_popularity_json": json.dumps([{"route": f'{row["schedule__route__origin"]} → {row["schedule__route__destination"]}', "count": row["count"]} for row in route_popularity]),
    }
    if bookings is not None:
        field_names = {field.name for field in Booking._meta.get_fields()}
        if "payment_status" in field_names:
            context["pending_bookings"] = bookings.filter(payment_status="PENDING").count()
        elif "status" in field_names:
            context["pending_bookings"] = bookings.filter(status="PENDING").count()
    return render(request, "dashboard/home.html", context)


@admin_required
def booking_list(request):
    Booking = get_booking_model()
    bookings = Booking.objects.select_related("schedule", "passenger").all() if Booking else Booking
    if Booking:
        query = request.GET.get("q", "").strip()
        date = request.GET.get("date", "")
        route_id = request.GET.get("route", "")
        status = request.GET.get("status", "")
        if query:
            bookings = bookings.filter(booking_ref__icontains=query)
        if date:
            bookings = bookings.filter(booked_at__date=date)
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
    booking = Booking.objects.select_related("schedule", "passenger").get(pk=pk)
    return render(request, "dashboard/booking_detail.html", {"booking": booking, "booking_model_available": True})


@admin_required
def reports(request):
    start = request.GET.get("start", "")
    end = request.GET.get("end", "")
    Booking = get_booking_model()
    booking_queryset = Booking.objects.all() if Booking else None
    paid = paid_bookings(booking_queryset) if booking_queryset is not None else booking_queryset
    if paid is not None and start:
        paid = paid.filter(booked_at__date__gte=start)
    if paid is not None and end:
        paid = paid.filter(booked_at__date__lte=end)

    if paid is not None:
        total_revenue = paid.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
        total_bookings = paid.count()
        daily = list(paid.annotate(day=TruncDate("booked_at")).values("day").annotate(revenue=Sum("total_amount")).order_by("day"))
        monthly = list(paid.annotate(month=TruncMonth("booked_at")).values("month").annotate(revenue=Sum("total_amount")).order_by("month"))
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
