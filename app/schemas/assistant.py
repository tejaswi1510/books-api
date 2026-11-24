from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AskRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {"question": "Which in-stock science fiction books cost less than $12?"}
        },
    )

    question: str = Field(
        min_length=3,
        max_length=500,
        description="A natural-language question about the book catalogue.",
    )


class AskResponse(BaseModel):
    answer: str = Field(description="The assistant's answer, or a standard refusal message.")
    sources: list[int] = Field(
        description="IDs of the catalogue books the answer is based on (see GET /api/v1/books/{id})."
    )
    refused: bool = Field(description="True when the guardrails or the model declined to answer.")
    refusal_reason: Literal["out_of_scope", "ungrounded", "unsafe_output"] | None = Field(
        default=None, description="Why the question was refused, if it was."
    )
    model: str = Field(description="The exact model that produced the answer.")
    prompt_version: str = Field(
        description="Version of the system prompt used; helps trace behaviour changes."
    )
    books_considered: int = Field(description="How many catalogue rows were given to the model.")
    catalogue_truncated: bool = Field(
        description="True if the catalogue was larger than the configured context limit."
    )
