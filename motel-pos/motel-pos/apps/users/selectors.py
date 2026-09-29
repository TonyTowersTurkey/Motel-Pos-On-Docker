"""User query/selectors for motel occupancy system."""

from typing import Any

from django.contrib.auth import get_user_model


class UserSelector:
    """Read-side user queries. All complex lookups go here."""

    def get_by_username(self, username: str) -> get_user_model() | None:  # type: ignore[misc]
        """Retrieve a single user by exact username match.

        Args:
            username: The username to look up.

        Returns:
            User instance or None if not found.
        """
        UserModel = get_user_model()  # type: ignore[misc]
        try:
            return UserModel.objects.get(username__iexact=username)
        except UserModel.DoesNotExist:
            return None

    def list_by_role(self, role: str) -> Any:  # type: ignore[no-untyped-def]
        """List all users with a specific role.

        Args:
            role: The role string to filter by.

        Returns:
            QuerySet of matching user instances.
        """
        UserModel = get_user_model()  # type: ignore[misc]
        return UserModel.objects.filter(role=role)

    def list_active_users(self) -> Any:  # type: ignore[no-untyped-def]
        """List all active (non-suspended) users."""
        UserModel = get_user_model()  # type: ignore[misc]
        return UserModel.objects.filter(is_active=True)


user_selector = UserSelector()
