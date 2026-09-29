"""Factory-boy factories for user model."""

import factory.django
from django.contrib.auth import get_user_model

from apps.users.access import assign_role_group

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    """Factory for custom User model."""

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda u: f"{u.username}@motel.com")
    first_name = "Test"
    last_name = "User"
    is_staff = False
    is_superuser = False

    @factory.post_generation
    def password(self, create, extracted, **kwargs):  # type: ignore[no-untyped-def]
        """Set password after creation (use set_password for proper hashing)."""
        if not create:
            return  # pragma: no cover
        password = extracted or "change_me"
        self.set_password(password)

    @factory.post_generation
    def role_group(self, create, extracted, **kwargs):  # type: ignore[no-untyped-def]
        """Mirror the legacy role into its managed Django group for tests."""
        if not create:
            return  # pragma: no cover
        assign_role_group(self)
