"""URL configuration for the users app."""

from django.urls import path

from apps.users.views import (
    SelfProfileUpdateView,
    SelfProfileView,
    UserCreateView,
    UserDetailView,
    UserListView,
    password_change,
    user_login,
    user_logout,
)

app_name: str = "users"

urlpatterns = [
    # User listing endpoint (at /api/users/)
    path("", UserListView.as_view(), name="user-list"),
    # Authentication endpoints under /api/auth/
    path("auth/login/", user_login, name="login"),
    path("auth/logout/", user_logout, name="logout"),
    path("auth/password-change/", password_change, name="password-change"),
    # User management
    path("<int:pk>/", UserDetailView.as_view(), name="user-detail"),
    path("create/", UserCreateView.as_view(), name="user-create"),
    # Self-service endpoints (at /api/users/profile/)
    path("profile/", SelfProfileView.as_view(), name="self-profile"),
    path(
        "profile/update/",
        SelfProfileUpdateView.as_view(),
        name="self-profile-update",
    ),
]
