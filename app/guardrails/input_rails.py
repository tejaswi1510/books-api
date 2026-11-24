"""Input rails: cheap checks that run BEFORE any money is spent on the model.

These regex heuristics catch the common, low-effort prompt-injection attempts.
They are a first layer only and can be bypassed by a determined attacker; the
real protection is layered (see README): instructions kept separate from data,
a model with no tools or secrets, and output rails that validate what comes back.
"""
import logging
import re

from app.exceptions import InputBlockedError

logger = logging.getLogger(__name__)

_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bignore\b.{0,40}\b(previous|prior|above|earlier|all)\b.{0,40}\b(instructions?|rules?|prompts?)\b",
        r"\bdisregard\b.{0,40}\b(instructions?|rules?|prompts?|above|previous)\b",
        r"\b(reveal|show|print|repeat|display|output|leak)\b.{0,30}\b(system|hidden|initial|original)\s+(prompt|instructions?|message)\b",
        r"\byou\s+are\s+now\b",
        r"\bpretend\s+(to\s+be|you\s+are)\b",
        r"\b(developer|debug|jailbreak|god)\s+mode\b",
        r"</?\s*(catalogue|system|assistant)\s*>",  # tries to break out of our <catalogue> block
    ]
]


def check_input(question: str) -> None:
    """Raise InputBlockedError if the question looks unsafe."""
    if any(ord(ch) < 32 and ch not in "\n\r\t" for ch in question):
        logger.warning("guardrail=input_blocked reason=control_characters")
        raise InputBlockedError()

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(question):
            logger.warning("guardrail=input_blocked reason=prompt_injection")
            raise InputBlockedError()
