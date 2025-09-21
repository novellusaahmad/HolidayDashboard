"""Entry point for running the Flask development server."""

from holiday_dashboard import create_app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
