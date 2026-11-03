import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from demo.config import Settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.bundle = tempfile.NamedTemporaryFile()
        self.environment = {
            "DB_HOST": "example.rds.amazonaws.com",
            "RDS_CA_BUNDLE": self.bundle.name,
            "AWS_REGION": "eu-central-1",
        }

    def tearDown(self):
        self.bundle.close()

    def settings(self, **changes):
        with patch.dict(os.environ, self.environment | changes, clear=True):
            return Settings.from_environment()

    def test_aws_defaults_use_iam_and_full_hostname_verification(self):
        settings = self.settings()
        self.assertEqual(settings.auth, "iam")
        parameters = settings.connection_parameters(username="contoso_app", password="example-token")
        self.assertEqual(parameters["sslmode"], "verify-full")
        self.assertEqual(parameters["sslrootcert"], self.bundle.name)
        self.assertEqual(parameters["connect_timeout"], 5)

    def test_iam_cannot_disable_tls_even_in_local_mode(self):
        with self.assertRaisesRegex(ValueError, "TLS"):
            self.settings(DB_SSLMODE="disable", APP_ENV="local")

    def test_remote_password_mode_cannot_disable_tls(self):
        with self.assertRaisesRegex(ValueError, "TLS"):
            self.settings(DB_AUTH="password", DB_PASSWORD="example", DB_SSLMODE="disable")

    def test_local_password_mode_explicitly_allows_plaintext(self):
        settings = self.settings(DB_AUTH="password", DB_PASSWORD="example", DB_SSLMODE="disable", APP_ENV="local")
        parameters = settings.connection_parameters(username=settings.user, password=settings.password)
        self.assertEqual(parameters["sslmode"], "disable")
        self.assertNotIn("sslrootcert", parameters)
        self.assertNotIn("example", repr(settings).split("host=")[0])

    def test_password_is_not_in_settings_representation(self):
        settings = self.settings(DB_AUTH="password", DB_PASSWORD="test-secret-do-not-log")
        self.assertNotIn("test-secret-do-not-log", repr(settings))

    def test_no_opportunistic_tls_downgrade(self):
        for mode in ["prefer", "allow", "require", "verify-ca"]:
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.settings(DB_SSLMODE=mode)

    def test_missing_host_or_ca_fails_closed(self):
        with self.assertRaises(ValueError):
            self.settings(DB_HOST="")
        with self.assertRaises(ValueError):
            self.settings(RDS_CA_BUNDLE=str(Path(self.bundle.name).with_suffix(".absent")))


if __name__ == "__main__":
    unittest.main()
