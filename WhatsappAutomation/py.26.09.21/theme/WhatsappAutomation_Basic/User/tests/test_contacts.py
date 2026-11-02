import unittest

from py.services.contacts import export_contacts_csv, normalize_phone, parse_contacts_csv, validate_contact


class ContactServiceTests(unittest.TestCase):
    def test_normalize_phone_preserves_plus(self):
        self.assertEqual(normalize_phone("+91 98765-43210"), "+919876543210")

    def test_validate_rejects_invalid_phone(self):
        with self.assertRaises(ValueError):
            validate_contact("123")

    def test_parse_csv_deduplicates_and_tracks_consent(self):
        content = "phone,name,consent\n+919876543210,Aman,yes\n+919876543210,Aman,yes\n123,Bad,no\n"
        records, warnings = parse_contacts_csv(content)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].consent_status, "granted")
        self.assertEqual(len(warnings), 2)

    def test_export_csv_has_expected_columns(self):
        csv_text = export_contacts_csv([{"phone": "+919876543210", "display_name": "Aman", "consent_status": "unknown"}])
        self.assertIn("phone,name,consent,source", csv_text)
        self.assertIn("+919876543210,Aman,unknown", csv_text)


if __name__ == "__main__":
    unittest.main()
