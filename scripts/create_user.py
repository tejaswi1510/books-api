"""Create a user (run from the project root, venv active, APP_DATABASE_URL set).

Usage:
    python -m scripts.create_user
The password is typed at a hidden prompt, so it never lands in shell history.
"""
import getpass

from sqlalchemy import select

from app.core.config import get_settings
from app.core.passwords import hash_password
from app.db import UserRow, create_db_engine, create_session_factory


def main() -> None:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("APP_DATABASE_URL is not set. Add it to .env first.")

    username = input("Username: ").strip()
    if not username:
        raise SystemExit("Username cannot be empty.")

    role = input("Role (user/admin) [user]: ").strip().lower() or "user"
    if role not in {"user", "admin"}:
        raise SystemExit("Role must be 'user' or 'admin'.")

    password = getpass.getpass("Password (min 8 chars): ")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters.")
    if password != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords do not match.")

    factory = create_session_factory(create_db_engine(settings.database_url))
    with factory() as session:
        if session.scalar(select(UserRow).where(UserRow.username == username)):
            raise SystemExit(f"User '{username}' already exists.")
        session.add(UserRow(username=username, hashed_password=hash_password(password), role=role))
        session.commit()
    print(f"Created {role} '{username}'.")


if __name__ == "__main__":
    main()
