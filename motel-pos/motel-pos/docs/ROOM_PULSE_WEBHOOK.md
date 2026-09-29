# Room Pulse Webhook — Receiver Design

## Purpose

Room Pulse sends the receiving POS a current snapshot of **all active rooms** and their confirmed
garage-door states. It sends one HTTP request for the full room list; it does not send one request
per room. A `room_state_changed` event is still a full snapshot, not a delta.

## HTTP request

```http
POST <configured POS webhook URL>
Content-Type: application/json
X-Room-Pulse-Event: 8d82e55c-ef4c-4105-b82a-df56c89445de
Authorization: Bearer <configured token>   # only when a token is configured
```

The `X-Room-Pulse-Event` value is identical to the JSON body’s `event_id`.

The POS should return any `2xx` status after accepting the event. The response body is ignored.
For a failed or non-`2xx` response, Room Pulse makes up to three immediate delivery attempts using
the same event ID and payload. The receiver should therefore process `event_id` idempotently.

## Example JSON body

```json
{
  "schema_version": "1.0",
  "event_id": "8d82e55c-ef4c-4105-b82a-df56c89445de",
  "event_type": "room_state_changed",
  "generated_at": "2026-07-15T14:31:00.123456+00:00",
  "source": "Garage Door Detection",
  "room_count": 1,
  "rooms": [
    {
      "room_record_id": 17,
      "room_number": 225,
      "room_name": "Room 225",
      "state": "closed",
      "confidence": 0.992,
      "state_source": "confirmed",
      "confirmation_streak": 4,
      "state_changed_at": "2026-07-15T13:42:00+00:00",
      "last_observed_at": "2026-07-15T14:30:00+00:00",
      "last_observed_state": "closed",
      "last_observed_confidence": 0.992,
      "camera_id": 3,
      "camera_name": "Garage North",
      "snapshot_id": 1842,
      "snapshot_captured_at": "2026-07-15T14:30:00+00:00",
      "crop_image_path": "/media/training_crops/camera_0003/room_0225/door.jpg",
      "crop_image_url": "https://garage.example.com/media/training_crops/camera_0003/room_0225/door.jpg",
      "model_version": "garage-door-v2",
      "stale": false
    }
  ]
}
```

## Top-level fields

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `schema_version` | string | Yes | Payload contract version. Currently `"1.0"`. |
| `event_id` | UUID string | Yes | Unique event/delivery ID and receiver idempotency key. |
| `event_type` | string | Yes | `room_state_changed`, `room_state_heartbeat`, or `test`. |
| `generated_at` | ISO 8601 datetime | Yes | UTC time at which this complete snapshot was built. |
| `source` | string | Yes | Name of the sending application; default is `Garage Door Detection`. |
| `room_count` | integer | Yes | Number of entries in `rooms`. |
| `rooms` | array | Yes | All rooms currently marked active. May be empty. |

Event types:

- `room_state_changed`: at least one confirmed room state changed since the last successful send.
- `room_state_heartbeat`: periodic full-state refresh at the configured interval.
- `test`: manually requested test delivery; it has the same real room data and structure.

## Room fields

| Field | Type | Nullable | Meaning |
|---|---|---:|---|
| `room_record_id` | integer | No | Sender’s internal database ID for the room record. |
| `room_number` | integer | No | Motel/POS-facing room number. This is the recommended business mapping field. |
| `room_name` | string | No | Display name configured for the room. |
| `state` | string enum | No | Confirmed state: `open`, `closed`, or `unknown`. |
| `confidence` | number | Yes | Confidence for the confirmed state, normally from `0.0` to `1.0`. |
| `state_source` | string | No | Currently always `confirmed`. |
| `confirmation_streak` | integer | No | Current number of consecutive matching observations. |
| `state_changed_at` | ISO 8601 datetime | Yes | Time the confirmed state last changed. |
| `last_observed_at` | ISO 8601 datetime | Yes | Time of the latest raw model observation. |
| `last_observed_state` | string enum | Yes | Latest raw observation: `open`, `closed`, or `unknown`. It may differ from `state` until confirmation. |
| `last_observed_confidence` | number | Yes | Confidence for the latest raw observation, normally `0.0` to `1.0`. |
| `camera_id` | integer | No | Sender’s internal camera ID. |
| `camera_name` | string | No | Configured camera display name. |
| `snapshot_id` | integer | Yes | Database ID of the snapshot used for the latest available room crop. |
| `snapshot_captured_at` | ISO 8601 datetime | Yes | Capture time of that snapshot. |
| `crop_image_path` | string | Yes | Sender-relative media path. Null when images are disabled or unavailable. |
| `crop_image_url` | URL string | Yes | Absolute crop URL. Null unless images are enabled, a crop exists, and a public base URL is configured. |
| `model_version` | string | Yes | Version recorded on the room’s latest detection event. |
| `stale` | boolean | No | `true` when no observation exists or the latest observation is more than 3 minutes old. |

All datetimes use ISO 8601. The sender emits UTC-aware timestamps, normally with a `+00:00`
offset. Nullable fields are included in the JSON with the value `null`; they are not normally
omitted.

## Recommended POS behavior

1. Authenticate the Bearer token when one is configured, and require HTTPS when traffic leaves a
   trusted private network.
2. Verify that the header `X-Room-Pulse-Event` matches body `event_id`.
3. If `event_id` was already accepted, return `200` without applying it again.
4. Validate `schema_version`; accept `1.0` and log or reject unsupported major versions.
5. For each item in `rooms`, map it to the POS using `room_number`, then upsert the latest state.
6. Treat `state` as authoritative. Use `last_observed_state` only for diagnostics because it may be
   unconfirmed.
7. Treat `unknown` and `stale: true` as explicit uncertainty; do not silently convert either to
   `open` or `closed`.
8. Store `generated_at` so an older delayed event cannot overwrite a newer snapshot.
9. Return a `2xx` response only after the event has been durably accepted. Keep processing fast and
   queue slower POS work asynchronously if needed.

Minimal successful response:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"accepted":true}
```

## Compatibility summary

- Method: `POST`
- Format: UTF-8 JSON (`application/json`)
- Authentication: optional Bearer token
- Delivery model: complete snapshot of active rooms
- Success contract: any `2xx` HTTP status
- Retry behavior: up to 3 attempts per event
- Duplicate handling: deduplicate by `event_id`
- Ordering protection: compare `generated_at`
- Primary POS mapping: `room_number`
