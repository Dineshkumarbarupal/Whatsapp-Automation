from __future__ import annotations

import re
import threading
import time
import uuid
from copy import deepcopy
from typing import Any


class CaptureSessionError(ValueError):
    pass


class MemberCaptureManager:
    """In-memory OCR batch sessions. Images and raw screenshots are never retained."""

    def __init__(self, ttl_seconds: int = 900):
        self.ttl_seconds = max(60, int(ttl_seconds))
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _candidate_key(candidate: dict[str, Any]) -> str:
        phone = str(candidate.get("phone") or "").strip()
        if phone:
            return f"phone:{phone}"
        name = re.sub(r"\s+", " ", str(candidate.get("display_name") or "")).strip().casefold()
        if not name:
            raise CaptureSessionError("OCR candidate has neither a name nor a phone number.")
        return f"name:{name}"

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [
            key for key, value in self._sessions.items()
            if now - value["created_monotonic"] > self.ttl_seconds
        ]
        for key in expired:
            self._sessions.pop(key, None)

    def start(self, group_name: str) -> dict[str, Any]:
        clean_name = (group_name or "").strip()
        if not clean_name or len(clean_name) > 80:
            raise CaptureSessionError("Enter a group name (1-80 characters) before starting OCR capture.")
        with self._lock:
            self._purge_expired()
            session_id = uuid.uuid4().hex
            self._sessions[session_id] = {
                "group_name": clean_name,
                "created_monotonic": time.monotonic(),
                "pages_captured": 0,
                "candidates": {},
            }
            return {"session_id": session_id, "group_name": clean_name, "pages_captured": 0}

    def add_page(self, session_id: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            self._purge_expired()
            session = self._sessions.get(session_id)
            if not session:
                raise CaptureSessionError("Capture session not found or expired. Start a new session.")
            session["pages_captured"] += 1
            new_count = 0
            for raw in candidates:
                if not isinstance(raw, dict):
                    continue
                try:
                    key = self._candidate_key(raw)
                except CaptureSessionError:
                    continue
                candidate = {
                    "capture_key": key,
                    "display_name": str(raw.get("display_name") or "").strip()[:120],
                    "phone": str(raw.get("phone") or "").strip(),
                    "confidence": max(0.0, min(100.0, float(raw.get("confidence") or 0.0))),
                    "raw_text": str(raw.get("raw_text") or "")[:240],
                    "pages_seen": 1,
                }
                existing = session["candidates"].get(key)
                if existing:
                    existing["pages_seen"] += 1
                    existing["confidence"] = max(existing["confidence"], candidate["confidence"])
                    if len(candidate["display_name"]) > len(existing["display_name"]):
                        existing["display_name"] = candidate["display_name"]
                    if not existing["raw_text"] and candidate["raw_text"]:
                        existing["raw_text"] = candidate["raw_text"]
                else:
                    session["candidates"][key] = candidate
                    new_count += 1
            result = self.review(session_id)
            result["new_candidates_on_page"] = new_count
            return result

    def review(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            self._purge_expired()
            session = self._sessions.get(session_id)
            if not session:
                raise CaptureSessionError("Capture session not found or expired. Start a new session.")
            return {
                "session_id": session_id,
                "group_name": session["group_name"],
                "pages_captured": session["pages_captured"],
                "candidates": deepcopy(list(session["candidates"].values())),
                "candidate_count": len(session["candidates"]),
            }

    def selected(self, session_id: str, capture_keys: list[str]) -> tuple[str, list[dict[str, Any]]]:
        if not isinstance(capture_keys, list) or not capture_keys or len(capture_keys) > 1000:
            raise CaptureSessionError("Select at least one candidate (maximum 1,000 per save).")
        with self._lock:
            review = self.review(session_id)
            by_key = {candidate["capture_key"]: candidate for candidate in review["candidates"]}
            clean_keys = list(dict.fromkeys(str(key) for key in capture_keys))
            unknown = [key for key in clean_keys if key not in by_key]
            if unknown:
                raise CaptureSessionError("One or more selected OCR records are not part of this session.")
            return review["group_name"], [by_key[key] for key in clean_keys]

    def discard(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None
