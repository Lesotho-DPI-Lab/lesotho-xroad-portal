import os
import secrets
from datetime import timedelta

from flask import Flask, jsonify, send_from_directory

from .db import close_db, get_db, init_schema


def _secret(instance):
    path = os.path.join(instance, "secret.key")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(secrets.token_hex(32))
        os.chmod(path, 0o600)
    with open(path) as f:
        return f.read().strip()


def create_app():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    instance = os.environ.get("PORTAL_DATA_DIR", os.path.join(base, "instance"))
    os.makedirs(os.path.join(instance, "uploads"), exist_ok=True)

    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config.update(
        DATABASE=os.path.join(instance, "portal.db"),
        UPLOAD_DIR=os.path.join(instance, "uploads"),
        SECRET_KEY=os.environ.get("PORTAL_SECRET_KEY") or _secret(instance),
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_NAME="xrp_session",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        DEMO_PASSWORD=os.environ.get("PORTAL_DEMO_PASSWORD", "Demo@2026"),
        JSON_SORT_KEYS=False,
    )
    app.teardown_appcontext(close_db)

    from .api import bp
    app.register_blueprint(bp)

    with app.app_context():
        db = get_db()
        init_schema(db)
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            from .seed import seed
            seed(app)

    @app.errorhandler(413)
    def too_large(_e):
        return jsonify({"error": "File exceeds the 10 MB limit"}), 413

    @app.after_request
    def headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    return app
