"""Real PostgreSQL tests. Opt in against the dedicated local demo database only."""

import os
from dataclasses import replace
import unittest
from uuid import uuid4

import psycopg
from psycopg import sql

from demo.bootstrap import bootstrap, configure_database
from demo.config import Settings
from demo.db import Database
from demo.server import create_app


@unittest.skipUnless(os.environ.get("RUN_DB_INTEGRATION") == "1", "Set RUN_DB_INTEGRATION=1 for real PostgreSQL tests")
class PostgreSQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = Settings.from_environment()
        if os.environ.get("APP_ENV") != "local" or cls.settings.auth != "password":
            raise RuntimeError("Integration tests require the explicit local password environment")
        bootstrap()
        bootstrap()  # Re-running initialization must preserve the schema and data.
        cls.database = Database(cls.settings)
        cls.client = create_app(cls.database).test_client()
        cls.marker = "integration-" + str(uuid4())

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(**cls.settings.connection_parameters(
            username=os.environ["BOOTSTRAP_DB_USER"], password=os.environ["BOOTSTRAP_DB_PASSWORD"]
        )) as connection:
            connection.execute("DELETE FROM app.messages WHERE body LIKE %s", (cls.marker + "%",))

    def test_post_and_read_back_database_value(self):
        body = self.marker + " PostgreSQL round trip: čřž ✓"
        created = self.client.post("/api/messages", json={"body": body})
        self.assertEqual(created.status_code, 201)
        listed = self.client.get("/api/messages")
        self.assertIn(body, [row["body"] for row in listed.json["messages"]])
        self.assertEqual(self.client.get("/readyz").status_code, 200)

    def test_sql_and_html_payload_is_stored_as_literal_data(self):
        body = self.marker + " '); DROP TABLE app.messages; -- <script>alert(1)</script>"
        created = self.client.post("/api/messages", json={"body": body})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json["message"]["body"], body)
        self.database.ready()

    def test_runtime_role_cannot_create_or_delete(self):
        with self.database.connect() as connection:
            privileges = connection.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                "FROM pg_roles WHERE rolname = current_user"
            ).fetchone()
            self.assertFalse(any(privileges.values()))
        for statement in ["CREATE TABLE app.forbidden_table (id integer)", "DELETE FROM app.messages", "DROP TABLE app.messages"]:
            with self.subTest(statement=statement), self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with self.database.connect() as connection:
                    connection.execute(statement)

    def test_bootstrap_database_owner_does_not_need_postgres_superuser(self):
        """RDS master has CREATEDB/CREATEROLE, but not PostgreSQL SUPERUSER."""
        suffix = uuid4().hex[:12]
        owner, user, database = [prefix + suffix for prefix in ("bootstrap_", "runtime_", "fixture_")]
        owner_password = "local-integration-only"
        with psycopg.connect(**self.settings.connection_parameters(
            username=os.environ["BOOTSTRAP_DB_USER"], password=os.environ["BOOTSTRAP_DB_PASSWORD"]
        ), autocommit=True) as administrator:
            try:
                administrator.execute(sql.SQL("CREATE ROLE {} LOGIN CREATEDB CREATEROLE PASSWORD {}").format(
                    sql.Identifier(owner), sql.Literal(owner_password)
                ))
                administrator.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(database), sql.Identifier(owner)
                ))
                settings = replace(self.settings, database=database, user=user)
                with psycopg.connect(**settings.connection_parameters(
                    username=owner, password=owner_password
                )) as connection:
                    configure_database(connection, settings)
                    configure_database(connection, settings)
                runtime = Database(settings)
                runtime.add_message("Bootstrap succeeded without PostgreSQL SUPERUSER")
                runtime.ready()
            finally:
                administrator.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))
                administrator.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(user)))
                administrator.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(owner)))


if __name__ == "__main__":
    unittest.main()
