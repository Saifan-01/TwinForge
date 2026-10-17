"""Flask Application Factory for IoT Digital Twin."""

import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()


def create_app(test_config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")

    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-key-12345"),
        MONGO_URI=os.getenv("MONGO_URI", "mongodb://localhost:27017/"),
        DB_NAME=os.getenv("DB_NAME", "iot_digital_twin"),
        API_KEY=os.getenv("API_KEY", ""),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=8 * 3600,
    )

    if test_config:
        app.config.update(test_config)

    from app.auth import api_guard
    app.before_request(api_guard)

    # Register blueprints
    from app.routes.views import bp as views_bp
    from app.routes.api_devices import bp as devices_bp
    from app.routes.api_events import bp as events_bp
    from app.routes.api_analytics import bp as analytics_bp
    from app.routes.api_alerts import bp as alerts_bp
    from app.routes.api_simulator import bp as simulator_bp

    app.register_blueprint(views_bp)
    app.register_blueprint(devices_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(simulator_bp)

    return app
