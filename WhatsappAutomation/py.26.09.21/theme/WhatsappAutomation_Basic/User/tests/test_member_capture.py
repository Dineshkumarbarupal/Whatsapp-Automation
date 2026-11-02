import unittest
from py.services.member_capture import CaptureSessionError, MemberCaptureManager


class MemberCaptureTests(unittest.TestCase):
    def setUp(self):
        self.manager = MemberCaptureManager()
        self.session = self.manager.start("Community Group")
        self.session_id = self.session["session_id"]

    def test_merges_multiple_visible_pages_and_deduplicates(self):
        first = self.manager.add_page(self.session_id, [
            {"display_name": "Aman Sharma", "phone": "", "confidence": 71},
            {"display_name": "Neha Verma", "phone": "+919876543210", "confidence": 82},
        ])
        self.assertEqual(first["pages_captured"], 1)
        self.assertEqual(first["new_candidates_on_page"], 2)
        second = self.manager.add_page(self.session_id, [
            {"display_name": "Aman Sharma", "phone": "", "confidence": 89},
            {"display_name": "Ravi Kumar", "phone": "", "confidence": 93},
        ])
        self.assertEqual(second["pages_captured"], 2)
        self.assertEqual(second["new_candidates_on_page"], 1)
        self.assertEqual(second["candidate_count"], 3)
        aman = next(row for row in second["candidates"] if row["display_name"] == "Aman Sharma")
        self.assertEqual(aman["pages_seen"], 2)
        self.assertEqual(aman["confidence"], 89)

    def test_selected_keys_must_belong_to_session(self):
        self.manager.add_page(self.session_id, [{"display_name": "Aman Sharma"}])
        with self.assertRaises(CaptureSessionError):
            self.manager.selected(self.session_id, ["name:someone else"])

    def test_discard_removes_in_memory_session(self):
        self.assertTrue(self.manager.discard(self.session_id))
        with self.assertRaises(CaptureSessionError):
            self.manager.review(self.session_id)


if __name__ == "__main__":
    unittest.main()
