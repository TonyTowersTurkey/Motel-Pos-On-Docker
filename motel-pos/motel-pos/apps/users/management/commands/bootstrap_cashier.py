"""Provision the default cashier account for motel desk login."""

import os
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.users.access import assign_role_group, provision_role_groups
from apps.users.models import User


class Command(BaseCommand):
    """Create or update the operational cashier login."""

    help = "Ensure the motel cashier user exists for the cashier portal."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--username",
            default=os.environ.get("MOTEL_CASHIER_USERNAME", "cashier"),
            help="Cashier username to create or update.",
        )
        parser.add_argument(
            "--password",
            default=None,
            help=(
                "Password for new users, or for resets with --reset-password. "
                "Supply it via --password or MOTEL_CASHIER_PASSWORD."
            ),
        )
        parser.add_argument(
            "--email",
            default=None,
            help=(
                "Email to apply when creating the cashier user; existing users "
                "keep their email unless this option is provided explicitly."
            ),
        )
        parser.add_argument(
            "--reset-password",
            action="store_true",
            help="Reset the cashier password to the supplied password.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        provision_role_groups(migrate_users=False)
        username = options["username"].strip()
        password = (
            options["password"]
            if options["password"] is not None
            else os.environ.get("MOTEL_CASHIER_PASSWORD")
        )
        email_option = options["email"]
        reset_password = options["reset_password"]
        explicit_email = email_option is not None
        email = (
            email_option.strip()
            if explicit_email and email_option is not None
            else os.environ.get("MOTEL_CASHIER_EMAIL", "cashier@local.invalid")
        )

        if not username:
            raise CommandError('Cashier username cannot be blank.')
        if explicit_email and not email:
            raise CommandError('Cashier email cannot be blank.')

        UserModel = get_user_model()
        existing_user = UserModel.objects.filter(username=username).first()
        password_required = existing_user is None or reset_password
        if password_required and (password is None or password == ''):
            raise CommandError(
                'Cashier password must be provided via --password or MOTEL_CASHIER_PASSWORD.'
            )

        user, created = UserModel.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "role": User.Role.CASHIER,
                "is_active": True,
            },
        )

        changed_fields: list[str] = []
        if created or reset_password:
            user.set_password(password)
            changed_fields.append("password")
        if user.role != User.Role.CASHIER:
            user.role = User.Role.CASHIER
            changed_fields.append("role")
        if not user.is_active:
            user.is_active = True
            changed_fields.append("is_active")
        if user.is_staff:
            user.is_staff = False
            changed_fields.append("is_staff")
        if user.is_superuser:
            user.is_superuser = False
            changed_fields.append("is_superuser")
        if explicit_email and email and user.email != email:
            user.email = email
            if "email" not in changed_fields:
                changed_fields.append("email")

        if changed_fields:
            user.save(update_fields=changed_fields)
        assign_role_group(user)

        if created:
            result = "created"
        elif changed_fields:
            result = "updated"
        else:
            result = "unchanged"
        self.stdout.write(self.style.SUCCESS(f"Cashier user {username!r} {result}."))
