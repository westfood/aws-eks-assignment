"""Same-origin frontend and API. The data is deliberately non-sensitive."""

from datetime import datetime
import logging

from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, UnsupportedMediaType

from .db import Database


def serialize_message(message: dict) -> dict:
    created_at = message["created_at"]
    return {
        "id": message["id"],
        "body": message["body"],
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
    }


def create_app(database=None) -> Flask:
    application = Flask(__name__, static_folder="static", static_url_path="/static")
    application.config.update(MAX_CONTENT_LENGTH=8192, JSON_SORT_KEYS=False)
    application.extensions["database"] = database if database is not None else Database()

    @application.after_request
    def security_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.path.startswith("/api/") or request.path.endswith("healthz") or request.path.endswith("readyz"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @application.get("/")
    def index():
        return application.send_static_file("index.html")

    @application.get("/healthz")
    def health():
        # Liveness must not depend on database availability.
        return jsonify(status="healthy"), 200

    @application.get("/readyz")
    def ready():
        try:
            application.extensions["database"].ready()
            return jsonify(status="ready", database="connected"), 200
        except Exception:
            application.logger.warning("Readiness database check failed")
            return jsonify(status="not_ready", database="unavailable"), 503

    @application.get("/api/messages")
    def list_messages():
        try:
            messages = application.extensions["database"].list_messages()
            return jsonify(messages=[serialize_message(message) for message in messages]), 200
        except Exception:
            application.logger.warning("Database read failed")
            return jsonify(error="Database temporarily unavailable"), 503

    @application.post("/api/messages")
    def add_message():
        try:
            payload = request.get_json()
        except (BadRequest, UnsupportedMediaType):
            return jsonify(error="Send a JSON object containing a message"), 400
        if not isinstance(payload, dict) or set(payload) != {"body"}:
            return jsonify(error="Send a JSON object containing only body"), 400
        body = payload.get("body")
        if not isinstance(body, str) or not 1 <= len(body.strip()) <= 512:
            return jsonify(error="Message must contain between 1 and 512 characters"), 400
        try:
            message = application.extensions["database"].add_message(body.strip())
            return jsonify(message=serialize_message(message)), 201
        except Exception:
            application.logger.warning("Database write failed")
            return jsonify(error="Database temporarily unavailable"), 503

    @application.errorhandler(RequestEntityTooLarge)
    def body_too_large(_error):
        return jsonify(error="Request body is too large"), 413

    return application


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
app = create_app()
