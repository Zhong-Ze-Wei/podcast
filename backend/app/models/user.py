# -*- coding: utf-8 -*-
"""
User model for first-party accounts.
"""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


class User:
    ROLE_USER = "user"
    ROLE_VIEWER = "viewer"
    ROLE_ADMIN = "admin"

    STATUS_ACTIVE = "active"
    STATUS_DISABLED = "disabled"

    @staticmethod
    def create(email: str, password: str, role: str = ROLE_USER, **kwargs) -> dict:
        now = datetime.utcnow()
        normalized_email = User.normalize_email(email)
        return {
            "email": normalized_email,
            "password_hash": generate_password_hash(password),
            "role": role if role in {User.ROLE_USER, User.ROLE_VIEWER, User.ROLE_ADMIN} else User.ROLE_USER,
            "status": kwargs.get("status", User.STATUS_ACTIVE),
            "created_at": now,
            "updated_at": now,
            "last_login_at": None,
        }

    @staticmethod
    def normalize_email(email: str) -> str:
        return str(email or "").strip().lower()

    @staticmethod
    def verify_password(doc: dict, password: str) -> bool:
        if not doc or not password:
            return False
        return check_password_hash(doc.get("password_hash", ""), password)

    @staticmethod
    def to_response(doc: dict) -> dict:
        if not doc:
            return None
        return {
            "id": str(doc.get("_id") or doc.get("id")),
            "email": doc.get("email", ""),
            "role": doc.get("role", User.ROLE_USER),
            "status": doc.get("status", User.STATUS_ACTIVE),
            "created_at": doc.get("created_at").isoformat() + "Z"
            if doc.get("created_at")
            else None,
            "last_login_at": doc.get("last_login_at").isoformat() + "Z"
            if doc.get("last_login_at")
            else None,
        }
