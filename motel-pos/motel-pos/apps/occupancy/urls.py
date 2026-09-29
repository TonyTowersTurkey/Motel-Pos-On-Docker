"""URL configuration for the occupancy app."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.occupancy.views import (
    AuditLogViewSet,
    OccupancyEventViewSet,
)

app_name: str = "occupancy"

router: DefaultRouter = DefaultRouter()  # type: ignore[type-arg]
router.register(r"events", OccupancyEventViewSet)
router.register(r"audit-log", AuditLogViewSet, basename="audit-log")


urlpatterns = [
    path("", include(router.urls)),
]
