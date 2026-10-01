"""
PolicyPilot — Flask Application Factory
Creates and configures the Flask app with all routes, CORS, and error handlers.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Optional

from flask import Flask, jsonify, request, g
from flask_cors import CORS

from backend.config import configure_logging, get_logger, get_settings, bind_request_context
from backend.api.routes.auth import auth_bp
from backend.api.routes.chat import chat_bp
from backend.api.routes.documents import documents_bp
from backend.api.routes.admin import admin_bp
from backend.database import health_check as db_health
from backend.rag.embeddings import health_check as embedding_health
from backend.rag.vectorstore import health_check as chroma_health

logger = get_logger(__name__)
settings = get_settings()

# Resolve paths relative to this file (backend/app.py → backend/ → policypilot/)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TEMPLATE_DIR = os.path.join(_BASE_DIR, "frontend", "templates")
_STATIC_DIR = os.path.join(_BASE_DIR, "frontend", "static")


def create_app() -> Flask:
    """Application factory."""
    configure_logging(settings.log_level)

    if settings.langsmith_enabled:
        settings.configure_langsmith()
        logger.info("langsmith_tracing_enabled", project=settings.langsmith_project)

    app = Flask(
        __name__,
        template_folder=_TEMPLATE_DIR,
        static_folder=_STATIC_DIR,
    )
    app.config["SECRET_KEY"] = settings.flask_secret_key
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_size_bytes

    # CORS
    CORS(app, origins=settings.cors_origins_list, supports_credentials=True)

    # ── Request hooks ──────────────────────────────────────────
    @app.before_request
    def before_request():
        g.request_id = bind_request_context()
        g.start_time = time.time()

    @app.after_request
    def after_request(response):
        latency = int((time.time() - getattr(g, "start_time", time.time())) * 1000)
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        response.headers["X-Latency-Ms"] = str(latency)
        return response

    # ── Register blueprints ────────────────────────────────────
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(admin_bp)

    # ── Health endpoint ────────────────────────────────────────
    @app.get("/health")
    def health():
        services = {
            "database": db_health(),
            "chromadb": chroma_health(),
            "embeddings": embedding_health(),
        }
        status = "healthy" if all(services.values()) else "degraded"
        return jsonify({
            "status": status,
            "services": services,
            "version": settings.app_version,
        }), 200 if status == "healthy" else 503

    # ── Error handlers ─────────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "code": "BAD_REQUEST"}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "Authentication required", "code": "UNAUTHORIZED"}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Access forbidden", "code": "FORBIDDEN"}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Resource not found", "code": "NOT_FOUND"}), 404

    @app.errorhandler(413)
    def request_too_large(e):
        return jsonify({"error": f"File too large. Max {settings.max_upload_size_mb}MB", "code": "FILE_TOO_LARGE"}), 413

    @app.errorhandler(500)
    def server_error(e):
        logger.error("unhandled_server_error", error=str(e))
        return jsonify({"error": "Internal server error", "code": "SERVER_ERROR"}), 500

    # ── Frontend routes (Jinja2 templates) ────────────────────
    @app.get("/")
    def index():
        from flask import render_template
        return render_template("index.html")

    @app.get("/chat")
    def chat_page():
        from flask import render_template
        return render_template("chat.html")

    @app.get("/admin")
    def admin_page():
        from flask import render_template
        return render_template("admin.html")

    @app.get("/login")
    def login_page():
        from flask import render_template
        return render_template("login.html")

    logger.info(
        "flask_app_created",
        env=settings.flask_env,
        langsmith=settings.langsmith_enabled,
    )
    return app
