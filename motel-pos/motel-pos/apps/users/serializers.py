"""Serializers for motel occupancy user model."""

from rest_framework import serializers

from apps.users.access import assign_role_group
from apps.users.models import User


class UserSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Serializer for the custom User model.

    Provides read/write access to user fields with password hashing support.

    Attributes:
        role_display: Read-only field showing the human-readable role name.
    """

    role_display: serializers.CharField = serializers.CharField(
        source="get_role_display",
        read_only=True,
        required=False,
    )
    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
            "role_display",
            "capabilities",
            "notes",
            "is_active",
            "is_staff",
            "is_superuser",
            "password",
            "date_joined",
            "last_login",
        ]
        read_only_fields = [
            "id",
            "date_joined",
            "last_login",
            "is_superuser",
        ]
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def validate_role(self, value: str) -> str:
        """Validate that the role is one of the allowed motel roles.

        Args:
            value: The role string to validate.

        Returns:
            The validated role string.

        Raises:
            serializers.ValidationError: If the role is not valid.
        """
        valid_roles = [choice[0] for choice in User.Role.choices]  # type: ignore[attr-defined]
        if value not in valid_roles:
            raise serializers.ValidationError(
                f"Invalid role. Must be one of: {', '.join(valid_roles)}"
            )
        return value

    def get_capabilities(self, instance: User) -> dict[str, bool]:
        """Expose stable UI capabilities without making role authoritative."""
        return {
            "cashier_access": instance.has_perm("rooms.view_room"),
            "manager_access": instance.has_perm("rooms.change_room"),
            "manage_users": instance.has_perm("users.change_user"),
            "manage_vehicles": instance.has_perm("guests.change_vehicle"),
            "manage_maintenance": instance.has_perm("workorders.view_workorder"),
            "generate_reports": instance.has_perm(
                "revenue.generate_management_reports"
            ),
        }

    def create(self, validated_data):
        """Create user with hashed password."""
        password = validated_data.pop("password", None)
        instance = self.Meta.model(**validated_data)
        if password:
            instance.set_password(password)
        instance.save()
        assign_role_group(instance)
        return instance

    def update(self, instance, validated_data):
        """Update user with password hashing."""
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        assign_role_group(instance)
        return instance


class SelfProfileSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Serializer for safe self-service profile reads and updates."""

    role_display: serializers.CharField = serializers.CharField(
        source="get_role_display",
        read_only=True,
        required=False,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
            "role_display",
            "notes",
            "is_active",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
        ]
        read_only_fields = [
            "id",
            "username",
            "role",
            "role_display",
            "is_active",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
        ]


class LoginSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """Serializer for user login requests.

    Attributes:
        username: The username to authenticate with.
        password: The plain-text password to verify.
    """

    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, write_only=True)


class PasswordChangeSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """Serializer for changing a user's password.

    Attributes:
        old_password: The current (old) password for verification.
        new_password1: The new password to set.
        new_password2: Confirmation of the new password.
    """

    old_password = serializers.CharField(max_length=128, write_only=True)
    new_password1 = serializers.CharField(max_length=128, write_only=True)
    new_password2 = serializers.CharField(max_length=128, write_only=True)

    def validate(self, attrs):  # type: ignore[override]
        """Validate password change request."""
        # Extract user from data if provided directly (test scenarios),
        # otherwise pull from serializer context.
        user = attrs.pop("user", None)
        if not user and self.context.get("request"):
            user = self.context["request"].user
        old_password = attrs.get("old_password", "")
        if not user or not user.check_password(old_password):
            raise serializers.ValidationError(
                {"old_password": "Current password is incorrect."}
            )
        if attrs.get("new_password1") != attrs.get("new_password2"):
            raise serializers.ValidationError(
                {"new_password2": "Passwords do not match."}
            )
        return attrs

    def save(self, **kwargs):  # type: ignore[override]
        """Save and update the user's password."""
        user = self.initial_data.get("user") or (
            self.context.get("request").user if self.context.get("request") else None
        )
        new_password = self.validated_data.get("new_password1")
        if user and new_password:
            user.set_password(new_password)
            user.save()
        return user
