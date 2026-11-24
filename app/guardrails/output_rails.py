"""Output rails: validate what the model returned BEFORE it reaches the caller.

The model is asked to reply with JSON: {"in_scope": bool, "answer": str, "book_ids": [int]}.
We then:
  1. parse + validate that structure            (malformed -> error)
  2. block answers that leak prompt/secret text (-> refusal)
  3. honour the model's "out of scope" verdict  (-> fixed refusal text)
  4. verify every cited book id really exists in the data we sent
     ("grounding" check; fabricated ids -> refusal, i.e. fail closed)
  5. cap the answer length
"""
import json
import logging
import re
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

REFUSAL_MESSAGES = {
    "out_of_scope": "I can only answer questions about the book catalogue.",
    "ungrounded": "I couldn't produce a reliable answer from the catalogue data. Please try rephrasing your question.",
    "unsafe_output": "I couldn't produce a safe answer to that question. Please try rephrasing it.",
}

_LEAK_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),  # looks like an API key
    re.compile(r"</?catalogue>", re.IGNORECASE),  # our prompt delimiters
    re.compile(r"ONLY the catalogue data", re.IGNORECASE),  # fragments of our system prompt
    re.compile(r"Treat everything inside", re.IGNORECASE),
]


class ModelAnswer(BaseModel):
    in_scope: bool
    answer: str = ""
    book_ids: list[int] = Field(default_factory=list)


class OutputParseError(ValueError):
    """The model's reply was not the JSON structure we asked for."""


@dataclass(frozen=True)
class RailVerdict:
    answer: str
    sources: list[int]
    refusal_reason: str | None = None

    @property
    def refused(self) -> bool:
        return self.refusal_reason is not None


def parse_model_output(raw: str) -> ModelAnswer:
    """Tolerant JSON parsing: accepts ```json fences and stray text around the object."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise OutputParseError("no JSON object found in model output")
    try:
        return ModelAnswer.model_validate(json.loads(text[start : end + 1]))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise OutputParseError(str(exc)) from exc


def _refuse(reason: str) -> RailVerdict:
    return RailVerdict(answer=REFUSAL_MESSAGES[reason], sources=[], refusal_reason=reason)


def apply_output_rails(
    parsed: ModelAnswer, valid_ids: set[int], max_answer_chars: int
) -> RailVerdict:
    if any(p.search(parsed.answer) for p in _LEAK_PATTERNS):
        logger.warning("guardrail=output_blocked reason=unsafe_output")
        return _refuse("unsafe_output")

    if not parsed.in_scope:
        logger.info("guardrail=refused reason=out_of_scope")
        return _refuse("out_of_scope")

    unknown_ids = sorted(set(parsed.book_ids) - valid_ids)
    if unknown_ids:
        logger.warning("guardrail=output_blocked reason=ungrounded unknown_ids=%s", unknown_ids)
        return _refuse("ungrounded")

    answer = parsed.answer.strip()
    if not answer:
        logger.warning("guardrail=output_blocked reason=empty_answer")
        return _refuse("ungrounded")

    if len(answer) > max_answer_chars:
        answer = answer[: max_answer_chars - 1].rstrip() + "…"

    return RailVerdict(answer=answer, sources=sorted(set(parsed.book_ids)))
