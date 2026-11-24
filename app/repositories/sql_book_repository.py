"""PostgreSQL-backed implementation of BookRepository."""
import logging

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db import BookRow
from app.repositories.base import BookRepository
from app.schemas.book import Book, BookCreate, BookUpdate

logger = logging.getLogger(__name__)


class SqlBookRepository(BookRepository):
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory
        logger.info("SqlBookRepository ready (PostgreSQL)")

    @staticmethod
    def _to_book(row: BookRow) -> Book:
        return Book.model_validate(row, from_attributes=True)

    def get_all(self) -> list[Book]:
        with self._session_factory() as session:
            rows = session.scalars(select(BookRow).order_by(BookRow.id)).all()
            return [self._to_book(r) for r in rows]

    def get(self, book_id: int) -> Book | None:
        with self._session_factory() as session:
            row = session.get(BookRow, book_id)
            return self._to_book(row) if row else None

    def add(self, data: BookCreate) -> Book:
        with self._session_factory() as session:
            row = BookRow(**data.model_dump())
            session.add(row)
            session.commit()
            return self._to_book(row)

    def replace(self, book_id: int, data: BookUpdate) -> Book | None:
        with self._session_factory() as session:
            row = session.get(BookRow, book_id)
            if row is None:
                return None
            for field, value in data.model_dump().items():
                setattr(row, field, value)
            session.commit()
            return self._to_book(row)

    def delete(self, book_id: int) -> bool:
        with self._session_factory() as session:
            row = session.get(BookRow, book_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True