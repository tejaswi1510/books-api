"""Test doubles shared by several test modules."""
import json

from app.clients.llm import LLMClient, LLMResult


def llm_json(answer: str = "", book_ids=(), in_scope: bool = True) -> str:
    """Build the JSON string a well-behaved model would return."""
    return json.dumps({"in_scope": in_scope, "answer": answer, "book_ids": list(book_ids)})


class FakeLLM(LLMClient):
    """Stands in for OpenAI so tests are free, fast and offline."""

    def __init__(self, reply: str | None = None, error: Exception | None = None):
        self.reply = reply if reply is not None else llm_json("Dune costs $12.99.", [3])
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_message: str) -> LLMResult:
        self.calls.append((system_prompt, user_message))
        if self.error:
            raise self.error
        return LLMResult(text=self.reply, model="fake-model")
