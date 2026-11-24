from pathlib import Path

from app.clients.llm import LLMClient, LLMResult
from app.evals.runner import compare_to_baseline, load_cases, run_suite
from app.repositories.csv_book_repository import CsvBookRepository
from app.services.assistant_service import AssistantService
from app.services.drift_monitor import ModelDriftMonitor
from tests.fakes import llm_json

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "evals" / "golden_set.json"
FIXTURE_CSV = ROOT / "evals" / "fixtures" / "books.csv"

GOOD_REPLIES = {
    "How many books": llm_json("There are 12 books in the catalogue.", []),
    "most expensive": llm_json("Designing Data-Intensive Applications ($44.99).", [12]),
    "Who wrote Dune": llm_json("Dune was written by Frank Herbert.", [3]),
    "out of stock": llm_json("A Wizard of Earthsea and Educated are out of stock.", [5, 9]),
    "weather": llm_json(in_scope=False),
    "pizza": llm_json(in_scope=False),
}


class ScriptedLLM(LLMClient):
    """Replies based on keywords in the question; `drifted=True` simulates a degraded model."""

    def __init__(self, drifted: bool = False, model: str = "model-v1"):
        self.drifted = drifted
        self.model = model

    def complete(self, system_prompt, user_message):
        if self.drifted:
            return LLMResult(llm_json("I am not sure.", []), self.model)
        for keyword, reply in GOOD_REPLIES.items():
            if keyword.lower() in user_message.lower():
                return LLMResult(reply, self.model)
        raise AssertionError(f"unscripted question: {user_message}")


def make_service(llm):
    return AssistantService(CsvBookRepository(FIXTURE_CSV), llm, 200, 2000, ModelDriftMonitor())


def test_healthy_model_passes_the_whole_golden_set():
    suite = run_suite(make_service(ScriptedLLM()), load_cases(GOLDEN))
    failures = [(r.id, r.detail) for r in suite.results if not r.passed]
    assert failures == []
    assert suite.pass_rate == 1.0


def test_drifted_model_is_detected_as_regression():
    cases = load_cases(GOLDEN)
    baseline = run_suite(make_service(ScriptedLLM()), cases).to_dict()

    drifted = run_suite(make_service(ScriptedLLM(drifted=True, model="model-v2")), cases)
    notes, regressions = compare_to_baseline(drifted, baseline)

    assert "count_books" in regressions and "off_topic_weather" in regressions
    assert "prompt_injection" not in regressions  # the input rail still works
    assert any("model changed" in n for n in notes)


def test_drift_monitor_warns_when_model_snapshot_changes(caplog):
    monitor = ModelDriftMonitor()
    monitor.observe("model-v1")
    monitor.observe("model-v1")
    assert "DRIFT" not in caplog.text
    with caplog.at_level("WARNING"):
        monitor.observe("model-v2")
    assert "DRIFT WARNING" in caplog.text
    assert monitor.snapshot() == {"model-v1": 2, "model-v2": 1}
