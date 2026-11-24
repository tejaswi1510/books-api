"""Run the golden-set evaluation against the REAL model and compare with the baseline.

Usage (from the project root, with APP_OPENAI_API_KEY set):
    python -m scripts.run_evals                    # run + compare with evals/baseline.json
    python -m scripts.run_evals --update-baseline  # run + save the result as the new baseline

Costs a few cents per run (about 5 model calls). Exit code is 1 on regressions.
"""
import argparse
import json
import sys
from pathlib import Path

from app.api.deps import get_llm_client
from app.core.config import BASE_DIR, get_settings
from app.core.logging import setup_logging
from app.evals.runner import compare_to_baseline, load_cases, run_suite
from app.exceptions import AINotConfiguredError
from app.repositories.csv_book_repository import CsvBookRepository
from app.services.assistant_service import AssistantService
from app.services.drift_monitor import ModelDriftMonitor

EVALS_DIR = BASE_DIR / "evals"
GOLDEN_SET = EVALS_DIR / "golden_set.json"
FIXTURE_CSV = EVALS_DIR / "fixtures" / "books.csv"  # fixed data, independent of your live CSV
BASELINE = EVALS_DIR / "baseline.json"
RESULTS_DIR = EVALS_DIR / "results"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the AI golden-set evaluation.")
    parser.add_argument("--update-baseline", action="store_true", help="Save this run as the baseline")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging("WARNING")
    try:
        llm = get_llm_client(settings)
    except AINotConfiguredError as exc:
        print(f"Cannot run evals: {exc.message}")
        return 2

    service = AssistantService(
        CsvBookRepository(FIXTURE_CSV),
        llm,
        settings.ai_max_books_in_context,
        settings.ai_max_answer_chars,
        ModelDriftMonitor(),
    )
    suite = run_suite(service, load_cases(GOLDEN_SET))

    print(f"\nModel: {suite.model}   Prompt: {suite.prompt_version}\n")
    for r in suite.results:
        print(f"  {'PASS' if r.passed else 'FAIL'}  {r.id}" + ("" if r.passed else f"  -> {r.detail}"))
    print(f"\nPass rate: {suite.pass_rate:.0%}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = suite.timestamp.replace(":", "-")
    result_file = RESULTS_DIR / f"{stamp}.json"
    result_file.write_text(json.dumps(suite.to_dict(), indent=2), encoding="utf-8")
    print(f"Saved: {result_file}")

    if args.update_baseline:
        BASELINE.write_text(json.dumps(suite.to_dict(), indent=2), encoding="utf-8")
        print(f"Baseline updated: {BASELINE}")
        return 0

    if not BASELINE.exists():
        print("No baseline yet. Run with --update-baseline once you are happy with the results.")
        return 0 if suite.pass_rate == 1.0 else 1

    notes, regressions = compare_to_baseline(suite, json.loads(BASELINE.read_text(encoding="utf-8")))
    for note in notes:
        print(f"NOTE: {note}")
    for cid in regressions:
        print(f"REGRESSION: '{cid}' passed in the baseline but fails now")
    if not regressions:
        print("No regressions vs baseline.")
    return 1 if regressions else 0


if __name__ == "__main__":
    sys.exit(main())
