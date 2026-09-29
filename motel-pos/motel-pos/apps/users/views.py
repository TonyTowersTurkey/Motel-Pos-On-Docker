"""Views for the users app - authentication and user management."""

import logging

from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from rest_framework import generics, status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.permissions import DjangoPermissionRequired
from apps.users.models import User
from apps.users.serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    SelfProfileSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)


# --- Public Views ---


class UserCreateView(generics.CreateAPIView):  # type: ignore[type-arg]
    """Admin-only endpoint for creating cashier/manager/admin accounts."""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [DjangoPermissionRequired]
    permission_required = "users.add_user"


@api_view(["POST"])  # type: ignore[call-overload]
@permission_classes([AllowAny])
@parser_classes([JSONParser])
def user_login(request) -> Response:  # type: ignore[no-untyped-def]
    """Authenticate a user and issue JWT tokens.

    Args:
        request: POST request containing username and password.

    Returns:
        HTTP 200 with tokens on success, 401 on failure.
    """
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    authenticated_user: User | None = authenticate(
        request=request,
        username=serializer.validated_data["username"],
        password=serializer.validated_data["password"],
    )

    if not authenticated_user:
        logger.warning(
            "Login failure for username: %s", serializer.validated_data.get("username")
        )
        return Response(
            {"detail": "Invalid username or password."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    refresh = RefreshToken.for_user(authenticated_user)
    auth_login(request, authenticated_user)
    logger.info("Successful login for user: %s", authenticated_user.username)

    return Response(
        {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserSerializer(authenticated_user).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])  # type: ignore[call-overload]
@permission_classes([IsAuthenticated])
def user_logout(request) -> Response:  # type: ignore[no-untyped-def]
    """Logout the current user and clear any session-backed auth state.

    Args:
        request: Authenticated POST request with an optional refresh token in body.

    Returns:
        HTTP 205 after clearing the session and, when possible, blacklisting refresh.
    """
    username = request.user.get_username()
    refresh_value = request.data.get("refresh", "")
    if refresh_value:
        try:
            RefreshToken(refresh_value).blacklist()
        except Exception as exc:
            logger.warning(
                "Refresh blacklist skipped for user %s: %s",
                username,
                exc,
            )

    auth_logout(request)
    logger.info("User %s logged out", username)
    return Response(status=status.HTTP_205_RESET_CONTENT)


# --- User Management Views ---


class UserListView(generics.ListAPIView):  # type: ignore[type-arg]
    """List all users (manager/admin only)."""

    serializer_class = UserSerializer
    permission_classes = [DjangoPermissionRequired]
    permission_required = "users.view_user"

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Return a stable user list for manager/admin review."""
        return User.objects.order_by("username")


class UserDetailView(generics.RetrieveUpdateAPIView):  # type: ignore[type-arg]
    """Retrieve user details for managers/admins, but reserve mutations for admins."""

    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Allow manager review while keeping user-account changes admin-only."""
        self.permission_required = (
            "users.view_user"
            if self.request.method in SAFE_METHODS
            else "users.change_user"
        )
        return [DjangoPermissionRequired()]


@api_view(["PUT"])  # type: ignore[call-overload]
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def password_change(request) -> Response:  # type: ignore[no-untyped-def]
    """Change the current user's password.

    Args:
        request: PUT request with old_password, new_password1, new_password2.

    Returns:
        HTTP 200 on success, 400 on validation failure.
    """
    serializer = PasswordChangeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    if not request.user.check_password(serializer.validated_data["old_password"]):
        return Response(
            {"detail": "Old password is incorrect"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    new_password = serializer.validated_data["new_password1"]
    if new_password != serializer.validated_data["new_password2"]:
        return Response(
            {"detail": "New passwords do not match"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    request.user.set_password(new_password)
    request.user.save(update_fields=["password"])
    logger.info("Password changed for user: %s", request.user.username)

    return Response(
        {"detail": "Password updated successfully"},
        status=status.HTTP_200_OK,
    )


class SelfProfileView(generics.RetrieveUpdateAPIView):  # type: ignore[type-arg]
    """Get or update the authenticated user's own profile."""

    serializer_class = SelfProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self) -> User:
        """Return the currently authenticated user."""
        return self.request.user


class SelfProfileUpdateView(generics.UpdateAPIView):  # type: ignore[type-arg]
    """Update the authenticated user's own profile (non-sensitive fields only)."""

    serializer_class = SelfProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self) -> User:
        """Return the currently authenticated user."""
        return self.request.user
