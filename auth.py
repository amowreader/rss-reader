"""
Minimal session-based auth. No email verification, no password reset,
no OAuth — just username + password, hashed, stored in a session cookie.
Add the rest later if you need it; this is the floor, not the ceiling.
"""

import functools

from flask import g, redirect, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def log_in_user(user_id: int) -> None:
    session.clear()
    session["user_id"] = user_id


def log_out_user() -> None:
    session.clear()


def require_login(view):
    """Route decorator: redirect to /login if no user is in the session."""

    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped
