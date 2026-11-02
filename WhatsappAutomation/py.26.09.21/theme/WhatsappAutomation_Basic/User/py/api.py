from __future__ import annotations

import csv
import io
import logging
from typing import Any

from core.config import DB_PATH, load_settings, save_settings
from db.database import Database
from db.repositories import Repository
from py.services.auth import LocalAuthService
from py.services.consent import OperatorAuthorization
from py.services.contacts import export_contacts_csv, parse_contacts_csv
from py.services.member_capture import MemberCaptureManager
from py.services.ocr import ScreenOCR
from py.services.whatsapp_gui import WhatsAppGUIDriver


class ApplicationServices:
    """Register the authenticated local desktop bridge used by the Eel front end."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.database = Database(DB_PATH)
        self.database.initialize()
        self.repo = Repository(self.database.connect)
        self.auth = LocalAuthService(self.database.connect)
        self.authorization = OperatorAuthorization()
        self.member_captures = MemberCaptureManager(ttl_seconds=900)

    def _ok(self, data: Any = None, message: str = "OK") -> dict[str, Any]:
        return {"ok": True, "message": message, "data": data}

    def _error(self, exc: Exception) -> dict[str, Any]:
        self.logger.warning("Desktop bridge request rejected: %s", exc)
        try:
            self.repo.record_audit("desktop_bridge_error", "error", str(exc))
        except Exception:
            self.logger.exception("Could not record bridge error")
        return {"ok": False, "message": str(exc), "data": None}

    def _guard(self, action, require_auth: bool = True):
        try:
            if require_auth:
                self.auth.require_authenticated()
            return self._ok(action())
        except Exception as exc:
            return self._error(exc)

    def register(self, eel) -> None:
        expose = eel.expose

        @expose
        def get_auth_state():
            return self._guard(self.auth.state, require_auth=False)

        @expose
        def register_account(full_name, email, password, confirm_password):
            def action():
                user = self.auth.register(full_name, email, password, confirm_password)
                self.repo.record_audit(
                    "account_registered", "success",
                    "Created local account: " + user["email"],
                )
                return {"user": user}
            return self._guard(action, require_auth=False)

        @expose
        def login_account(email, password):
            def action():
                user = self.auth.login(email, password)
                self.repo.record_audit(
                    "account_signed_in", "success",
                    "Local account signed in: " + user["email"],
                )
                return {"user": user}
            return self._guard(action, require_auth=False)

        @expose
        def logout_account():
            def action():
                user = self.auth.require_authenticated()
                self.repo.record_audit(
                    "account_signed_out", "success",
                    "Local account signed out: " + user["email"],
                )
                self.auth.logout()
                return {"logged_out": True}
            return self._guard(action, require_auth=False)

        @expose
        def get_dashboard_stats():
            return self._guard(lambda: {**self.repo.dashboard_stats(), "database_ok": self.database.health()["ok"]})

        @expose
        def list_groups(search=""):
            return self._guard(lambda: self.repo.list_groups(str(search)[:100]))

        @expose
        def create_group_record(name, description=""):
            def action():
                clean = str(name or "").strip()
                if not clean or len(clean) > 80:
                    raise ValueError("Group name must contain 1 to 80 characters.")
                group_id = self.repo.create_group(clean, str(description or "")[:500])
                self.repo.record_audit("group_record_created", "success", "Created local group record: " + clean)
                return {"id": group_id}
            return self._guard(action)

        @expose
        def list_members(search=""):
            return self._guard(lambda: self.repo.list_members(str(search)[:100]))

        @expose
        def import_contacts_csv(csv_content):
            def action():
                records, warnings = parse_contacts_csv(str(csv_content or ""))
                imported = 0
                for record in records:
                    self.repo.upsert_member(
                        record.phone, record.display_name, record.consent_status, record.source
                    )
                    imported += 1
                self.repo.record_audit(
                    "contacts_imported", "success", f"Imported {imported} rows; {len(warnings)} warnings."
                )
                return {"imported": imported, "warnings": warnings}
            return self._guard(action)

        @expose
        def export_members_csv():
            return self._guard(lambda: export_contacts_csv(self.repo.list_members()))

        @expose
        def acknowledge_authorization(confirmed):
            def action():
                result = self.authorization.acknowledge(bool(confirmed))
                self.repo.record_audit("operator_authorization", "success", "Operator acknowledged authorized group/data use.")
                return result
            return self._guard(action)

        @expose
        def capture_screen_ocr(confirmed):
            def action():
                self.authorization.require(confirmed_now=bool(confirmed))
                settings = load_settings()
                result = ScreenOCR(
                    settings.get("tesseract_cmd", ""), settings.get("ocr_language", "eng")
                ).capture_and_extract()
                self.repo.record_audit("screen_ocr_preview", "success", f"Generated {result['candidate_count']} review candidates.")
                return result
            return self._guard(action)

        @expose
        def save_ocr_candidates(candidates, group_name, confirmed):
            def action():
                self.authorization.require(confirmed_now=bool(confirmed))
                if not isinstance(candidates, list) or len(candidates) > 500:
                    raise ValueError("Invalid OCR candidate list.")
                group = str(group_name or "").strip()
                if not group or len(group) > 80:
                    raise ValueError("Group label must contain 1 to 80 characters.")
                valid = [item for item in candidates if isinstance(item, dict)]
                result = self.repo.save_member_observations(group, valid)
                self.repo.record_audit("member_observations_saved", "success", f"Saved {result['saved']} reviewed rows.")
                return result
            return self._guard(action)

        @expose
        def start_member_capture(group_name, confirmed):
            def action():
                self.authorization.require(confirmed_now=bool(confirmed))
                result = self.member_captures.start(str(group_name or ""))
                self.repo.record_audit("member_capture_started", "info", "Started visible-list OCR session: " + result["group_name"])
                return result
            return self._guard(action)

        @expose
        def capture_member_page(session_id, confirmed):
            def action():
                self.authorization.require(confirmed_now=bool(confirmed))
                self.member_captures.review(str(session_id))
                settings = load_settings()
                page = ScreenOCR(settings.get("tesseract_cmd", ""), settings.get("ocr_language", "eng")).capture_and_extract()
                result = self.member_captures.add_page(str(session_id), page["candidates"])
                result["page_text"] = page["text"]
                result["image_size"] = page["image_size"]
                result["page_candidate_count"] = page["candidate_count"]
                self.repo.record_audit("member_capture_page", "success", f"Captured page {result['pages_captured']}; total candidates {result['candidate_count']}.")
                return result
            return self._guard(action)

        @expose
        def get_member_capture_review(session_id):
            return self._guard(lambda: self.member_captures.review(str(session_id)))

        @expose
        def save_member_capture(session_id, selected_keys, confirmed):
            def action():
                self.authorization.require(confirmed_now=bool(confirmed))
                group_name, selected = self.member_captures.selected(str(session_id), selected_keys)
                result = self.repo.save_member_observations(group_name, selected)
                self.member_captures.discard(str(session_id))
                self.repo.record_audit("member_observations_saved", "success", f"Saved {result['saved']} reviewed observations.")
                return result
            return self._guard(action)

        @expose
        def discard_member_capture(session_id):
            def action():
                discarded = self.member_captures.discard(str(session_id))
                return {"discarded": discarded}
            return self._guard(action)

        @expose
        def list_member_observations(group_name=""):
            return self._guard(lambda: self.repo.list_member_observations(str(group_name or "")[:80]))

        @expose
        def export_member_observations_csv(group_name=""):
            def action():
                rows = self.repo.list_member_observations(str(group_name or "")[:80])
                output = io.StringIO(newline="")
                fields = ["group_name", "display_name", "phone", "confidence", "pages_seen", "source", "first_seen_at", "last_seen_at"]
                writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
                self.repo.record_audit("member_observations_exported", "success", f"Exported {len(rows)} reviewed observations.")
                return output.getvalue()
            return self._guard(action)

        @expose
        def open_whatsapp_web():
            def action():
                settings = load_settings()
                result = WhatsAppGUIDriver(settings.get("automation_delay_seconds", 1.0)).open_web()
                self.repo.record_audit("whatsapp_web_opened", "info", "Opened WhatsApp Web for manual sign-in.")
                return result
            return self._guard(action)

        @expose
        def create_whatsapp_group(group_name, participants, confirmed):
            def action():
                self.authorization.require(confirmed_now=bool(confirmed))
                if not isinstance(participants, list):
                    raise ValueError("Participants must be a list of phone numbers.")
                driver = WhatsAppGUIDriver(load_settings().get("automation_delay_seconds", 1.0))
                result = driver.create_group(str(group_name), participants)
                self.repo.record_run("create_group", "submitted", result["message"])
                self.repo.record_audit("whatsapp_group_create", "submitted", result["message"])
                return result
            return self._guard(action)

        @expose
        def add_members_to_current_group(participants, confirmed):
            def action():
                self.authorization.require(confirmed_now=bool(confirmed))
                if not isinstance(participants, list):
                    raise ValueError("Participants must be a list of phone numbers.")
                result = WhatsAppGUIDriver(load_settings().get("automation_delay_seconds", 1.0)).add_members_to_current_group(participants)
                self.repo.record_run("add_members", "submitted", result["message"])
                self.repo.record_audit("whatsapp_members_add", "submitted", result["message"])
                return result
            return self._guard(action)

        @expose
        def get_recent_activity():
            return self._guard(self.repo.recent_audit)

        @expose
        def get_settings():
            return self._guard(load_settings)

        @expose
        def update_settings(payload):
            def action():
                if not isinstance(payload, dict):
                    raise ValueError("Settings payload must be an object.")
                updated = save_settings(payload)
                self.repo.record_audit("settings_updated", "success", "Application settings updated.")
                return updated
            return self._guard(action)
