from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps import BookServiceDep
from app.schemas.book import Book, BookCreate, BookList, BookPatch, BookUpdate
from app.schemas.common import ErrorResponse
from app.services.book_service import SortField, SortOrder
from app.core.security import require_api_key

router = APIRouter(prefix="/books", tags=["Books"])

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Book not found"}}
PROTECTED = [Depends(require_api_key)]
# Handlers are plain `def` (not async) because the CSV I/O is blocking;
# FastAPI runs them in a threadpool so the event loop is never blocked.


@router.get("", response_model=BookList, summary="List books")
def list_books(
    service: BookServiceDep,
    genre: Annotated[str | None, Query(description="Exact genre, case-insensitive")] = None,
    author: Annotated[str | None, Query(description="Author name contains")] = None,
    search: Annotated[str | None, Query(description="Search in title or author")] = None,
    in_stock: Annotated[bool | None, Query(description="Filter by availability")] = None,
    sort_by: SortField = "id",
    order: SortOrder = "asc",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> BookList:
    """Return a paginated, filterable, sortable list of books."""
    return service.list_books(
        genre=genre,
        author=author,
        search=search,
        in_stock=in_stock,
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )


@router.get("/{book_id}", response_model=Book, responses=NOT_FOUND, summary="Get a book")
def get_book(book_id: int, service: BookServiceDep) -> Book:
    return service.get_book(book_id)


@router.post(
    "",
    response_model=Book,
    status_code=status.HTTP_201_CREATED,
    summary="Create a book",
    dependencies=PROTECTED,
)
def create_book(
    payload: BookCreate, request: Request, response: Response, service: BookServiceDep
) -> Book:
    book = service.create_book(payload)
    response.headers["Location"] = str(request.url_for("get_book", book_id=book.id))
    return book


@router.put(
    "/{book_id}",
    response_model=Book,
    responses=NOT_FOUND,
    summary="Replace a book (full update)",
    dependencies=PROTECTED,
)
def replace_book(book_id: int, payload: BookUpdate, service: BookServiceDep) -> Book:
    return service.replace_book(book_id, payload)


@router.patch(
    "/{book_id}",
    response_model=Book,
    responses=NOT_FOUND,
    summary="Update part of a book",
    dependencies=PROTECTED,
)
def patch_book(book_id: int, payload: BookPatch, service: BookServiceDep) -> Book:
    return service.patch_book(book_id, payload)


@router.delete(
    "/{book_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=NOT_FOUND,
    summary="Delete a book",
    dependencies=PROTECTED,
)
def delete_book(book_id: int, service: BookServiceDep) -> Response:
    service.delete_book(book_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
