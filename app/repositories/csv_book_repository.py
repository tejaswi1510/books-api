"""CSV-backed implementation of BookRepository.

Writes are guarded by a lock and done atomically (temp file + os.replace) so a
crash mid-write cannot corrupt the CSV. To move to a real database later, write
e.g. SqlBookRepository(BookRepository) and change one line in api/deps.py.
"""
import csv
import logging
import os
import threading
from pathlib import Path

from app.repositories.base import BookRepository
from app.schemas.book import Book, BookCreate, BookUpdate

logger = logging.getLogger(__name__)

FIELDNAMES = ["id", "title", "author", "genre", "published_year", "price", "in_stock"]


class CsvBookRepository(BookRepository):
    def __init__(self, csv_path: Path) -> None:
        self._path = Path(csv_path)
        self._lock = threading.RLock()
        if not self._path.exists():
            logger.warning("CSV file %s not found, creating an empty one", self._path)
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._write_all([])
        logger.info("CsvBookRepository using %s", self._path)

    # ---- internal helpers -------------------------------------------------
    def _read_all(self) -> list[Book]:
        with self._path.open(newline="", encoding="utf-8") as f:
            return [Book.model_validate(row) for row in csv.DictReader(f)]

    def _write_all(self, books: list[Book]) -> None:
        tmp_path = self._path.with_suffix(".csv.tmp")
        with tmp_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            for book in books:
                row = book.model_dump()
                row["in_stock"] = str(book.in_stock).lower()
                writer.writerow(row)
        os.replace(tmp_path, self._path)

    # ---- BookRepository interface ----------------------------------------
    def get_all(self) -> list[Book]:
        with self._lock:
            return self._read_all()

    def get(self, book_id: int) -> Book | None:
        return next((b for b in self.get_all() if b.id == book_id), None)

    def add(self, data: BookCreate) -> Book:
        with self._lock:
            books = self._read_all()
            new_id = max((b.id for b in books), default=0) + 1
            book = Book(id=new_id, **data.model_dump())
            books.append(book)
            self._write_all(books)
            return book

    def replace(self, book_id: int, data: BookUpdate) -> Book | None:
        with self._lock:
            books = self._read_all()
            for index, existing in enumerate(books):
                if existing.id == book_id:
                    updated = Book(id=book_id, **data.model_dump())
                    books[index] = updated
                    self._write_all(books)
                    return updated
            return None

    def delete(self, book_id: int) -> bool:
        with self._lock:
            books = self._read_all()
            remaining = [b for b in books if b.id != book_id]
            if len(remaining) == len(books):
                return False
            self._write_all(remaining)
            return True
