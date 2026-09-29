from dataclasses import dataclass
from urllib.parse import quote

import httpx

from app.core.config import Settings, settings


class UnifiProtectError(RuntimeError):
    """A safe-to-display UniFi Protect integration error."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class UnifiCamera:
    id: str
    name: str
    state: str
    model: str | None = None
    mac: str | None = None


class UnifiProtectClient:
    def __init__(self, config: Settings = settings, *, console_id: str | None = None) -> None:
        self.config = config
        self.console_id = console_id or config.unifi_console_id
        self._client = httpx.Client(
            timeout=config.unifi_timeout_seconds,
            follow_redirects=True,
            verify=config.unifi_verify_ssl,
        )

    def __enter__(self) -> "UnifiProtectClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def list_cameras(self) -> list[UnifiCamera]:
        response = self._request("GET", "/v1/cameras", accept="application/json")
        try:
            payload = response.json()
        except ValueError as exc:
            raise UnifiProtectError("Protect returned an invalid camera list") from exc

        if not isinstance(payload, list):
            raise UnifiProtectError("Protect returned an unexpected camera list")

        cameras = []
        for item in payload:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            cameras.append(
                UnifiCamera(
                    id=str(item["id"]),
                    name=self._camera_name(item),
                    state=str(item.get("state") or "UNKNOWN"),
                    model=self._optional_string(item.get("modelKey")),
                    mac=self._optional_string(item.get("mac")),
                )
            )
        return cameras

    def get_snapshot(self, camera_id: str) -> bytes:
        quality = str(self.config.unifi_snapshot_high_quality).lower()
        path = f"/v1/cameras/{quote(camera_id, safe='')}/snapshot"
        try:
            response = self._request(
                "GET",
                path,
                accept="image/jpeg",
                params={"highQuality": quality},
            )
        except UnifiProtectError as exc:
            if not self.config.unifi_snapshot_high_quality or exc.status_code != 400:
                self._raise_snapshot_error(exc)
            try:
                response = self._request(
                    "GET",
                    path,
                    accept="image/jpeg",
                    params={"highQuality": "false"},
                )
            except UnifiProtectError as fallback_exc:
                self._raise_snapshot_error(fallback_exc)
        if not response.content:
            raise UnifiProtectError("Protect returned an empty snapshot")
        return response.content

    @staticmethod
    def _raise_snapshot_error(exc: UnifiProtectError) -> None:
        if exc.status_code == 500:
            raise UnifiProtectError(
                "Protect could not generate a snapshot for this camera (HTTP 500). "
                "The camera can still be connected; use a Protect RTSPS stream or a "
                "direct local camera snapshot as a fallback.",
                status_code=exc.status_code,
            ) from exc
        raise exc

    def _request(
        self,
        method: str,
        path: str,
        *,
        accept: str,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            response = self._client.request(
                method,
                f"{self._base_url()}{path}",
                headers={"Accept": accept, "X-API-Key": self._api_key()},
                params=params,
            )
            response.raise_for_status()
            return response
        except httpx.TimeoutException as exc:
            raise UnifiProtectError("Protect request timed out") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise UnifiProtectError(
                f"Protect request failed with HTTP {status}", status_code=status
            ) from exc
        except httpx.HTTPError as exc:
            raise UnifiProtectError("Could not connect to UniFi Protect") from exc

    def _base_url(self) -> str:
        if self.config.unifi_connection_mode == "local":
            if not self.config.unifi_local_base_url:
                raise UnifiProtectError("UNIFI_LOCAL_BASE_URL is not configured")
            return self.config.unifi_local_base_url.rstrip("/")

        if not self.console_id:
            raise UnifiProtectError("UNIFI_CONSOLE_ID is not configured")
        console_id = quote(self.console_id, safe="")
        root = self.config.unifi_remote_base_url.rstrip("/")
        return f"{root}/v1/connector/consoles/{console_id}/proxy/protect/integration"

    def _api_key(self) -> str:
        local_secret = self.config.unifi_local_api_key
        use_local_secret = (
            self.config.unifi_connection_mode == "local"
            and local_secret is not None
            and bool(local_secret.get_secret_value())
        )
        secret = local_secret if use_local_secret else self.config.unifi_api_key
        if secret is None or not secret.get_secret_value():
            raise UnifiProtectError("UNIFI_API_KEY is not configured")
        return secret.get_secret_value()

    @staticmethod
    def _camera_name(item: dict[str, object]) -> str:
        value = item.get("name")
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            for key in ("text", "value", "name"):
                nested = value.get(key)
                if isinstance(nested, str) and nested:
                    return nested
        return str(item["id"])

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return str(value) if value is not None else None
