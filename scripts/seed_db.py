"""Create the books table and load the seed CSV into it (run once).

Usage (project root, venv active, APP_DATABASE_URL set):
    python -m scripts.seed_db
"""
from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.db import BookRow, create_db_engine, create_session_factory
from app.repositories.csv_book_repository import CsvBookRepository


def main() -> None:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("APP_DATABASE_URL is not set. Add it to .env first.")

    engine = create_db_engine(settings.database_url)
    factory = create_session_factory(engine)

    with factory() as session:
        if session.scalar(select(func.count()).select_from(BookRow)):
            print("Table already has data; nothing to do.")
            return

        books = CsvBookRepository(settings.books_csv_path).get_all()
        session.add_all(BookRow(**b.model_dump()) for b in books)
        session.flush()
        # We inserted explicit ids, so move the id counter past them.
        session.execute(
            text("SELECT setval(pg_get_serial_sequence('books', 'id'), (SELECT MAX(id) FROM books))")
        )
        session.commit()
        print(f"Seeded {len(books)} books.")


if __name__ == "__main__":
    main()