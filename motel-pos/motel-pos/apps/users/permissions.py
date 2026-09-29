"""User-specific permission classes."""

from rest_framework.permissions import BasePermission


class RoleRequired(BasePermission):
    """Permission class requiring a minimum role level.

    Usage in views: set `minimum_role = 'cashier'` on the view class.
    """

    message = "Insufficient role for this action."

    def has_permission(self, request, view) -> bool:  # type: ignore[no-untyped-def]
        """Check if user's role meets or exceeds the required minimum."""
        if not request.user or not request.user.is_authenticated:
            return False

        role = getattr(request.user, "role", None)
        if role is None:
            return False

        if hasattr(view, "minimum_role"):
            hierarchy = ["cashier", "manager", "admin"]
            try:
                required_idx = hierarchy.index(view.minimum_role)  # type: ignore[attr-defined]
                user_idx = hierarchy.index(role)
                return user_idx >= required_idx
            except ValueError:
                pass

        return False


class StaffOnly(BasePermission):
    """Allow access only to staff users (is_staff=True)."""

    def has_permission(self, request, view) -> bool:  # type: ignore[no-untyped-def]
        """Check if user is a staff member."""
        return bool(
            request.user and request.user.is_authenticated and request.user.is_staff
        )
