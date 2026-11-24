"""Database connection and table definition (PostgreSQL via SQLAlchemy)."""
from sqlalchemy import Boolean, Float, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class BookRow(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    author: Mapped[str] = mapped_column(String(100))
    genre: Mapped[str] = mapped_column(String(50))
    published_year: Mapped[int]
    price: Mapped[float] = mapped_column(Float)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)


def create_db_engine(url: str) -> Engine:
    # pool_pre_ping checks a connection is alive before using it.
    return create_engine(url, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(engine, expire_on_commit=False)