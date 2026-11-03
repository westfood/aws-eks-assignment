from datetime import datetime, timezone
import unittest
from unittest.mock import Mock

from demo.server import create_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.database = Mock()
        self.database.list_messages.return_value = []
        self.database.add_message.side_effect = lambda body: {
            "id": 7, "body": body, "created_at": datetime(2026, 11, 3, tzinfo=timezone.utc)
        }
        self.app = create_app(self.database)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_liveness_does_not_contact_database(self):
        self.database.ready.side_effect = RuntimeError("database offline")
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        self.database.ready.assert_not_called()

    def test_readiness_fails_without_database(self):
        self.database.ready.side_effect = RuntimeError("private-connection-details")
        response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private-connection-details", response.get_data(as_text=True))

    def test_readiness_checks_schema(self):
        response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 200)
        self.database.ready.assert_called_once_with()

    def test_write_returns_created_row(self):
        response = self.client.post("/api/messages", json={"body": "  Hello PostgreSQL  "})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["message"]["body"], "Hello PostgreSQL")
        self.assertTrue(response.json["message"]["created_at"].endswith("+00:00"))
        self.database.add_message.assert_called_once_with("Hello PostgreSQL")

    def test_invalid_messages_are_rejected_before_database(self):
        for payload in [{}, {"body": " "}, {"body": "x" * 513}, {"body": 4}, {"body": "test", "extra": True}, ["test"], None]:
            with self.subTest(payload_type=type(payload).__name__):
                response = self.client.post("/api/messages", json=payload)
                self.assertEqual(response.status_code, 400)
        self.database.add_message.assert_not_called()

    def test_malformed_json_and_wrong_content_type_are_rejected(self):
        for body, content_type in [("{broken", "application/json"), ("hello", "text/plain")]:
            response = self.client.post("/api/messages", data=body, content_type=content_type)
            self.assertEqual(response.status_code, 400)
        self.database.add_message.assert_not_called()

    def test_large_request_is_rejected(self):
        response = self.client.post("/api/messages", data='{"body":"' + "x" * 10000 + '"}', content_type="application/json")
        self.assertEqual(response.status_code, 413)
        self.database.add_message.assert_not_called()

    def test_database_error_is_not_disclosed(self):
        self.database.add_message.side_effect = RuntimeError("password=example-sensitive-value")
        response = self.client.post("/api/messages", json={"body": "test"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("example-sensitive-value", response.get_data(as_text=True))

    def test_frontend_and_api_have_browser_security_headers(self):
        for path in ["/", "/api/messages"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                response.close()
        self.assertEqual(self.client.get("/api/messages").headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
