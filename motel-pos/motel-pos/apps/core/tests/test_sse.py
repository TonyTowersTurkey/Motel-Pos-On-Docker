"""Tests for the authenticated dashboard event stream."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace

from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from apps.core.consumers import DashboardEventsConsumer
from apps.core.events import DASHBOARD_GROUP
from config.asgi import protocol_application

TEST_CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}


class DevelopmentStaticFilesTest(SimpleTestCase):
    def test_asgi_static_handler_serves_admin_css(self) -> None:
        async def scenario() -> None:
            communicator = ApplicationCommunicator(
                ASGIStaticFilesHandler(protocol_application),
                {
                    "type": "http",
                    "http_version": "1.1",
                    "method": "GET",
                    "path": "/static/admin/css/base.css",
                    "raw_path": b"/static/admin/css/base.css",
                    "query_string": b"",
                    "headers": [],
                    "server": ("testserver", 80),
                    "client": ("127.0.0.1", 12345),
                    "scheme": "http",
                },
            )
            await communicator.send_input(
                {"type": "http.request", "body": b"", "more_body": False}
            )
            response_start = await communicator.receive_output()
            assert response_start["status"] == HTTPStatus.OK
            headers = dict(response_start["headers"])
            assert headers[b"Content-Type"].startswith(b"text/css")
            await communicator.wait()

        async_to_sync(scenario)()


class LocalDevelopmentServerTest(SimpleTestCase):
    def test_reload_has_bounded_graceful_shutdown_for_open_event_streams(self) -> None:
        runner = Path(settings.BASE_DIR, "scripts", "run_local.sh").read_text()

        self.assertIn(
            'GRACEFUL_SHUTDOWN_TIMEOUT="${GRACEFUL_SHUTDOWN_TIMEOUT:-3}"',
            runner,
        )
        self.assertIn(
            '--timeout-graceful-shutdown "${GRACEFUL_SHUTDOWN_TIMEOUT}"',
            runner,
        )


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class DashboardEventsConsumerTest(TransactionTestCase):
    def test_rejects_anonymous_connections(self) -> None:
        async def scenario() -> None:
            communicator = ApplicationCommunicator(
                DashboardEventsConsumer.as_asgi(),
                {
                    "type": "http",
                    "method": "GET",
                    "path": "/api/events/stream/",
                    "headers": [],
                    "user": SimpleNamespace(is_authenticated=False),
                },
            )
            await communicator.send_input(
                {"type": "http.request", "body": b"", "more_body": False}
            )
            response_start = await communicator.receive_output()
            assert response_start["status"] == HTTPStatus.UNAUTHORIZED
            await communicator.wait()

        async_to_sync(scenario)()

    def test_streams_group_updates_to_authorized_staff(self) -> None:
        async def scenario() -> None:
            communicator = ApplicationCommunicator(
                DashboardEventsConsumer.as_asgi(),
                {
                    "type": "http",
                    "method": "GET",
                    "path": "/api/events/stream/",
                    "headers": [],
                    "user": SimpleNamespace(is_authenticated=True, role="cashier"),
                },
            )
            await communicator.send_input(
                {"type": "http.request", "body": b"", "more_body": False}
            )
            response_start = await communicator.receive_output()
            assert response_start["status"] == HTTPStatus.OK
            ready = await communicator.receive_output()
            assert b"event: ready" in ready["body"]

            channel_layer = get_channel_layer()
            assert channel_layer is not None
            await channel_layer.group_send(
                DASHBOARD_GROUP,
                {
                    "type": "dashboard.update",
                    "payload": {
                        "event_id": "test-event",
                        "app": "rooms",
                        "model": "room",
                        "action": "updated",
                        "object_id": "room_101",
                    },
                },
            )
            update = await communicator.receive_output()
            assert b"event: dashboard.update" in update["body"]
            assert b'"object_id":"room_101"' in update["body"]
            await communicator.send_input({"type": "http.disconnect"})
            await communicator.wait()

        async_to_sync(scenario)()
