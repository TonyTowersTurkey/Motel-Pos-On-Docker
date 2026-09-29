"""Provision default motel role accounts for development and ops smoke tests."""

import os
from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.users.access import assign_role_group, provision_role_groups
from apps.users.models import User


@dataclass(frozen=True)
class RoleAccount:
    """Account settings for one motel role."""

    role: str
    username: str
    password: str
    email: str
    email_explicit: bool = False
    is_staff: bool = False


class Command(BaseCommand):
    """Create or update the standard cashier, manager, and admin accounts."""

    help = "Ensure default cashier, manager, and admin motel users exist."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--cashier-username",
            default=os.environ.get("MOTEL_CASHIER_USERNAME", "cashier"),
            help="Cashier username to create or update.",
        )
        parser.add_argument(
            "--cashier-password",
            default=None,
            help=(
                "Cashier password for new users, or resets with --reset-password. "
                "Supply it via --cashier-password or MOTEL_CASHIER_PASSWORD."
            ),
        )
        parser.add_argument(
            "--cashier-email",
            default=None,
            help=(
                "Cashier email to apply when creating the user; existing users "
                "keep their email unless this option is provided explicitly."
            ),
        )
        parser.add_argument(
            "--manager-username",
            default=os.environ.get("MOTEL_MANAGER_USERNAME", "manager"),
            help="Manager username to create or update.",
        )
        parser.add_argument(
            "--manager-password",
            default=None,
            help=(
                "Manager password for new users, or resets with --reset-password. "
                "Supply it via --manager-password or MOTEL_MANAGER_PASSWORD."
            ),
        )
        parser.add_argument(
            "--manager-email",
            default=None,
            help=(
                "Manager email to apply when creating the user; existing users "
                "keep their email unless this option is provided explicitly."
            ),
        )
        parser.add_argument(
            "--admin-username",
            default=os.environ.get("MOTEL_ADMIN_USERNAME", "admin"),
            help="Admin username to create or update.",
        )
        parser.add_argument(
            "--admin-password",
            default=None,
            help=(
                "Admin password for new users, or resets with --reset-password. "
                "Supply it via --admin-password or MOTEL_ADMIN_PASSWORD."
            ),
        )
        parser.add_argument(
            "--admin-email",
            default=None,
            help=(
                "Admin email to apply when creating the user; existing users "
                "keep their email unless this option is provided explicitly."
            ),
        )
        parser.add_argument(
            "--reset-password",
            action="store_true",
            help="Reset existing account passwords to the supplied role passwords.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        provision_role_groups(migrate_users=False)
        cashier_email_option = options["cashier_email"]
        manager_email_option = options["manager_email"]
        admin_email_option = options["admin_email"]

        accounts = [
            RoleAccount(
                role=User.Role.CASHIER,
                username=options["cashier_username"],
                password=self._resolve_password(
                    options["cashier_password"],
                    "MOTEL_CASHIER_PASSWORD",
                    "cashier",
                ),
                email=(
                    cashier_email_option.strip()
                    if cashier_email_option is not None
                    else os.environ.get("MOTEL_CASHIER_EMAIL", "cashier@local.invalid")
                ),
                email_explicit=cashier_email_option is not None,
            ),
            RoleAccount(
                role=User.Role.MANAGER,
                username=options["manager_username"],
                password=self._resolve_password(
                    options["manager_password"],
                    "MOTEL_MANAGER_PASSWORD",
                    "manager",
                ),
                email=(
                    manager_email_option.strip()
                    if manager_email_option is not None
                    else os.environ.get("MOTEL_MANAGER_EMAIL", "manager@local.invalid")
                ),
                email_explicit=manager_email_option is not None,
            ),
            RoleAccount(
                role=User.Role.ADMIN,
                username=options["admin_username"],
                password=self._resolve_password(
                    options["admin_password"],
                    "MOTEL_ADMIN_PASSWORD",
                    "admin",
                ),
                email=(
                    admin_email_option.strip()
                    if admin_email_option is not None
                    else os.environ.get("MOTEL_ADMIN_EMAIL", "admin@local.invalid")
                ),
                email_explicit=admin_email_option is not None,
                is_staff=True,
            ),
        ]

        usernames = [account.username.strip() for account in accounts]
        if len(set(usernames)) != len(usernames):
            raise CommandError("Bootstrap usernames must be unique.")

        for account in accounts:
            result = self._ensure_account(account, options["reset_password"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"{account.role.title()} user {account.username!r} {result}."
                )
            )

    def _resolve_password(
        self, password_option: str | None, env_var: str, role_name: str
    ) -> str:
        password = password_option if password_option is not None else os.environ.get(env_var)
        if password is None or password == "":
            raise CommandError(
                f"{role_name.title()} password must be provided via --{role_name}-password or {env_var}."
            )
        return password

    def _ensure_account(self, account: RoleAccount, reset_password: bool) -> str:
        username = account.username.strip()
        password = account.password
        email = account.email.strip()
        if not username:
            raise CommandError(f"{account.role.title()} username cannot be blank.")
        if not password:
            raise CommandError(f"{account.role.title()} password cannot be blank.")
        if not email:
            raise CommandError(f"{account.role.title()} email cannot be blank.")

        UserModel = get_user_model()
        user, created = UserModel.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "role": account.role,
                "is_active": True,
                "is_staff": account.is_staff,
            },
        )

        changed_fields: list[str] = []
        if created or reset_password:
            user.set_password(password)
            changed_fields.append("password")
        if user.role != account.role:
            user.role = account.role
            changed_fields.append("role")
        if not user.is_active:
            user.is_active = True
            changed_fields.append("is_active")
        if user.is_staff != account.is_staff:
            user.is_staff = account.is_staff
            changed_fields.append("is_staff")
        if account.email_explicit and email and user.email != email:
            user.email = email
            if "email" not in changed_fields:
                changed_fields.append("email")

        if changed_fields:
            user.save(update_fields=changed_fields)
        assign_role_group(user)

        if created:
            return "created"
        if changed_fields:
            return "updated"
        return "unchanged"
