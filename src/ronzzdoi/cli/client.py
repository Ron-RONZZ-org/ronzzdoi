"""HTTP client for the ronzzdoi API.

Wraps ``httpx.Client`` with authentication, error handling, and
connection management.
"""

from __future__ import annotations

import sys
from typing import Any

import httpx


class RonzzdoiError(Exception):
    """Base exception for CLI-client errors."""


class AuthenticationError(RonzzdoiError):
    """Raised on 401 — invalid or missing API key."""


class PermissionError_(RonzzdoiError):
    """Raised on 403 — API key lacks required permission.

    Named with trailing underscore to avoid shadowing the built-in.
    """


class ConnectionError_(RonzzdoiError):
    """Raised when the server is unreachable."""


class ServerError(RonzzdoiError):
    """Raised on unexpected server-side errors (5xx)."""


class ClientError(RonzzdoiError):
    """Raised on 4xx errors other than 401/403 (e.g. 404, 409, 422)."""


_ERROR_MAP: dict[int, type[RonzzdoiError]] = {
    401: AuthenticationError,
    403: PermissionError_,
}


def _translate_error(status_code: int, detail: str) -> RonzzdoiError:
    """Map an HTTP status code to the appropriate CLI exception."""
    exc_type = _ERROR_MAP.get(status_code, ClientError)
    return exc_type(detail)


class RonzzdoiClient:
    """HTTP client for the ronzzdoi REST API.

    Args:
        server_url: Base URL of the ronzzdoi server (default
            ``http://127.0.0.1:8000``).
        api_key: API key for authentication.  Passed via
            ``Authorization: Bearer <key>`` on every request.
        client: Optional pre-configured ``httpx.Client`` for dependency
            injection (tests inject ``MockTransport``).
    """

    def __init__(
        self,
        server_url: str = "https://doi.ronzz.org:8001",
        api_key: str = "",
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self._client = client or httpx.Client(timeout=30.0)

    # ── Public request methods ─────────────────────────────────────────────

    def get(self, path: str, **kwargs: Any) -> Any:
        """Send a GET request.

        Args:
            path: URL path relative to the server base (e.g. ``/api/v1/doi/10.ronzz/abc``).
            **kwargs: Extra arguments passed to ``httpx.Client.get``.

        Returns:
            Parsed JSON response (dict or list).

        Raises:
            AuthenticationError: On 401.
            PermissionError_: On 403.
            ClientError: On other 4xx.
            ServerError: On 5xx.
            ConnectionError_: On connection failure.
        """
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        """Send a POST request."""
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> Any:
        """Send a PUT request."""
        return self._request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> Any:
        """Send a PATCH request."""
        return self._request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        """Send a DELETE request.

        Returns ``None`` for 204 No Content responses.
        """
        return self._request("DELETE", path, **kwargs)

    # ── Internal ───────────────────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Execute an HTTP request and handle errors."""
        url = f"{self.server_url}{path}"
        headers = kwargs.pop("headers", {})
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = self._client.request(method, url, headers=headers, **kwargs)
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise ConnectionError_(
                f"Could not connect to server at {self.server_url}. Is it running?"
            ) from exc

        # 204 No Content
        if response.status_code == 204:
            return None

        # Parse response body (can be dict or list)
        try:
            body = response.json()
        except Exception:
            body = {"detail": response.text or f"HTTP {response.status_code}"}

        # Extract error detail from dict responses; list = always success
        detail = body.get("detail", "") if isinstance(body, dict) else ""

        if response.status_code >= 500:
            raise ServerError(detail or f"Server error (HTTP {response.status_code})")
        if response.status_code >= 400:
            raise _translate_error(response.status_code, detail)

        return body


__all__ = [
    "RonzzdoiClient",
    "RonzzdoiError",
    "AuthenticationError",
    "PermissionError_",
    "ConnectionError_",
    "ServerError",
    "ClientError",
]
