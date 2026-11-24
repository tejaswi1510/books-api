"""Provider-agnostic LLM interface. Services depend on this, not on OpenAI directly,
so the provider (or a test fake) can be swapped without touching business logic."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str


class LLMClient(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_message: str) -> LLMResult:
        """Send one system + user message and return the model's text answer.

        Implementations must raise the AI* exceptions from app.exceptions on failure.
        """
