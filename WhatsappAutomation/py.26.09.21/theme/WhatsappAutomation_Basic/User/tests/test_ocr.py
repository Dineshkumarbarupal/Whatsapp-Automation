import unittest

from py.services.ocr import ScreenOCR


class OCRParsingTests(unittest.TestCase):
    def test_extracts_visible_phone_candidates_without_persisting(self):
        ocr = ScreenOCR()
        results = ocr.extract_candidates("Aman Sharma +91 98765 43210\nNeha Verma +91 98123 45678")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["phone"], "+919876543210")
        self.assertEqual(results[0]["display_name"], "Aman Sharma")

    def test_deduplicates_exact_candidate(self):
        results = ScreenOCR().extract_candidates("Aman +919876543210\nAman +919876543210")
        self.assertEqual(len(results), 1)

    def test_extracts_name_only_visible_entries_and_skips_ui_counters(self):
        results = ScreenOCR().extract_candidates(
            "Participants 37\nGroup info\nAman Sharma\nNeha Verma\nSearch"
        )
        self.assertEqual([row["display_name"] for row in results], ["Aman Sharma", "Neha Verma"])
        self.assertTrue(all(row["phone"] == "" for row in results))

    def test_keeps_best_ocr_confidence_for_duplicate_line(self):
        results = ScreenOCR().extract_candidates(
            "Aman Sharma\nAman Sharma",
            {"Aman Sharma": 82.5},
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["confidence"], 82.5)


if __name__ == "__main__":
    unittest.main()
