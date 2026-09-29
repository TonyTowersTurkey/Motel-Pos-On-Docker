"""Publish small, non-sensitive invalidation events to connected dashboards."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

DASHBOARD_GROUP = "dashboard_updates"


def publish_dashboard_update(
    *, app_label: str, model_name: str, action: str, object_id: str
) -> None:
    """Notify browsers that persisted dashboard data should be reconciled."""
    channel_layer = get_channel_layer()
    if channel_layer is None:  # pragma: no cover - protects unusual deployments
        logger.warning("Dashboard update skipped because no channel layer is configured")
        return

    payload: dict[str, Any] = {
        "event_id": str(uuid4()),
        "occurred_at": datetime.now(UTC).isoformat(),
        "app": app_label,
        "model": model_name,
        "action": action,
        "object_id": object_id,
    }
    try:
        async_to_sync(channel_layer.group_send)(
            DASHBOARD_GROUP,
            {"type": "dashboard.update", "payload": payload},
        )
    except Exception:  # pragma: no cover - updates must never roll back business data
        logger.exception("Unable to publish dashboard update")
