"""Thin CLI: run the full pipeline over a CSV end to end and print
results. This is the spine-verification step (build order step 9) —
FastAPI is deliberately not wired up yet.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

from analytics.aggregate import compute_analytics  # noqa: E402
from pipeline.classify import classify_batch  # noqa: E402
from pipeline.preprocess import clean_and_redact, is_long_ticket  # noqa: E402
from pipeline.summarize import generate_executive_summary, maybe_summarize  # noqa: E402
from pipeline.validate import FileValidationError, validate_csv  # noqa: E402
from services.llm_client import LLMClient  # noqa: E402
from utils.config import load_config  # noqa: E402

DEFAULT_CSV_PATH = Path(__file__).resolve().parent / "data" / "loom_dev_10.csv"


def run(csv_path: Path) -> None:
    config = load_config()
    llm_client = LLMClient(
        model=config.llm_model, api_key=config.api_key, timeout=config.request_timeout
    )

    df = pd.read_csv(csv_path)
    try:
        report = validate_csv(df)
    except FileValidationError as exc:
        print(f"REJECTED [{exc.code}]: {exc.message}")
        sys.exit(1)

    print(f"Loaded {report.total_rows} rows -> processed {report.processed}, skipped {report.skipped}")
    if report.skip_reasons:
        print(f"Skip reasons: {report.skip_reasons}")
    print()

    prepared = []
    for row in report.valid_rows:
        cleaned = clean_and_redact(row.original_text)
        # Single word-count measurement (on cleaned text) drives both the
        # long_ticket warning and the summarization-routing decision.
        if is_long_ticket(cleaned, config.long_ticket_word_limit):
            row.warnings.append("long_ticket")
        text_to_classify, was_summarized = maybe_summarize(
            row.ticket_id, cleaned, "long_ticket" in row.warnings, llm_client
        )
        prepared.append((row.ticket_id, text_to_classify, cleaned, was_summarized, row.warnings))

    start = time.perf_counter()
    classifications = classify_batch(
        [(ticket_id, text, feedback_text, was_summarized)
         for ticket_id, text, feedback_text, was_summarized, _ in prepared],
        llm_client,
        batch_size=config.batch_size,
        max_concurrency=config.max_concurrency,
    )
    elapsed = time.perf_counter() - start

    by_id = {c.ticket_id: c for c in classifications}
    print("=== Per-ticket classification ===")
    for ticket_id, _text, _feedback_text, was_summarized, warnings in prepared:
        c = by_id[ticket_id]
        flags = (["summarized"] if was_summarized else []) + warnings
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        print(f"{ticket_id}{flag_str}")
        print(f"  category:        {c.primary_category.value}")
        print(f"  theme:           {c.primary_theme.value}")
        print(f"  sentiment:       {c.sentiment.value}")
        print(f"  sentiment_score: {c.sentiment_score}")
        print(f"  urgency:         {c.urgency.value}")
        print(f"  actionable:      {c.actionable}")
        for issue in c.additional_issues:
            print(f"  + additional: {issue.category.value} / {issue.theme.value} (urgency={issue.urgency.value})")
        print()

    print(f"Classification time: {elapsed:.2f}s for {len(classifications)} tickets")
    print()

    facts = compute_analytics(classifications, report)
    print("=== Analytics ===")
    for key, value in facts.items():
        print(f"{key}: {value}")
    print()

    summary = generate_executive_summary(facts, llm_client, model=config.summary_model)
    print("=== Executive summary ===")
    print(summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Loom pipeline end-to-end over a CSV.")
    parser.add_argument("csv_path", nargs="?", default=str(DEFAULT_CSV_PATH))
    args = parser.parse_args()
    run(Path(args.csv_path))
