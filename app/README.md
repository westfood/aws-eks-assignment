# Contoso demonstration application

A small, same-origin web frontend and Flask API prove the full browser → application → PostgreSQL write/read path. Use synthetic messages only. This exercise intentionally has no user accounts or authorization and is not a production message service.

## Run locally

From the repository root, after completing the mise setup in the [root README](../README.md). This route also requires a running Docker engine and the Compose plugin:

```sh
docker compose up --build -d app
docker compose ps
curl --fail http://127.0.0.1:18080/healthz
curl --fail http://127.0.0.1:18080/readyz
open http://127.0.0.1:18080/
```

The Compose project has its own PostgreSQL container and named volume. The bootstrap container must complete successfully before the app starts. Its example passwords are disposable local values; they are not used in AWS. Both published ports bind to `127.0.0.1` only: app `18080`, PostgreSQL `55432`. Stop these resources with `docker compose down`; the database volume remains for the next run.

The app and bootstrap containers run as UID/GID `10001` with read-only roots, dropped Linux capabilities and a writable `/tmp` tmpfs. Gunicorn's optional control socket is disabled because it otherwise writes below the user's home directory.

## API and probes

| Route | Purpose |
| --- | --- |
| `GET /` | Frontend, served by the same application as the API |
| `GET /healthz` | Process liveness; deliberately independent of PostgreSQL |
| `GET /readyz` | Connect to the database and query the bootstrapped schema; `503` on failure |
| `GET /api/messages` | Latest 50 messages, newest first |
| `POST /api/messages` | JSON `{"body":"A synthetic demo message"}`; returns the stored row with status `201` |

Messages must contain 1–512 characters after trimming. Request bodies are capped at 8 KiB. Browser text is inserted with `textContent`, SQL values use bound parameters, and database errors return generic responses without SQL or credentials. A same-origin Content Security Policy blocks third-party scripts and inline execution. These controls do not replace authentication, rate limiting or data retention requirements for a real application.

Connections have a 5-second connection timeout and a 5-second SQL statement timeout. IAM credential refresh can require a separate STS call. Readiness and load-balancer probe timeouts therefore need more than 5 seconds; liveness does not depend on those external systems. The frontend's displayed milliseconds measure its readiness HTTP round trip, not an isolated database query benchmark.

## AWS identity and database initialization

Runtime command:

```sh
gunicorn --bind 0.0.0.0:8080 --workers 2 --threads 2 \
  --timeout 30 --graceful-timeout 20 --worker-tmp-dir /tmp \
  --no-control-socket --access-logfile - --error-logfile - demo.server:app
```

Bootstrap command:

```sh
python -m demo.bootstrap
```

The normal app creates a fresh RDS IAM authentication token for each new PostgreSQL connection. The SDK obtains AWS credentials through EKS Pod Identity. The app role needs only `rds-db:connect` on the exact DB resource ID and database username; it never retrieves the RDS master secret. A token is used to establish a connection, and its later expiry does not terminate an established session. This deliberately simple demo uses short-lived connections, rather than a production connection pool.

The separate bootstrap Job has a different Pod Identity role. It retrieves only the RDS-managed master secret specified by `BOOTSTRAP_SECRET_ARN`, connects as the database owner, and creates the `app` schema, `app.messages` table and restricted `contoso_app` login. It grants `rds_iam` in AWS, plus database `CONNECT`, schema `USAGE`, table `SELECT`/`INSERT`, and identity-sequence `USAGE`/`SELECT`. The runtime user does not own the schema or table and cannot create, update, delete or drop them. Public database privileges and public-schema creation are revoked. The operation is transactional and idempotent. Existing application roles with elevated attributes or unexpected role memberships cause initialization to fail closed.

RDS's master user is not a PostgreSQL superuser. Initialization therefore creates a login with PostgreSQL's safe default role attributes and validates existing attributes, rather than attempting superuser-only `ALTER ROLE ... NOSUPERUSER` commands.

| Variable | AWS value / meaning |
| --- | --- |
| `DB_AUTH` | `iam` (default); `password` is provided for local testing |
| `DB_HOST` | Required real RDS endpoint; do not substitute a custom DNS alias |
| `DB_PORT` | `5432` by default |
| `DB_NAME` | `contoso` by default |
| `DB_USER` | `contoso_app` by default |
| `AWS_REGION` | Deployment region; `AWS_DEFAULT_REGION` is also supported |
| `DB_SSLMODE` | `verify-full` by default and required in AWS |
| `RDS_CA_BUNDLE` | `/app/certs/global-bundle.pem` by default |
| `BOOTSTRAP_SECRET_ARN` | Bootstrap Job only; RDS-managed master secret ARN |

`DB_PASSWORD`, `BOOTSTRAP_DB_USER` and `BOOTSTRAP_DB_PASSWORD` are used only by the local password setup. Plaintext PostgreSQL is accepted only when all three explicit settings are present: `APP_ENV=local`, `DB_AUTH=password`, `DB_SSLMODE=disable`. IAM mode always verifies TLS and the endpoint hostname.

## Tests

From the repository root, with Docker running:

```sh
mise run app:test
```

The task creates `app/.venv` with the mise-pinned Python (`app:setup`), starts the Compose PostgreSQL on `127.0.0.1:55432`, and runs all 23 tests. GitHub Actions runs the same task. No AWS credentials are needed.

The four PostgreSQL integration tests are for the disposable local database only. They initialize the schema twice, verify real read/write and literal SQL/HTML payload handling, check runtime privilege restrictions, and create/remove a uniquely named database and roles to verify bootstrap without PostgreSQL `SUPERUSER`. They remove only their own marker rows and fixture database/roles.

## Dependency and certificate provenance

Direct package versions were checked against official PyPI metadata on 2026-11-03: [Flask](https://pypi.org/pypi/Flask/3.1.3/json), [Gunicorn](https://pypi.org/pypi/gunicorn/26.2.0/json), [psycopg](https://pypi.org/pypi/psycopg/3.3.7/json), [boto3](https://pypi.org/pypi/boto3/1.43.123/json). `requirements.in` records direct dependencies; `requirements.txt` pins their resolved dependency set. Python and PostgreSQL container references use multi-platform image-index digests resolved from Docker Official Images on the same date. Pins make a build reproducible; review and refresh them for security updates before deployment.

`certs/global-bundle.pem` is the public AWS RDS global CA bundle, downloaded from [AWS's trust store](https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem). Retrieval date, URL and SHA-256 are in `certs/provenance.json`; it contains no private keys. Refresh and review the bundle when AWS announces CA changes.

Relevant primary documentation: [RDS IAM authentication](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html), [RDS PostgreSQL user setup](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.DBAccounts.html), [EKS Pod Identity](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html).
