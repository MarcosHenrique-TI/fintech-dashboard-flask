import os
from flask import Flask
from fintech.db import db


def create_app():
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))
    app = Flask(__name__, template_folder=template_dir)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    app.config["DATABASE_URL"] = os.getenv(
        "DATABASE_URL", "postgresql://postgres:1234@localhost:5432/fintech"
    )

    db.init_app(app)
    app.teardown_appcontext(db.put_connection)

    from fintech.routes import bp

    app.register_blueprint(bp)
    return app