"""
PolicyPilot — Application Entry Point
"""
from backend.app import create_app
from backend.config import get_settings

settings = get_settings()
app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=(settings.flask_env == "development"),
        use_reloader=False,
    )
