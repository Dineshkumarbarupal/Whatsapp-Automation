import unittest

from py.services.consent import AuthorizationRequired, OperatorAuthorization


class AuthorizationTests(unittest.TestCase):
    def test_requires_explicit_acknowledgement(self):
        gate = OperatorAuthorization()
        with self.assertRaises(AuthorizationRequired):
            gate.require(confirmed_now=True)
        gate.acknowledge(True)
        gate.require(confirmed_now=True)

    def test_requires_current_confirmation_even_after_ack(self):
        gate = OperatorAuthorization()
        gate.acknowledge(True)
        with self.assertRaises(AuthorizationRequired):
            gate.require(confirmed_now=False)


if __name__ == "__main__":
    unittest.main()
