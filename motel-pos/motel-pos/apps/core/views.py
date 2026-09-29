"""Shared view functions for motel occupancy Django project."""

from django.conf import settings
from django.shortcuts import render


def base_context(request) -> dict:
    """Common template context shared across all frontend views."""
    return {"debug": getattr(settings, "DEBUG", False)}


def dashboard_view(request) -> render:  # type: ignore[return]
    """Serve the main occupancy dashboard template."""
    ctx = base_context(request)
    ctx["default_room"] = "101"
    ctx["new_room_default"] = "102"
    return render(request, "rooms/dashboard.html", ctx)


def manager_view(request) -> render:  # type: ignore[return]
    """Serve the manager dashboard template."""
    ctx = base_context(request)
    ctx["default_room"] = "101"
    ctx["new_room_default"] = "102"
    return render(request, "rooms/manager.html", ctx)


def cashier_view(request) -> render:  # type: ignore[return]
    """Serve the cashier portal template."""
    ctx = base_context(request)
    ctx["default_room"] = "101"
    ctx["default_username"] = "cashier"
    return render(request, "revenue/cashier.html", ctx)
