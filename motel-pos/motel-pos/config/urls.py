"""URL configuration for motel occupancy Django project.

Root URL router includes all sub-app endpoints under /api/.
Frontend views serve the static HTML UIs as Django templates.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import FileResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.core.healthcheck import healthcheck
from apps.guests import views as guests_views
from apps.maintenance import views as maintenance_views
from apps.occupancy import views as occupancy_views
from apps.revenue import views as revenue_views
from apps.rooms import views as rooms_views
from apps.users import views as users_views
from apps.workorders import views as workorders_views

app_name: str = "config"

api_router: DefaultRouter = DefaultRouter()  # type: ignore[type-arg]


def favicon_view(request):  # type: ignore[no-untyped-def]
    """Serve the browser favicon without depending on reverse-proxy static config."""
    return FileResponse(
        open(settings.STATIC_ROOT / "favicon.svg", "rb"),
        content_type="image/svg+xml",
    )

# Register all ViewSets
api_router.register(r"rooms", rooms_views.RoomViewSet)
api_router.register(r"vehicles", guests_views.VehicleViewSet)
api_router.register(
    r"vehicle-shapes",
    guests_views.VehicleShapeViewSet,
    basename="vehicle-shapes",
)
api_router.register(r"planned-maintenance-templates", maintenance_views.PlannedMaintenanceTemplateViewSet)
api_router.register(r"work-orders", workorders_views.WorkOrderViewSet)
api_router.register(r"pricing-tiers", rooms_views.PricingTierViewSet)
api_router.register(r"amenities", rooms_views.AmenityViewSet)
api_router.register(r"room-amenities", rooms_views.RoomAmenityViewSet)
api_router.register(r"maintenance", rooms_views.MaintenanceLogViewSet)
api_router.register(r"rental-sessions", rooms_views.RentalSessionViewSet)
api_router.register(
    r"pricing-rules", rooms_views.DynamicPricingRuleViewSet, basename="pricing-rules"
)
api_router.register(r"events", occupancy_views.OccupancyEventViewSet)
api_router.register(r"audit-log", occupancy_views.AuditLogViewSet, basename="audit-log")
api_router.register(r"sessions", revenue_views.OccupancySessionViewSet)
api_router.register(r"ledgers", revenue_views.ShiftLedgerViewSet)

urlpatterns = [
    path("favicon.ico", favicon_view, name="favicon"),
    path("favicon.svg", favicon_view, name="favicon-svg"),
    # Health check - no auth required
    path("api/health/", healthcheck, name="health"),
    path(
        "api/webhooks/room-pulse",
        occupancy_views.RoomPulseWebhookView.as_view(),
        name="room-pulse-webhook",
    ),
    path(
        "api/webhooks/room-pulse/",
        occupancy_views.RoomPulseWebhookView.as_view(),
        name="room-pulse-webhook-slash",
    ),
    # Admin interface
    path("admin/", admin.site.urls),
    # API docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # --- Frontend template views ---
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="login"),
        name="logout",
    ),
    path("", rooms_views.dashboard_view, name="rooms_dashboard"),
    path("cashier/login/", revenue_views.cashier_login_view, name="revenue_cashier_login"),
    path("cashier/", revenue_views.cashier_view, name="revenue_cashier"),
    path("manager/", rooms_views.manager_view, name="rooms_manager"),
    path("manager/rooms/", rooms_views.room_config_view, name="rooms_config"),
    path(
        "manager/vehicles/",
        guests_views.vehicle_manager_view,
        name="vehicles_manager",
    ),
    path("maintenance/", include(("apps.maintenance.urls", "maintenance"), namespace="maintenance")),
    # Auth (JWT) - root level
    path("api/auth/login/", users_views.user_login, name="users_login"),
    path("api/auth/logout/", users_views.user_logout, name="users_logout"),
    path(
        "api/auth/password-change/", users_views.password_change, name="password-change"
    ),
    path(
        "api/auth/token/obtain/",
        TokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Revenue API extensions (cuadre JSON + generate-shift) under /api/
    path(
        "api/revenue/cuadre/",
        revenue_views.ShiftLedgerViewSet.as_view({"get": "cuadre"}),
        name="revenue-cuadre",
    ),
    path(
        "api/revenue/generate-shift/",
        revenue_views.ShiftLedgerViewSet.as_view({"post": "generate_shift"}),
        name="revenue-generate-shift",
    ),
    path(
        "api/revenue/summary/",
        revenue_views.ShiftLedgerViewSet.as_view({"get": "summary"}),
        name="revenue-summary",
    ),
    path(
        "api/revenue/sales-summary/",
        revenue_views.ShiftLedgerViewSet.as_view({"get": "sales_summary"}),
        name="revenue-sales-summary",
    ),
    # Report generation under /api/
    path(
        "api/reports/generate/<str:report_type>/",
        revenue_views.generate_report_view,
        name="generate_report",
    ),
    # Users app endpoints - MUST be before the api_router catch-all
    path("api/users/", include("apps.users.urls")),
    # API (authenticated by DefaultRouter + DRF permission classes)
    path("api/", include(api_router.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
