"""Argon2id password hashing and password policy."""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import get_settings

_hasher = PasswordHasher()  # argon2id by default


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(hashed: str, password: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def validate_password_policy(password: str) -> list[str]:
    """Return a list of policy violations (empty = acceptable)."""
    problems: list[str] = []
    min_len = get_settings().password_min_length
    if len(password) < min_len:
        problems.append(f"Password must be at least {min_len} characters long.")
    if password.lower() == password or password.upper() == password:
        problems.append("Password must mix upper- and lower-case letters.")
    if not any(c.isdigit() for c in password):
        problems.append("Password must contain at least one digit.")
    return problems
