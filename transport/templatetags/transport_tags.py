"""Template filters for the transport admin pages.  Load with {% load transport_tags %}."""

from django import template

register = template.Library()


@register.filter
def duration(value):
    """timedelta(hours=5, minutes=30) -> "5 h 30 m"; timedelta(hours=10) -> "10 h"."""
    if value is None:
        return ""
    hours, minutes = divmod(int(value.total_seconds()) // 60, 60)
    return f"{hours} h {minutes:02d} m" if minutes else f"{hours} h"
