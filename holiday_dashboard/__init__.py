from flask import Flask


from .routes import api_bp, ui_bp



def create_app():
    """Application factory for the leave management service."""
    app = Flask(__name__)

    app.config.setdefault("SECRET_KEY", "leave-dashboard-secret")
    app.register_blueprint(api_bp)
    app.register_blueprint(ui_bp)

    return app


__all__ = ["create_app"]
