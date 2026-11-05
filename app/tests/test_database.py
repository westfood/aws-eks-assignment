import unittest
from unittest.mock import Mock, patch

from demo.config import Settings
from demo.db import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            host="db.example.rds.amazonaws.com", port=5432, database="contoso", user="contoso_app",
            auth="iam", region="eu-north-1", sslmode="verify-full", ca_bundle="/bundle.pem", password=None,
        )

    @patch("demo.db.psycopg.connect")
    @patch("demo.db.boto3.client")
    def test_each_connection_gets_a_fresh_iam_token(self, client, connect):
        client.return_value.generate_db_auth_token.side_effect = ["first-example-token", "second-example-token"]
        database = Database(self.settings)
        database.connect()
        database.connect()
        self.assertEqual(client.call_count, 2)
        calls = connect.call_args_list
        self.assertEqual(calls[0].kwargs["password"], "first-example-token")
        self.assertEqual(calls[1].kwargs["password"], "second-example-token")
        self.assertTrue(all(call.kwargs["sslmode"] == "verify-full" for call in calls))
        client.return_value.generate_db_auth_token.assert_called_with(
            DBHostname=self.settings.host, Port=5432, DBUsername="contoso_app", Region="eu-north-1"
        )

    @patch("demo.db.psycopg.connect")
    @patch("demo.db.boto3.client")
    def test_application_never_fetches_master_secret(self, client, connect):
        client.return_value.generate_db_auth_token.return_value = "example-token"
        Database(self.settings).connect()
        self.assertEqual(client.call_args.args, ("rds",))
        self.assertFalse(client.return_value.get_secret_value.called)

    def test_user_text_is_a_bound_parameter(self):
        database = Database(self.settings)
        connection = Mock()
        connection.execute.return_value.fetchone.return_value = {"id": 1}
        manager = Mock()
        manager.__enter__ = Mock(return_value=connection)
        manager.__exit__ = Mock(return_value=False)
        text = "hello'); DROP TABLE app.messages; --"
        with patch.object(database, "connect", return_value=manager):
            database.add_message(text)
        query, parameters = connection.execute.call_args.args
        self.assertNotIn(text, query)
        self.assertEqual(parameters, (text,))


if __name__ == "__main__":
    unittest.main()
