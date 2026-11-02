import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from db.database import Database
from py.services.auth import LocalAuthService


class LocalAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp.name) / "auth.sqlite3")
        self.database.initialize()
        self.auth = LocalAuthService(self.database.connect)

    def tearDown(self):
        self.temp.cleanup()

    def test_register_creates_account_and_starts_local_session(self):
        user = self.auth.register(
            "Dinesh Kumar", "DINESH@example.com",
            "a-strong-local-password", "a-strong-local-password"
        )
        self.assertEqual(user["email"], "dinesh@example.com")
        self.assertTrue(self.auth.state()["authenticated"])
        with closing(self.database.connect()) as db:
            row = db.execute(
                "SELECT password_hash, password_salt FROM users WHERE email=?",
                ("dinesh@example.com",),
            ).fetchone()
        self.assertNotEqual(row["password_hash"], "a-strong-local-password")
        self.assertNotEqual(row["password_salt"], "")

    def test_login_accepts_normalized_email_and_correct_password(self):
        self.auth.register(
            "Dinesh", "dinesh@example.com",
            "a-strong-local-password", "a-strong-local-password"
        )
        self.auth.logout()
        second_session = LocalAuthService(self.database.connect)
        user = second_session.login(" DINESH@EXAMPLE.COM ", "a-strong-local-password")
        self.assertEqual(user["full_name"], "Dinesh")
        self.assertTrue(second_session.state()["authenticated"])

    def test_second_local_account_cannot_be_created_after_setup(self):
        self.auth.register(
            "Dinesh", "dinesh@example.com",
            "a-strong-local-password", "a-strong-local-password"
        )
        self.auth.logout()
        with self.assertRaises(PermissionError):
            self.auth.register(
                "Another user", "another@example.com",
                "another-strong-password", "another-strong-password"
            )

    def test_weak_password_and_mismatch_are_rejected(self):
        with self.assertRaises(ValueError):
            self.auth.register("Dinesh", "dinesh@example.com", "short", "short")
        with self.assertRaises(ValueError):
            self.auth.register(
                "Dinesh", "dinesh@example.com",
                "a-strong-local-password", "a-different-local-password"
            )

    def test_wrong_password_does_not_create_a_session(self):
        self.auth.register(
            "Dinesh", "dinesh@example.com",
            "a-strong-local-password", "a-strong-local-password"
        )
        self.auth.logout()
        with self.assertRaises(PermissionError):
            self.auth.login("dinesh@example.com", "not-the-password")
        self.assertFalse(self.auth.state()["authenticated"])

    def test_api_guard_can_require_an_authenticated_account(self):
        with self.assertRaises(PermissionError):
            self.auth.require_authenticated()
        self.auth.register(
            "Dinesh", "dinesh@example.com",
            "a-strong-local-password", "a-strong-local-password"
        )
        self.assertEqual(self.auth.require_authenticated()["email"], "dinesh@example.com")


if __name__ == "__main__":
    unittest.main()
