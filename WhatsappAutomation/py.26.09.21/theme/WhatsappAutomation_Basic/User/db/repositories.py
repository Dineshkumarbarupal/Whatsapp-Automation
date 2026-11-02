from __future__ import annotations

from contextlib import contextmanager
from typing import Any


class Repository:
    def __init__(self, connection_factory):
        self._connect = connection_factory

    @contextmanager
    def _session(self):
        db = self._connect()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def dashboard_stats(self) -> dict[str, int]:
        with self._session() as db:
            return {
                "groups": db.execute("SELECT COUNT(*) FROM groups").fetchone()[0],
                "members": db.execute("SELECT COUNT(*) FROM members").fetchone()[0],
                "linked_members": db.execute("SELECT COUNT(*) FROM group_members").fetchone()[0],
                "automation_runs": db.execute("SELECT COUNT(*) FROM automation_runs").fetchone()[0],
            }

    def list_groups(self, search: str = "") -> list[dict[str, Any]]:
        query = """SELECT g.id, g.name, g.description, g.whatsapp_status, g.created_at,
                   COUNT(gm.member_id) AS member_count
                   FROM groups g LEFT JOIN group_members gm ON gm.group_id = g.id
                   WHERE (? = '' OR g.name LIKE ? OR g.description LIKE ?)
                   GROUP BY g.id ORDER BY g.updated_at DESC, g.id DESC"""
        with self._session() as db:
            rows = db.execute(query, (search, f"%{search}%", f"%{search}%")).fetchall()
            return [dict(row) for row in rows]

    def create_group(self, name: str, description: str = "", status: str = "local") -> int:
        with self._session() as db:
            cursor = db.execute(
                "INSERT INTO groups(name, description, whatsapp_status) VALUES (?, ?, ?)",
                (name, description, status),
            )
            return int(cursor.lastrowid)

    def list_members(self, search: str = "") -> list[dict[str, Any]]:
        query = """SELECT m.id, m.phone, m.display_name, m.consent_status, m.source,
                   COUNT(gm.group_id) AS group_count
                   FROM members m LEFT JOIN group_members gm ON gm.member_id = m.id
                   WHERE (? = '' OR m.phone LIKE ? OR m.display_name LIKE ?)
                   GROUP BY m.id ORDER BY m.updated_at DESC, m.id DESC"""
        with self._session() as db:
            rows = db.execute(query, (search, f"%{search}%", f"%{search}%")).fetchall()
            return [dict(row) for row in rows]

    def upsert_member(self, phone: str, display_name: str, consent_status: str,
                      source: str = "manual") -> int:
        with self._session() as db:
            db.execute(
                """INSERT INTO members(phone, display_name, consent_status, source)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(phone) DO UPDATE SET
                     display_name=excluded.display_name,
                     consent_status=excluded.consent_status,
                     source=excluded.source,
                     updated_at=CURRENT_TIMESTAMP""",
                (phone, display_name, consent_status, source),
            )
            row = db.execute("SELECT id FROM members WHERE phone = ?", (phone,)).fetchone()
            return int(row[0])

    def link_member(self, group_id: int, member_id: int) -> None:
        with self._session() as db:
            db.execute(
                "INSERT OR IGNORE INTO group_members(group_id, member_id) VALUES (?, ?)",
                (group_id, member_id),
            )

    def save_member_observations(self, group_name: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        clean_name = (group_name or "").strip()
        if not clean_name or len(clean_name) > 80:
            raise ValueError("Group name must contain 1 to 80 characters.")
        saved = 0
        with self._session() as db:
            group = db.execute("SELECT id FROM groups WHERE name = ? COLLATE NOCASE", (clean_name,)).fetchone()
            if group:
                group_id = int(group[0])
            else:
                cursor = db.execute(
                    "INSERT INTO groups(name, description, whatsapp_status) VALUES (?, ?, 'observed')",
                    (clean_name, "Created from operator-reviewed visible-screen OCR observations"),
                )
                group_id = int(cursor.lastrowid)
            for candidate in candidates:
                display_name = str(candidate.get("display_name") or "").strip()[:120]
                phone = str(candidate.get("phone") or "").strip()[:20]
                capture_key = str(candidate.get("capture_key") or "").strip()[:180]
                if not capture_key or (not display_name and not phone):
                    continue
                try:
                    confidence = max(0.0, min(100.0, float(candidate.get("confidence") or 0.0)))
                    pages_seen = max(1, min(1000, int(candidate.get("pages_seen") or 1)))
                except (TypeError, ValueError) as exc:
                    raise ValueError("Invalid OCR confidence or page count.") from exc
                db.execute(
                    """INSERT INTO member_observations
                       (group_id, capture_key, display_name, phone, confidence, pages_seen, source)
                       VALUES (?, ?, ?, ?, ?, ?, 'screen_ocr')
                       ON CONFLICT(group_id, capture_key) DO UPDATE SET
                         display_name=CASE WHEN length(excluded.display_name)>length(member_observations.display_name)
                                           THEN excluded.display_name ELSE member_observations.display_name END,
                         phone=CASE WHEN excluded.phone<>'' THEN excluded.phone ELSE member_observations.phone END,
                         confidence=MAX(member_observations.confidence, excluded.confidence),
                         pages_seen=member_observations.pages_seen + excluded.pages_seen,
                         last_seen_at=CURRENT_TIMESTAMP""",
                    (group_id, capture_key, display_name, phone, confidence, pages_seen),
                )
                saved += 1
            db.execute("UPDATE groups SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (group_id,))
        return {"group_id": group_id, "group_name": clean_name, "saved": saved}

    def list_member_observations(self, group_name: str = "") -> list[dict[str, Any]]:
        query = """SELECT o.id, g.name AS group_name, o.display_name, o.phone,
                          o.confidence, o.pages_seen, o.source, o.first_seen_at, o.last_seen_at
                   FROM member_observations o JOIN groups g ON g.id=o.group_id
                   WHERE (?='' OR g.name LIKE ?)
                   ORDER BY o.last_seen_at DESC, o.id DESC"""
        with self._session() as db:
            rows = db.execute(query, (group_name, f"%{group_name}%")).fetchall()
            return [dict(row) for row in rows]

    def record_audit(self, event_type: str, status: str, details: str) -> None:
        with self._session() as db:
            db.execute(
                "INSERT INTO audit_events(event_type, status, details) VALUES (?, ?, ?)",
                (event_type, status, details[:1000]),
            )

    def recent_audit(self, limit: int = 12) -> list[dict[str, Any]]:
        with self._session() as db:
            rows = db.execute(
                "SELECT id, event_type, status, details, created_at FROM audit_events "
                "ORDER BY id DESC LIMIT ?", (max(1, min(limit, 100)),)
            ).fetchall()
            return [dict(row) for row in rows]

    def record_run(self, action: str, status: str, summary: str) -> None:
        with self._session() as db:
            db.execute(
                "INSERT INTO automation_runs(action, status, result_summary, finished_at) "
                "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (action, status, summary[:1000]),
            )
