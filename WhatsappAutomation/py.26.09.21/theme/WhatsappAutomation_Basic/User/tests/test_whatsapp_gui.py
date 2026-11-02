import unittest

from py.services.whatsapp_gui import WhatsAppGUIDriver


class GUIDriverValidationTests(unittest.TestCase):
    def setUp(self):
        self.driver = WhatsAppGUIDriver()

    def test_validates_and_deduplicates_participants(self):
        numbers = self.driver._validate_participants(["+91 98765 43210", "+919876543210"])
        self.assertEqual(numbers, ["+919876543210"])

    def test_rejects_more_than_twenty_participants(self):
        with self.assertRaises(ValueError):
            self.driver._validate_participants([f"+1202555{i:04d}" for i in range(21)])

    def test_rejects_invalid_number(self):
        with self.assertRaises(ValueError):
            self.driver._validate_participants(["not-a-phone"])


if __name__ == "__main__":
    unittest.main()
