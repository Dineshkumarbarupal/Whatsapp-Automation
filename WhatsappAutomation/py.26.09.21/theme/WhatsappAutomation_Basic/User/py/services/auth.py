from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from contextlib import closing
from typing import Any


PASSWORD_ITERATIONS = 600_000
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 256
EMAIL_PATTERN = re.compile(
    r"^[A-Z0-9.!#$%&'*+/=?^`_{}|~-]+@"
    r"[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?"
    r"(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+$",
    re.IGNORECASE,
)
_DUMMY_SALT = b"whatsapp-workspace-dummy-salt"


class LocalAuthService:
    """Single-account local desktop gate; workspace records remain on this PC."""

    def __init__(self, connection_factory):
        self._connect = connection_factory
        self._user_id: int | None = None
        self._failed_attempts = 0
        self._blocked_until = 0.0

    @staticmethod
    def _derive(password: str, salt: bytes, iterations: int = PASSWORD_ITERATIONS) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)

    @staticmethod
    def _public_user(row: Any) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "full_name": str(row["full_name"]),
            "email": str(row["email"]),
        }

    @staticmethod
    def _validate_email(email: str) -> str:
        clean = str(email or "").strip().lower()
        if len(clean) > 254 or not EMAIL_PATTERN.fullmatch(clean):
            raise ValueError("Enter a valid email address.")
        return clean

    @staticmethod
    def _validate_password(password: str) -> str:
        value = str(password or "")
        if len(value) < PASSWORD_MIN_LENGTH:
            raise ValueError("Password must be at least 12 characters long.")
        if len(value) > PASSWORD_MAX_LENGTH:
            raise ValueError("Password must be 256 characters or fewer.")
        return value

    def state(self) -> dict[str, Any]:
        with closing(self._connect()) as db:
            count = int(db.execute("SELECT COUNT(*) FROM users").fetchone()[0])
            user = None
            if self._user_id is not None:
                row = db.execute(
                    "SELECT id, full_name, email FROM users WHERE id = ?",
                    (self._user_id,),
                ).fetchone()
                if row:
                    user = self._public_user(row)
                else:
                    self._user_id = None
        return {
            "authenticated": user is not None,
            "user": user,
            "has_accounts": count > 0,
        }

    def require_authenticated(self) -> dict[str, Any]:
        state = self.state()
        if not state["authenticated"]:
            raise PermissionError("Sign in to access the workspace.")
        return state["user"]

    def register(self, full_name: str, email: str, password: str,
                 confirmation: str) -> dict[str, Any]:
        if self._user_id is not None:
            raise PermissionError("Sign out before creating another local account.")
        name = " ".join(str(full_name or "").split())
        if not name or len(name) > 80:
            raise ValueError("Full name must contain 1 to 80 characters.")
        clean_email = self._validate_email(email)
        clean_password = self._validate_password(password)
        if clean_password != str(confirmation or ""):
            raise ValueError("Password and confirmation do not match.")

        salt = secrets.token_bytes(16)
        digest = self._derive(clean_password, salt).hex()
        with closing(self._connect()) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                existing = db.execute("SELECT 1 FROM users LIMIT 1").fetchone()
                if existing:
                    db.rollback()
                    raise PermissionError(
                        "This workspace already has a local account. Sign in instead."
                    )
                cursor = db.execute(
                    """INSERT INTO users
                       (full_name, email, password_salt, password_hash, password_iterations)
                       VALUES (?, ?, ?, ?, ?)""",
                    (name, clean_email, salt.hex(), digest, PASSWORD_ITERATIONS),
                )
                user_id = int(cursor.lastrowid)
                db.commit()
            except (sqlite3.IntegrityError, PermissionError):
                db.rollback()
                raise
            except Exception:
                db.rollback()
                raise

            row = db.execute(
                "SELECT id, full_name, email FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        self._user_id = user_id
        self._failed_attempts = 0
        self._blocked_until = 0.0
        return self._public_user(row)

    def login(self, email: str, password: str) -> dict[str, Any]:
        if self._user_id is not None:
            raise PermissionError("Sign out before switching local accounts.")
        remaining = self._blocked_until - time.monotonic()
        if remaining > 0:
            raise PermissionError(
                "Too many sign-in attempts. Try again in "
                + str(max(1, int(remaining + 0.99))) + " seconds."
            )

        try:
            clean_email = self._validate_email(email)
        except ValueError:
            clean_email = ""
        supplied = str(password or "")
        if len(supplied) > PASSWORD_MAX_LENGTH:
            supplied = supplied[:PASSWORD_MAX_LENGTH]

        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT id, full_name, email, password_salt, password_hash,
                          password_iterations
                   FROM users WHERE email = ?""",
                (clean_email,),
            ).fetchone()

        if row:
            try:
                salt = bytes.fromhex(str(row["password_salt"]))
                iterations = int(row["password_iterations"])
                expected = bytes.fromhex(str(row["password_hash"]))
                candidate = self._derive(supplied, salt, iterations)
                valid = hmac.compare_digest(candidate, expected)
            except (ValueError, TypeError):
                valid = False
        else:
            self._derive(supplied, _DUMMY_SALT)
            valid = False

        if not valid:
            self._failed_attempts += 1
            if self._failed_attempts >= 5:
                self._failed_attempts = 0
                self._blocked_until = time.monotonic() + 60
                raise PermissionError("Too many sign-in attempts. Try again in 60 seconds.")
            raise PermissionError("Email or password is incorrect.")

        with closing(self._connect()) as db:
            db.execute(
                "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?",
                (int(row["id"]),),
            )
            db.commit()
        self._user_id = int(row["id"])
        self._failed_attempts = 0
        self._blocked_until = 0.0
        return self._public_user(row)

    def logout(self) -> None:
        self._user_id = None
