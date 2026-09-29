"""Admin interface for motel occupancy custom user model."""

from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.users.access import assign_role_group
from apps.users.models import User


class MotelUserAdmin(BaseUserAdmin):  # type: ignore[misc]
    """Admin interface extending Django's default UserAdmin with motel-specific fields.

    Attributes:
        list_display: Columns shown in the user list view.
        fieldsets: Field groups shown in the user edit form.
        add_fieldsets: Field groups shown when creating a new user.
        list_filter: Fields available for filtering in the changelist.
        search_fields: Fields available for full-text search.
    """

    list_display: tuple[str, ...] = (
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "is_active",
        "is_staff",
    )
    list_filter: tuple[str, ...] = ("role", "is_active", "is_staff", "date_joined")
    search_fields: tuple[str, ...] = (
        "username",
        "email",
        "first_name",
        "last_name",
        "phone",
    )

    fieldsets: tuple[tuple[str, dict[str, Any]], ...] = (
        (None, {"fields": ("username", "password")}),
        (
            "Personal info",
            {
                "fields": ("first_name", "last_name", "email", "phone"),
            },
        ),
        ("Role", {"fields": ("role",)}),
        ("Notes", {"fields": ("notes",)}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets: tuple[tuple[str, dict[str, Any]], ...] = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "password1",
                    "password2",
                    "role",
                    "first_name",
                    "last_name",
                    "email",
                    "phone",
                ),
            },
        ),
    )

    ordering: tuple[str, ...] = ("username",)

    def save_related(self, request, form, formsets, change):  # type: ignore[no-untyped-def]
        """Keep the legacy role and managed group aligned during transition."""
        super().save_related(request, form, formsets, change)
        assign_role_group(form.instance)


admin.site.register(User, MotelUserAdmin)  # type: ignore[arg-type]
