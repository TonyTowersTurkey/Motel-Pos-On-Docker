"""Django permission adapters shared by DRF endpoints."""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission


def _permission_tuple(
    value: str | tuple[str, ...] | list[str] | set[str] | None,
) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(value)


class DjangoPermissionRequired(BasePermission):
    """Require the Django permissions declared on ``view.permission_required``."""

    message = "You do not have permission to perform this action."

    def has_permission(self, request: Any, view: Any) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        permissions = _permission_tuple(getattr(view, "permission_required", None))
        return bool(permissions) and request.user.has_perms(permissions)


class DjangoActionPermissions(BasePermission):
    """Map a DRF ViewSet action to one or more Django permissions.

    Views declare ``permission_map`` and may optionally declare
    ``default_permission``. Missing mappings fail closed.
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request: Any, view: Any) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        permission_map = getattr(view, "permission_map", {})
        required = permission_map.get(
            getattr(view, "action", None),
            getattr(view, "default_permission", None),
        )
        permissions = _permission_tuple(required)
        return bool(permissions) and request.user.has_perms(permissions)


class CanGenerateManagementReports(BasePermission):
    """Require the custom management-report permission."""

    def has_permission(self, request: Any, view: Any) -> bool:  # noqa: ARG002
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.has_perm("revenue.generate_management_reports")
        )


# Transitional aliases for endpoints not yet moved to an explicit action map.
# They now use Django permissions rather than the legacy ``role`` field.
class IsManagerOrAdmin(BasePermission):
    def has_permission(self, request: Any, view: Any) -> bool:  # noqa: ARG002
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.has_perm("rooms.change_room")
        )


class IsAdminRole(BasePermission):
    def has_permission(self, request: Any, view: Any) -> bool:  # noqa: ARG002
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.has_perm("users.change_user")
        )


class IsCashierOrAbove(BasePermission):
    def has_permission(self, request: Any, view: Any) -> bool:  # noqa: ARG002
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.has_perm("rooms.view_room")
        )
