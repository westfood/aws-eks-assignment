"""Configuration shared by the runtime application and the bootstrap job."""

from dataclasses import dataclass, field
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    database: str
    user: str
    auth: str
    region: str
    sslmode: str
    ca_bundle: str
    password: str | None = field(repr=False)

    @classmethod
    def from_environment(cls) -> "Settings":
        auth = os.environ.get("DB_AUTH", "iam")
        if auth not in {"iam", "password"}:
            raise ValueError("DB_AUTH must be iam or password")
        host = os.environ.get("DB_HOST", "")
        if not host:
            raise ValueError("DB_HOST is required")
        port = int(os.environ.get("DB_PORT", "5432"))
        if not 1 <= port <= 65535:
            raise ValueError("DB_PORT is outside the valid range")
        sslmode = os.environ.get("DB_SSLMODE", "verify-full")
        local_password = auth == "password" and os.environ.get("APP_ENV") == "local"
        if sslmode != "verify-full" and not (local_password and sslmode == "disable"):
            raise ValueError("Only explicit local password mode may disable database TLS")
        ca_bundle = os.environ.get("RDS_CA_BUNDLE", "/app/certs/global-bundle.pem")
        if sslmode == "verify-full" and not Path(ca_bundle).is_file():
            raise ValueError("RDS_CA_BUNDLE must identify a readable CA bundle")
        password = os.environ.get("DB_PASSWORD")
        if auth == "password" and not password:
            raise ValueError("DB_PASSWORD is required for password authentication")
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "eu-central-1")
        return cls(
            host=host,
            port=port,
            database=os.environ.get("DB_NAME", "contoso"),
            user=os.environ.get("DB_USER", "contoso_app"),
            auth=auth,
            region=region,
            sslmode=sslmode,
            ca_bundle=ca_bundle,
            password=password,
        )

    def connection_parameters(self, *, username: str, password: str) -> dict:
        parameters = {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": username,
            "password": password,
            "sslmode": self.sslmode,
            "connect_timeout": 5,
            "application_name": "contoso-demo",
            "options": "-c statement_timeout=5000 -c lock_timeout=3000 -c idle_in_transaction_session_timeout=10000",
        }
        if self.sslmode == "verify-full":
            parameters["sslrootcert"] = self.ca_bundle
        return parameters
