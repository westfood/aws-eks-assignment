"""Short-lived connections avoid keeping an expired IAM token for reconnects."""

import boto3
from botocore.config import Config
import psycopg
from psycopg.rows import dict_row

from .config import Settings


AWS_CLIENT_CONFIG = Config(connect_timeout=3, read_timeout=5, retries={"total_max_attempts": 2})


class Database:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings

    def connect(self):
        settings = self.settings or Settings.from_environment()
        if settings.auth == "iam":
            client = boto3.client("rds", region_name=settings.region, config=AWS_CLIENT_CONFIG)
            password = client.generate_db_auth_token(
                DBHostname=settings.host,
                Port=settings.port,
                DBUsername=settings.user,
                Region=settings.region,
            )
        else:
            password = settings.password
        return psycopg.connect(
            **settings.connection_parameters(username=settings.user, password=password),
            row_factory=dict_row,
        )

    def ready(self) -> None:
        with self.connect() as connection:
            # Check both the database connection and the schema created by bootstrap.
            connection.execute("SELECT id FROM app.messages LIMIT 1").fetchall()

    def list_messages(self) -> list[dict]:
        with self.connect() as connection:
            return connection.execute(
                "SELECT id, body, created_at FROM app.messages ORDER BY id DESC LIMIT 50"
            ).fetchall()

    def add_message(self, body: str) -> dict:
        with self.connect() as connection:
            return connection.execute(
                "INSERT INTO app.messages (body) VALUES (%s) RETURNING id, body, created_at",
                (body,),
            ).fetchone()
