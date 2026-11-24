"""Golden-set evaluation: the practical way to detect *drift*.

A fixed list of questions with machine-checkable expectations is run against the
real model. The pass/fail result is stored and compared with a saved baseline, so a
silent model update or prompt change that degrades answers shows up as a regression.

Supported expectations per case:
  must_contain   list[str]  every string must appear in the answer (case-insensitive)
  must_cite_ids  list[int]  these book ids must appear in `sources`
  must_refuse    bool       whether the assistant must refuse (default false)
  expect_error   str        the request must fail with this error code (e.g. input_blocked)
"""
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.exceptions import AppError
from app.services.assistant_service import PROMPT_VERSION, AssistantService


@dataclass(frozen=True)
class EvalCase:
    id: str
    question: str
    expect: dict


@dataclass
class CaseResult:
    id: str
    passed: bool
    detail: str
    answer: str | None = None
    model: str | None = None


@dataclass
class SuiteResult:
    prompt_version: str
    timestamp: str
    results: list[CaseResult]

    @property
    def model(self) -> str | None:
        return next((r.model for r in self.results if r.model), None)

    @property
    def passed_ids(self) -> list[str]:
        return [r.id for r in self.results if r.passed]

    @property
    def pass_rate(self) -> float:
        return len(self.passed_ids) / len(self.results) if self.results else 0.0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "pass_rate": round(self.pass_rate, 4),
            "passed_ids": self.passed_ids,
            "results": [r.__dict__ for r in self.results],
        }


def load_cases(path: Path) -> list[EvalCase]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [EvalCase(c["id"], c["question"], c.get("expect", {})) for c in data["cases"]]


def run_case(service: AssistantService, case: EvalCase) -> CaseResult:
    expected_error = case.expect.get("expect_error")
    try:
        response = service.ask(case.question)
    except AppError as exc:
        if expected_error == exc.code:
            return CaseResult(case.id, True, f"failed with {exc.code} as expected")
        return CaseResult(case.id, False, f"unexpected error: {exc.code}")

    if expected_error:
        return CaseResult(
            case.id, False, f"expected error {expected_error} but got an answer",
            response.answer, response.model,
        )

    problems: list[str] = []
    if case.expect.get("must_refuse", False) != response.refused:
        problems.append("expected a refusal" if case.expect.get("must_refuse") else "unexpected refusal")
    for text in case.expect.get("must_contain", []):
        if text.lower() not in response.answer.lower():
            problems.append(f"answer is missing {text!r}")
    missing_ids = sorted(set(case.expect.get("must_cite_ids", [])) - set(response.sources))
    if missing_ids:
        problems.append(f"did not cite book ids {missing_ids}")

    return CaseResult(
        case.id,
        not problems,
        "ok" if not problems else "; ".join(problems),
        response.answer,
        response.model,
    )


def run_suite(service: AssistantService, cases: list[EvalCase]) -> SuiteResult:
    results = [run_case(service, c) for c in cases]
    return SuiteResult(
        prompt_version=PROMPT_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        results=results,
    )


def compare_to_baseline(current: SuiteResult, baseline: dict) -> tuple[list[str], list[str]]:
    """Return (notes, regressions). Regressions are cases that passed before but fail now."""
    notes: list[str] = []
    if baseline.get("model") != current.model:
        notes.append(f"model changed: {baseline.get('model')} -> {current.model}")
    if baseline.get("prompt_version") != current.prompt_version:
        notes.append(f"prompt version changed: {baseline.get('prompt_version')} -> {current.prompt_version}")
    still_passing = set(current.passed_ids)
    regressions = [cid for cid in baseline.get("passed_ids", []) if cid not in still_passing]
    return notes, regressions
