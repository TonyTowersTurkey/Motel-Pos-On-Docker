"""URL configuration for the revenue app."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.revenue.views import (
    OccupancySessionViewSet,
    ShiftLedgerViewSet,
)

app_name: str = "revenue"

router: DefaultRouter = DefaultRouter()  # type: ignore[type-arg]
router.register(r"sessions", OccupancySessionViewSet)
router.register(r"shifts", ShiftLedgerViewSet)


urlpatterns = [
    path("", include(router.urls)),
]
