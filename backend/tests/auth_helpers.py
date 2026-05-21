from flask import Flask

from app.models.user import User
from app.services.jwt_auth import create_token
from tests.conftest import MockDB


def make_auth_app(*blueprints):
    app = Flask(__name__)
    app.config.update(
        AUTH_REQUIRED=True,
        JWT_SECRET="test-secret",
        JWT_EXPIRES_HOURS=1,
        TRANSCRIPTION_DEFAULT_PROVIDER="official",
        TRANSCRIPTION_CLOUD_ENABLED=False,
        TRANSCRIPTION_DEFAULT_LANGUAGE="auto",
        TRANSCRIPTION_AI_NORMALIZE_ENABLED=False,
        AI_ANALYSIS_ENABLED=False,
        MEDIA_ROOT=".",
    )
    app.db = MockDB()
    for blueprint, prefix in blueprints:
        app.register_blueprint(blueprint, url_prefix=prefix)
    return app


def add_user(db, email, role="user"):
    doc = User.create(email, "password123", role=role)
    result = db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def token_for(user):
    return create_token(
        {"sub": str(user["_id"]), "email": user["email"], "role": user["role"]},
        "test-secret",
        1,
    )


def auth_headers(user):
    return {"Authorization": f"Bearer {token_for(user)}"}
