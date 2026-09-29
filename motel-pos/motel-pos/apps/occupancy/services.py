"""Occupancy controls and transactional Room Pulse ingestion."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from django.db import transaction

from apps.core.models import MotelSettings
from apps.occupancy.models import (
    OccupancyEvent,
    RoomPulseDelivery,
    RoomPulseRoomState,
)
from apps.rooms.models import RentalSession, Room

logger = logging.getLogger(__name__)

MANUAL_STATES = {
    "occupied": "manual_occupied",
    "vacant": "manual_vacant",
    "maintenance": "maintenance",
}

ROOM_PULSE_OCCUPANCY_STATES = {
    "closed": "occupied",
    "open": "vacant",
    "unknown": "unknown",
}


class OccupancyService:
    """Apply manual controls and authoritative Room Pulse snapshots."""

    def _sync_revenue_session(
        self,
        room_id: str,
        action: str,
        source: str = "manual_override",
        occurred_at: datetime | None = None,
        audit_mode: bool = False,
    ) -> None:
        """Keep revenue sessions aligned with an accepted occupancy change."""
        from apps.revenue.models import OccupancySession
        from apps.revenue.services import revenue_engine

        active_session = (
            OccupancySession.objects.filter(
                room_id=room_id,
                status=OccupancySession.Status.ACTIVE,
                check_out__isnull=True,
            )
            .order_by("-check_in")
            .first()
        )

        if action == "occupied":
            if active_session is None:
                revenue_engine.create_occupancy_session(
                    room_id=room_id,
                    event_type="occupied",
                    source=source,
                    check_in_at=occurred_at,
                )
            return

        if action == "vacant" and active_session is not None:
            revenue_engine.close_occupancy_session(
                active_session.id,
                check_out_at=occurred_at,
                bill_in_eight_hour_blocks=audit_mode,
            )

    def _sync_audit_sale(
        self,
        room: Room,
        action: str,
        occurred_at: datetime,
        *,
        allow_create: bool,
    ) -> None:
        """Create or update the single cashier sale driven by Audit Mode."""
        sale = (
            RentalSession.objects.filter(
                room_id=room.room_id,
                source="room_pulse_audit",
                status=RentalSession.Status.CHECKED_IN,
            )
            .order_by("start_time", "session_id")
            .first()
        )

        if action == "occupied":
            if sale is None:
                if not allow_create:
                    return
                RentalSession.objects.create(
                    room_id=room.room_id,
                    start_time=occurred_at,
                    end_time=occurred_at + timedelta(hours=8),
                    status=RentalSession.Status.CHECKED_IN,
                    source="room_pulse_audit",
                    vehicle=room.current_vehicle,
                    reviewed_by="Audit Mode",
                    notes="Automatically created when Room Pulse marked room occupied.",
                )
                return

            elapsed_hours = max(
                0,
                (occurred_at - sale.start_time).total_seconds() / 3600,
            )
            billed_hours = (
                24 if elapsed_hours > 16 else (16 if elapsed_hours > 8 else 8)
            )
            billed_end = sale.start_time + timedelta(hours=billed_hours)
            if sale.end_time != billed_end:
                sale.end_time = billed_end
                sale.save(update_fields=["end_time"])
            return

        if action != "vacant" or sale is None:
            return

        exit_time = max(occurred_at, sale.start_time)
        elapsed_hours = (exit_time - sale.start_time).total_seconds() / 3600
        billed_hours = 24 if elapsed_hours > 16 else (16 if elapsed_hours > 8 else 8)
        sale.exit_time = exit_time
        sale.end_time = sale.start_time + timedelta(hours=billed_hours)
        sale.status = RentalSession.Status.CHECKED_OUT
        sale.save(update_fields=["exit_time", "end_time", "status"])

    def manual_override(self, room_id: str, action: str, user: str) -> dict[str, Any]:
        """Apply an explicit staff override without any sensor transport."""
        try:
            new_state = MANUAL_STATES[action]
        except KeyError as exc:
            raise ValueError(f"Unknown override action: {action}") from exc

        Room.objects.filter(room_id=room_id).update(current_state=new_state)
        event = OccupancyEvent.objects.create(
            room_id=room_id,
            event_type=OccupancyEvent.EventType.MANUAL_OVERRIDE,
            confidence=1.0,
            source=OccupancyEvent.Source.MANUAL_INPUT,
            notes=f"{user} set room state to {new_state}",
        )
        try:
            self._sync_revenue_session(room_id, action)
        except Exception:  # pragma: no cover - revenue sync must not block overrides
            logger.exception("Failed to sync occupancy session for room %s", room_id)

        return {
            "room_id": room_id,
            "new_state": new_state,
            "event_id": event.event_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "user": user,
        }

    @transaction.atomic
    def ingest_room_pulse_snapshot(
        self,
        data: dict[str, Any],
        raw_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Durably apply a validated Room Pulse snapshot exactly once.

        ``generated_at`` is compared independently for each room, so a delayed
        delivery can be retained for audit without rolling newer room state back.
        """
        delivery, created = RoomPulseDelivery.objects.get_or_create(
            event_id=data["event_id"],
            defaults={
                "schema_version": data["schema_version"],
                "event_type": data["event_type"],
                "generated_at": data["generated_at"],
                "source": data["source"],
                "room_count": data["room_count"],
                "payload": raw_payload,
            },
        )
        if not created:
            return {
                "accepted": True,
                "duplicate": True,
                "event_id": str(delivery.event_id),
                **delivery.result,
            }

        requested_numbers = {str(room["room_number"]) for room in data["rooms"]}
        rooms_by_number: dict[str, list[Room]] = {}
        for room in Room.objects.select_for_update().filter(
            active=True, room_number__in=requested_numbers
        ):
            rooms_by_number.setdefault(room.room_number, []).append(room)

        updated = 0
        unchanged = 0
        out_of_order = 0
        unmapped: list[str] = []
        ambiguous: list[str] = []
        operating_mode = MotelSettings.active_operating_mode()
        audit_mode = operating_mode == MotelSettings.OperatingMode.AUDIT_MODE

        for incoming in data["rooms"]:
            room_number = str(incoming["room_number"])
            matches = rooms_by_number.get(room_number, [])
            if not matches:
                unmapped.append(room_number)
                continue
            if len(matches) > 1:
                ambiguous.append(room_number)
                continue

            room = matches[0]
            latest = (
                RoomPulseRoomState.objects.select_for_update()
                .filter(room=room)
                .first()
            )
            if latest is not None and latest.generated_at >= data["generated_at"]:
                out_of_order += 1
                continue

            effective_state = (
                "unknown"
                if incoming["stale"]
                else ROOM_PULSE_OCCUPANCY_STATES[incoming["state"]]
            )
            previous_state = room.current_state

            # Once the desk confirms a departed vehicle will not return, an
            # open door must not immediately erase the room's cleaning state.
            # A later closed-door signal can still move it back to occupied.
            if (
                operating_mode == MotelSettings.OperatingMode.POS_HANDS_ON_MODE
                and previous_state == "dirty"
                and effective_state == "vacant"
            ):
                effective_state = "dirty"

            state_values = {
                key: incoming[key]
                for key in (
                    "room_record_id",
                    "room_name",
                    "state",
                    "confidence",
                    "state_source",
                    "confirmation_streak",
                    "state_changed_at",
                    "last_observed_at",
                    "last_observed_state",
                    "last_observed_confidence",
                    "camera_id",
                    "camera_name",
                    "snapshot_id",
                    "snapshot_captured_at",
                    "crop_image_path",
                    "crop_image_url",
                    "model_version",
                    "stale",
                )
            }
            for nullable_text_field in (
                "last_observed_state",
                "crop_image_path",
                "crop_image_url",
                "model_version",
            ):
                state_values[nullable_text_field] = (
                    state_values[nullable_text_field] or ""
                )
            RoomPulseRoomState.objects.update_or_create(
                room=room,
                defaults={
                    "delivery": delivery,
                    "generated_at": data["generated_at"],
                    **state_values,
                },
            )

            audit_mode_vehicle_release = bool(
                operating_mode == MotelSettings.OperatingMode.AUDIT_MODE
                and effective_state == "vacant"
                and room.current_vehicle_id
            )
            released_vehicle = (
                room.current_vehicle if audit_mode_vehicle_release else None
            )

            if previous_state == effective_state and not audit_mode_vehicle_release:
                if audit_mode and effective_state in {"occupied", "vacant"}:
                    self._sync_audit_sale(
                        room,
                        effective_state,
                        data["generated_at"],
                        allow_create=False,
                    )
                unchanged += 1
                continue

            room.current_state = effective_state
            update_fields = ["current_state"]
            if audit_mode_vehicle_release:
                room.current_vehicle = None
                update_fields.append("current_vehicle")
            room.save(update_fields=update_fields)
            updated += 1

            if released_vehicle is not None:
                OccupancyEvent.objects.create(
                    room_id=room.room_id,
                    event_type=OccupancyEvent.EventType.VEHICLE_CLEARED,
                    confidence=incoming["confidence"] or 0.0,
                    source=OccupancyEvent.Source.ROOM_PULSE,
                    notes=(
                        f"Room Pulse event {delivery.event_id}: automatically "
                        f"released vehicle {released_vehicle}; room remains vacant."
                    ),
                )

            if previous_state == effective_state:
                if audit_mode and effective_state == "vacant":
                    self._sync_audit_sale(
                        room,
                        effective_state,
                        data["generated_at"],
                        allow_create=False,
                    )
                continue

            if effective_state not in {"occupied", "vacant"}:
                continue

            event_type = (
                OccupancyEvent.EventType.ARRIVAL
                if effective_state == "occupied"
                else OccupancyEvent.EventType.DEPARTURE
            )
            OccupancyEvent.objects.create(
                room_id=room.room_id,
                event_type=event_type,
                confidence=incoming["confidence"] or 0.0,
                source=OccupancyEvent.Source.ROOM_PULSE,
                notes=(
                    f"Room Pulse event {delivery.event_id}: door "
                    f"{incoming['state']} mapped to {effective_state}"
                ),
            )
            self._sync_revenue_session(
                room.room_id,
                effective_state,
                source="room_pulse",
                occurred_at=data["generated_at"],
                audit_mode=audit_mode,
            )
            if audit_mode:
                self._sync_audit_sale(
                    room,
                    effective_state,
                    data["generated_at"],
                    allow_create=effective_state == "occupied",
                )

        result = {
            "updated": updated,
            "unchanged": unchanged,
            "out_of_order": out_of_order,
            "unmapped_room_numbers": sorted(unmapped),
            "ambiguous_room_numbers": sorted(ambiguous),
        }
        delivery.result = result
        delivery.save(update_fields=["result"])
        return {
            "accepted": True,
            "duplicate": False,
            "event_id": str(delivery.event_id),
            **result,
        }


occupancy_service = OccupancyService()
