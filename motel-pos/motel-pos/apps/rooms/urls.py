"""URL configuration for the rooms app."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.rooms.views import (
    DynamicPricingRuleViewSet,
    AmenityViewSet,
    MaintenanceLogViewSet,
    PricingTierViewSet,
    RentalSessionViewSet,
    RoomAmenityViewSet,
    RoomViewSet,
)

app_name: str = "rooms"

router: DefaultRouter = DefaultRouter()  # type: ignore[type-arg]
router.register(r"rooms", RoomViewSet)
router.register(r"pricing-tiers", PricingTierViewSet)
router.register(r"amenities", AmenityViewSet)
router.register(r"room-amenity", RoomAmenityViewSet)
router.register(r"maintenance", MaintenanceLogViewSet)
router.register(r"rental-sessions", RentalSessionViewSet)
router.register(
    r"pricing-rules", DynamicPricingRuleViewSet, basename="pricing-rules"
)


urlpatterns = [
    path("", include(router.urls)),
]
