"""Django authentication backend for motel occupancy system."""

import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

logger = logging.getLogger(__name__)


class MotelAuthBackend(ModelBackend):
    """Custom authentication backend supporting both Django auth and
    legacy motel username/password pairs if needed in the future.

    Falls back to the default ModelBackend for standard Django auth.
    """

    def authenticate(
        self,
        request: Any | None = None,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> get_user_model() | None:
        """Authenticate a user against the database.

        Args:
            request: The HTTP request object (unused).
            username: Username to authenticate.
            password: Password to verify.
            **kwargs: Additional keyword arguments from DRF.

        Returns:
            User instance if authentication succeeds, None otherwise.
        """
        if not username or not password:
            logger.warning("Missing username or password in auth request")
            return None

        UserModel = get_user_model()  # type: ignore[misc]
        try:
            user = UserModel.objects.get(username__iexact=username)
        except UserModel.DoesNotExist:
            logger.info("Auth attempt with non-existent username: %s", username)
            return None

        if not self.check_password_compat(user, password):
            logger.info(
                "Auth failure for user: %s (wrong password)",
                username,
            )
            return None

        if not self.user_can_authenticate(user):
            logger.info("Auth failure for inactive user: %s", username)
            return None

        logger.info("Successful auth for user: %s with role: %s", username, user.role)  # type: ignore[attr-defined]
        return user

    def check_password_compat(
        self,
        user: get_user_model(),
        password: str,
    ) -> bool:
        """Check if the provided password matches the user's hashed password.

        Args:
            user: The user instance to check against.
            password: The plain-text password to verify.

        Returns:
            True if password matches, False otherwise.
        """
        return user.check_password(password)

    def get_user(self, user_id: int) -> get_user_model() | None:  # type: ignore[misc]
        """Retrieve a user by their primary key ID.

        Args:
            user_id: The integer primary key of the user.

        Returns:
            User instance if found, None otherwise.
        """
        UserModel = get_user_model()  # type: ignore[misc]
        try:
            return UserModel.objects.get(pk=user_id)  # type: ignore[arg-type]
        except UserModel.DoesNotExist:
            return None
