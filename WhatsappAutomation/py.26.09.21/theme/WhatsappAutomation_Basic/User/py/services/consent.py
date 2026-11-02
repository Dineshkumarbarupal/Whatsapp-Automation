from __future__ import annotations

import threading
import time


class AuthorizationRequired(PermissionError):
    pass


class OperatorAuthorization:
    """Short-lived, explicit local acknowledgement for sensitive operations."""
    def __init__(self, ttl_seconds: int = 1800):
        self._ttl = ttl_seconds
        self._acknowledged_at: float | None = None
        self._lock = threading.Lock()

    def acknowledge(self, confirmed: bool) -> dict[str, object]:
        if confirmed is not True:
            raise AuthorizationRequired("Please confirm you are authorized to manage this group and its data.")
        with self._lock:
            self._acknowledged_at = time.monotonic()
        return {"authorized": True, "expires_in_seconds": self._ttl}

    def require(self, confirmed_now: bool = False) -> None:
        with self._lock:
            active = self._acknowledged_at is not None and (
                time.monotonic() - self._acknowledged_at < self._ttl
            )
        if not active or not confirmed_now:
            raise AuthorizationRequired(
                "Authorization is missing or expired. Confirm authorization in the app before this operation."
            )
