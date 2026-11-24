"""Business logic layer: filtering, sorting, pagination, and domain errors."""
import logging
from typing import Literal

from app.exceptions import BookNotFoundError
from app.repositories.base import BookRepository
from app.schemas.book import Book, BookCreate, BookList, BookPatch, BookUpdate

logger = logging.getLogger(__name__)

SortField = Literal["id", "title", "author", "published_year", "price"]
SortOrder = Literal["asc", "desc"]


class BookService:
    def __init__(self, repository: BookRepository) -> None:
        self._repo = repository

    def list_books(
        self,
        *,
        genre: str | None = None,
        author: str | None = None,
        search: str | None = None,
        in_stock: bool | None = None,
        sort_by: SortField = "id",
        order: SortOrder = "asc",
        limit: int = 20,
        offset: int = 0,
    ) -> BookList:
        # NOTE: with a real database, push these filters into the query instead.
        books = self._repo.get_all()

        if genre:
            books = [b for b in books if b.genre.lower() == genre.lower()]
        if author:
            books = [b for b in books if author.lower() in b.author.lower()]
        if search:
            q = search.lower()
            books = [b for b in books if q in b.title.lower() or q in b.author.lower()]
        if in_stock is not None:
            books = [b for b in books if b.in_stock == in_stock]

        def sort_key(book: Book):
            value = getattr(book, sort_by)
            return value.lower() if isinstance(value, str) else value

        books.sort(key=sort_key, reverse=(order == "desc"))

        total = len(books)
        page = books[offset : offset + limit]
        logger.info("Listed books: total=%d returned=%d offset=%d", total, len(page), offset)
        return BookList(items=page, total=total, limit=limit, offset=offset)

    def get_book(self, book_id: int) -> Book:
        book = self._repo.get(book_id)
        if book is None:
            logger.warning("Book %d not found", book_id)
            raise BookNotFoundError(book_id)
        return book

    def create_book(self, data: BookCreate) -> Book:
        book = self._repo.add(data)
        logger.info("Created book id=%d title=%r", book.id, book.title)
        return book

    def replace_book(self, book_id: int, data: BookUpdate) -> Book:
        book = self._repo.replace(book_id, data)
        if book is None:
            raise BookNotFoundError(book_id)
        logger.info("Replaced book id=%d", book_id)
        return book

    def patch_book(self, book_id: int, data: BookPatch) -> Book:
        current = self.get_book(book_id)
        changes = data.model_dump(exclude_unset=True)
        merged = {**current.model_dump(), **changes}
        # Re-validate the merged result, then store via the same replace path.
        updated = BookUpdate.model_validate({k: v for k, v in merged.items() if k != "id"})
        book = self._repo.replace(book_id, updated)
        if book is None:  # deleted between read and write
            raise BookNotFoundError(book_id)
        logger.info("Patched book id=%d fields=%s", book_id, sorted(changes))
        return book

    def delete_book(self, book_id: int) -> None:
        if not self._repo.delete(book_id):
            raise BookNotFoundError(book_id)
        logger.info("Deleted book id=%d", book_id)
