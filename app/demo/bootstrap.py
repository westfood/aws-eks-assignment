"""Initialize a dedicated schema and a restricted application database role.

AWS mode reads the RDS-managed master secret only in this short-lived job. The
normal application role uses RDS IAM authentication and cannot read that secret.
"""

import json
import logging
import os

import boto3
import psycopg
from psycopg import sql

from .config import Settings
from .db import AWS_CLIENT_CONFIG


def configure_database(connection, settings: Settings) -> None:
    role = sql.Identifier(settings.user)
    database = sql.Identifier(settings.database)
    with connection.transaction():
        attributes = connection.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
            "FROM pg_roles WHERE rolname = %s", (settings.user,)
        ).fetchone()
        if attributes is None:
            # PostgreSQL defaults all elevated role attributes to false. RDS's
            # master user is not a PostgreSQL superuser, so do not issue ALTER
            # ROLE NOSUPERUSER/NOREPLICATION/NOBYPASSRLS even with false values.
            connection.execute(sql.SQL("CREATE ROLE {} LOGIN").format(role))
        elif any(attributes):
            raise ValueError("The application role already has elevated privileges")
        memberships = connection.execute(
            "SELECT parent.rolname FROM pg_auth_members membership "
            "JOIN pg_roles parent ON parent.oid = membership.roleid "
            "JOIN pg_roles member ON member.oid = membership.member "
            "WHERE member.rolname = %s", (settings.user,)
        ).fetchall()
        allowed_memberships = {"rds_iam"} if settings.auth == "iam" else set()
        if any(name not in allowed_memberships for (name,) in memberships):
            raise ValueError("The application role already has unexpected role memberships")
        connection.execute(sql.SQL("ALTER ROLE {} LOGIN").format(role))
        if settings.auth == "iam":
            connection.execute(sql.SQL("ALTER ROLE {} PASSWORD NULL").format(role))
            connection.execute(sql.SQL("GRANT rds_iam TO {}").format(role))
        else:
            # SQL literals are quoted by psycopg; no string interpolation of credentials.
            connection.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(role, sql.Literal(settings.password)))
        connection.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
        connection.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(database))
        connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(database, role))
        connection.execute("CREATE SCHEMA IF NOT EXISTS app")
        connection.execute("REVOKE ALL ON SCHEMA app FROM PUBLIC")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS app.messages ("
            "id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, "
            "body text NOT NULL CHECK (char_length(body) BETWEEN 1 AND 512), "
            "created_at timestamptz NOT NULL DEFAULT now())"
        )
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA app TO {}").format(role))
        connection.execute(sql.SQL("GRANT SELECT, INSERT ON app.messages TO {}").format(role))
        connection.execute(sql.SQL("GRANT USAGE, SELECT ON SEQUENCE app.messages_id_seq TO {}").format(role))


def bootstrap() -> None:
    settings = Settings.from_environment()
    if settings.auth == "iam":
        secret_arn = os.environ.get("BOOTSTRAP_SECRET_ARN")
        if not secret_arn:
            raise ValueError("BOOTSTRAP_SECRET_ARN is required")
        client = boto3.client("secretsmanager", region_name=settings.region, config=AWS_CLIENT_CONFIG)
        secret = json.loads(client.get_secret_value(SecretId=secret_arn)["SecretString"])
        username, password = secret["username"], secret["password"]
    else:
        username = os.environ["BOOTSTRAP_DB_USER"]
        password = os.environ["BOOTSTRAP_DB_PASSWORD"]
    with psycopg.connect(**settings.connection_parameters(username=username, password=password)) as connection:
        configure_database(connection, settings)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        bootstrap()
    except Exception:
        # PostgreSQL exceptions may contain SQL/connection details. Do not emit them.
        logging.error("Database initialization failed; check configuration, identity permissions and connectivity")
        return 1
    logging.info("Database schema and application role initialized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
