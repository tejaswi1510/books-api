"""Repository interface. Services depend on this, never on a concrete data source."""
from abc import ABC, abstractmethod

from app.schemas.book import Book, BookCreate, BookUpdate


class BookRepository(ABC):
    @abstractmethod
    def get_all(self) -> list[Book]: ...

    @abstractmethod
    def get(self, book_id: int) -> Book | None: ...

    @abstractmethod
    def add(self, data: BookCreate) -> Book: ...

    @abstractmethod
    def replace(self, book_id: int, data: BookUpdate) -> Book | None: ...

    @abstractmethod
    def delete(self, book_id: int) -> bool: ...
