"""Translate committed application model changes into dashboard invalidations."""

from __future__ import annotations

from functools import partial
from typing import Any

from django.apps import apps
from django.db import transaction
from django.db.models.signals import post_delete, post_save

from apps.core.events import publish_dashboard_update

REALTIME_APPS = {
    "guests",
    "maintenance",
    "occupancy",
    "revenue",
    "rooms",
    "users",
    "workorders",
}


def _model_changed(
    sender: type[Any], instance: Any, *, created: bool = False, **kwargs: Any
) -> None:
    """Schedule one invalidation only if the surrounding transaction succeeds."""
    del kwargs
    meta = sender._meta
    action = "created" if created else "updated"
    callback = partial(
        publish_dashboard_update,
        app_label=meta.app_label,
        model_name=meta.model_name,
        action=action,
        object_id=str(instance.pk),
    )
    transaction.on_commit(callback)


def _model_deleted(sender: type[Any], instance: Any, **kwargs: Any) -> None:
    del kwargs
    meta = sender._meta
    callback = partial(
        publish_dashboard_update,
        app_label=meta.app_label,
        model_name=meta.model_name,
        action="deleted",
        object_id=str(instance.pk),
    )
    transaction.on_commit(callback)


for model in apps.get_models():
    if model._meta.app_label not in REALTIME_APPS:
        continue
    label = model._meta.label_lower
    post_save.connect(
        _model_changed,
        sender=model,
        weak=False,
        dispatch_uid=f"dashboard-post-save-{label}",
    )
    post_delete.connect(
        _model_deleted,
        sender=model,
        weak=False,
        dispatch_uid=f"dashboard-post-delete-{label}",
    )
