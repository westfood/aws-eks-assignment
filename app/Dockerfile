# Multi-platform image index, resolved 2026-11-03 from Docker Official Images.
FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --chown=10001:10001 demo ./demo
COPY --chown=10001:10001 certs ./certs
USER 10001:10001
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "2", "--timeout", "30", "--graceful-timeout", "20", "--worker-tmp-dir", "/tmp", "--no-control-socket", "--access-logfile", "-", "--error-logfile", "-", "demo.server:app"]
