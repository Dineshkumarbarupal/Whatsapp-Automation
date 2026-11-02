import tempfile
import unittest
from pathlib import Path

from db.database import Database
from db.repositories import Repository


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp.name) / "test.sqlite3")
        self.database.initialize()
        self.repo = Repository(self.database.connect)

    def tearDown(self):
        self.temp.cleanup()

    def test_schema_health_and_dashboard_counts(self):
        self.assertTrue(self.database.health()["ok"])
        self.assertEqual(self.repo.dashboard_stats()["groups"], 0)

    def test_create_group_member_and_link(self):
        group_id = self.repo.create_group("Project Alpha", "Test group")
        member_id = self.repo.upsert_member("+919876543210", "Aman", "granted", "test")
        self.repo.link_member(group_id, member_id)
        self.assertEqual(self.repo.dashboard_stats(), {
            "groups": 1, "members": 1, "linked_members": 1, "automation_runs": 0
        })
        self.assertEqual(self.repo.list_groups()[0]["member_count"], 1)

    def test_group_name_is_unique_case_insensitively(self):
        self.repo.create_group("Project Alpha")
        with self.assertRaises(Exception):
            self.repo.create_group("project alpha")

    def test_group_observations_save_and_merge_name_only_and_phone_rows(self):
        candidates = [
            {"capture_key": "name:aman sharma", "display_name": "Aman Sharma", "phone": "", "confidence": 77.0, "pages_seen": 2},
            {"capture_key": "phone:+919876543210", "display_name": "Neha Verma", "phone": "+919876543210", "confidence": 91.0, "pages_seen": 1},
        ]
        result = self.repo.save_member_observations("Community Group", candidates)
        self.assertEqual(result["saved"], 2)
        self.repo.save_member_observations("community group", [
            {"capture_key": "name:aman sharma", "display_name": "Aman Sharma", "phone": "", "confidence": 88.0, "pages_seen": 1}
        ])
        rows = self.repo.list_member_observations("Community")
        self.assertEqual(len(rows), 2)
        aman = next(row for row in rows if row["display_name"] == "Aman Sharma")
        self.assertEqual(aman["pages_seen"], 3)
        self.assertEqual(aman["confidence"], 88.0)
        self.assertEqual(aman["phone"], "")


if __name__ == "__main__":
    unittest.main()
