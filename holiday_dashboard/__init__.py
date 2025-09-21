from flask import Flask

from .routes import bp as leave_blueprint


def create_app():
    """Application factory for the leave management service."""
    app = Flask(__name__)
    app.register_blueprint(leave_blueprint)
    return app


__all__ = ["create_app"]
