"""Template context shared by every page."""

from pathlib import Path

from django.conf import settings


def _latest_static_change():
    """Newest modification time of our CSS/JS files, as an integer."""
    newest = 0
    for folder in settings.STATICFILES_DIRS:
        for path in Path(folder).rglob("*"):
            if path.suffix in (".css", ".js"):
                newest = max(newest, int(path.stat().st_mtime))
    return newest


def asset_version(request):
    """`{{ ASSET_VERSION }}` is appended to CSS/JS links (?v=...), so browsers
    download a fresh copy whenever a file changes instead of using an old
    cached one. In development it follows the files' last change; in
    production set ASSET_VERSION in .env (e.g. the release number)."""
    version = getattr(settings, "ASSET_VERSION", "") or (_latest_static_change() if settings.DEBUG else "1")
    return {"ASSET_VERSION": version}


def currency(request):
    """`{{ CURRENCY }}` – the money symbol from .env (CURRENCY_SYMBOL, default ₦), for any template."""
    return {"CURRENCY": settings.CURRENCY_SYMBOL}
