"""Pydantic models: the API contract (request/response bodies) shown in Swagger."""
from pydantic import BaseModel, ConfigDict, Field, model_validator


class BookBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1, max_length=100)
    genre: str = Field(min_length=1, max_length=50)
    published_year: int = Field(ge=1000, le=2100)
    price: float = Field(ge=0, description="Price in USD")
    in_stock: bool = True


class BookCreate(BookBase):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "title": "The Left Hand of Darkness",
                "author": "Ursula K. Le Guin",
                "genre": "Science Fiction",
                "published_year": 1969,
                "price": 11.99,
                "in_stock": True,
            }
        },
    )


class BookUpdate(BookBase):
    """Full replacement (PUT): every field is required."""


class BookPatch(BaseModel):
    """Partial update (PATCH): send only the fields you want to change."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    author: str | None = Field(default=None, min_length=1, max_length=100)
    genre: str | None = Field(default=None, min_length=1, max_length=50)
    published_year: int | None = Field(default=None, ge=1000, le=2100)
    price: float | None = Field(default=None, ge=0)
    in_stock: bool | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> "BookPatch":
        # Omitting a field means "leave unchanged"; sending null is never valid
        # because none of the stored fields are nullable. Fail early with a 422.
        nulls = sorted(f for f in self.model_fields_set if getattr(self, f) is None)
        if nulls:
            raise ValueError(f"These fields cannot be null: {', '.join(nulls)}")
        return self


class Book(BookBase):
    id: int


class BookList(BaseModel):
    items: list[Book]
    total: int = Field(description="Total matches before pagination")
    limit: int
    offset: int
