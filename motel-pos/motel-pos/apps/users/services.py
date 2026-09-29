"""User service layer for motel occupancy system."""

import logging

from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)


class UserService:
    """Service layer for user management operations.

    Encapsulates all write-side user logic (creation, role updates, password changes).
    """

    def create_user(  # type: ignore[no-untyped-def]
        self,
        username: str,
        password: str,
        email: str = "",
        first_name: str = "",
        last_name: str = "",
        phone: str = "",
        role: str = "cashier",
    ) -> get_user_model():  # type: ignore[misc]
        """Create a new user account.

        Args:
            username: Unique username for the new user.
            password: Plain-text password (will be hashed).
            email: Email address for the user.
            first_name: User's first name.
            last_name: User's last name.
            phone: Contact phone number.
            role: Role assignment (cashier/manager/admin).

        Returns:
            The newly created user instance.
        """
        UserModel = get_user_model()  # type: ignore[misc]
        user = UserModel.objects.create_user(  # type: ignore[attr-defined]
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role=role,
        )

        logger.info("Created user account for %s with role %s", username, role)
        return user

    def update_role(  # type: ignore[no-untyped-def]
        self,
        user_id: int,
        new_role: str,
    ) -> get_user_model():  # type: ignore[misc]
        """Update a user's role.

        Args:
            user_id: The primary key of the user to update.
            new_role: New role string (cashier/manager/admin).

        Returns:
            The updated user instance.
        """
        UserModel = get_user_model()  # type: ignore[misc]
        user = UserModel.objects.get(pk=user_id)  # type: ignore[arg-type]
        old_role = user.role
        user.role = new_role  # type: ignore[union-attr]
        user.save(update_fields=["role"])

        logger.info(
            "Updated role for user %s: %s -> %s",
            user.username,
            old_role,
            new_role,
        )
        return user


user_service = UserService()
