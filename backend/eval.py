"""Accuracy evaluation against a hand-labeled answer key (docs/Loom_Source_of_Truth.md,
Evaluation Strategy). Runs the real pipeline (validate -> preprocess -> classify;
no executive summary, since accuracy is a classification-only concern) over a
feedback CSV, joins the results against an answer-key CSV by `id`, and reports
correct/total accuracy overall, per expected category, and per expected theme.

Hold-out discipline: the classification prompt (prompts/classification.py)
uses no few-shot examples at all, so there is nothing to exclude here — every
labeled ticket is genuinely held-out.

Answer-key rows marked "SKIP" (see data/loom_answer_key_100.csv) are rows the
input CSV expects validate_csv() to reject before classification (empty/blank
feedback) — never scored for classification accuracy; instead checked that
they really were skipped, since a "SKIP" ticket that got classified anyway
would itself be a bug.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

from pipeline.classify import classify_batch  # noqa: E402
from pipeline.preprocess import clean_and_redact, is_long_ticket  # noqa: E402
from pipeline.summarize import maybe_summarize  # noqa: E402
from pipeline.validate import FileValidationError, validate_csv  # noqa: E402
from services.llm_client import LLMClient  # noqa: E402
from utils.config import load_config  # noqa: E402

DEFAULT_FEEDBACK_CSV = Path(__file__).resolve().parent / "data" / "loom_feedback_100.csv"
DEFAULT_ANSWER_KEY_CSV = Path(__file__).resolve().parent / "data" / "loom_answer_key_100.csv"

FIELDS = ["category", "theme", "sentiment", "urgency", "actionable"]


def _load_answer_key(path: Path) -> dict[str, dict]:
    df = pd.read_csv(path)
    expected: dict[str, dict] = {}
    for _, row in df.iterrows():
        expected[str(row["id"])] = {
            "category": row["expected_category"],
            "theme": row["expected_theme"],
            "sentiment": row["expected_sentiment"],
            "urgency": row["expected_urgency"],
            "actionable": row["expected_actionable"],
            "case_type": row.get("case_type", ""),
        }
    return expected


def _actual_value(classification, field: str):
    if field == "category":
        return classification.primary_category.value
    if field == "theme":
        return classification.primary_theme.value
    if field == "sentiment":
        return classification.sentiment.value
    if field == "urgency":
        return classification.urgency.value
    if field == "actionable":
        return classification.actionable
    raise ValueError(field)


def _normalize_actionable(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def run(feedback_csv: Path, answer_key_csv: Path) -> None:
    config = load_config()
    llm_client = LLMClient(
        model=config.llm_model, api_key=config.api_key, timeout=config.request_timeout
    )

    df = pd.read_csv(feedback_csv)
    try:
        report = validate_csv(df)
    except FileValidationError as exc:
        print(f"REJECTED [{exc.code}]: {exc.message}")
        sys.exit(1)

    expected = _load_answer_key(answer_key_csv)

    skipped_ids = {row.ticket_id for row in report.skipped_rows}
    expected_skip_ids = {tid for tid, e in expected.items() if e["category"] == "SKIP"}

    prepared: list[tuple[str, str, str, bool]] = []
    for row in report.valid_rows:
        cleaned = clean_and_redact(row.original_text)
        is_long = is_long_ticket(cleaned, config.long_ticket_word_limit)
        text_to_classify, was_summarized = maybe_summarize(row.ticket_id, cleaned, is_long, llm_client)
        prepared.append((row.ticket_id, text_to_classify, cleaned, was_summarized))

    print(f"Loaded {report.total_rows} rows -> processed {report.processed}, skipped {report.skipped}")
    print(f"Answer key has {len(expected)} labeled rows ({len(expected_skip_ids)} expected-skip)")
    print()

    classifications = classify_batch(prepared, llm_client, max_concurrency=config.max_concurrency)
    by_id = {c.ticket_id: c for c in classifications}

    # Expected-skip check: a labeled "SKIP" row must actually have been
    # skipped by validate_csv, never classified — that would be a real bug,
    # not a scoring nuance.
    wrongly_classified_skips = expected_skip_ids & set(by_id)
    missed_skips = expected_skip_ids - skipped_ids - set(by_id)  # neither skipped nor classified — shouldn't happen
    if wrongly_classified_skips:
        print(f"WARNING: {len(wrongly_classified_skips)} expected-skip ticket(s) were classified anyway: "
              f"{sorted(wrongly_classified_skips)}")
    if missed_skips:
        print(f"WARNING: {len(missed_skips)} expected-skip ticket(s) neither skipped nor classified: "
              f"{sorted(missed_skips)}")

    scorable = {tid: exp for tid, exp in expected.items() if exp["category"] != "SKIP" and tid in by_id}
    unlabeled = [tid for tid in by_id if tid not in expected]

    if not scorable:
        print("No scorable (labeled + classified) tickets found — nothing to evaluate.")
        return

    correct = dict.fromkeys(FIELDS, 0)
    per_category_total: dict[str, int] = {}
    per_category_correct: dict[str, int] = {}
    per_theme_total: dict[str, int] = {}
    per_theme_correct: dict[str, int] = {}
    mismatches: list[str] = []
    # category/theme get one combined mismatch line above (a wrong theme
    # usually means a wrong category too); sentiment/urgency/actionable are
    # independent fields, so each gets its own mismatch list.
    field_mismatches: dict[str, list[str]] = {"sentiment": [], "urgency": [], "actionable": []}

    for tid, exp in scorable.items():
        actual = by_id[tid]
        exp_category = exp["category"]
        exp_theme = exp["theme"]

        per_category_total[exp_category] = per_category_total.get(exp_category, 0) + 1
        per_theme_total[exp_theme] = per_theme_total.get(exp_theme, 0) + 1

        category_ok = _actual_value(actual, "category") == exp_category
        theme_ok = _actual_value(actual, "theme") == exp_theme
        if category_ok:
            correct["category"] += 1
            per_category_correct[exp_category] = per_category_correct.get(exp_category, 0) + 1
        if theme_ok:
            correct["theme"] += 1
            per_theme_correct[exp_theme] = per_theme_correct.get(exp_theme, 0) + 1

        sentiment_actual = _actual_value(actual, "sentiment")
        if sentiment_actual == exp["sentiment"]:
            correct["sentiment"] += 1
        else:
            field_mismatches["sentiment"].append(
                f"  {tid} [{exp['case_type']}]: expected {exp['sentiment']}, got {sentiment_actual}"
            )

        urgency_actual = _actual_value(actual, "urgency")
        if urgency_actual == exp["urgency"]:
            correct["urgency"] += 1
        else:
            field_mismatches["urgency"].append(
                f"  {tid} [{exp['case_type']}]: expected {exp['urgency']}, got {urgency_actual} "
                f"(category: {exp_category}/{exp_theme})"
            )

        actionable_actual = _actual_value(actual, "actionable")
        expected_actionable = _normalize_actionable(exp["actionable"])
        if actionable_actual == expected_actionable:
            correct["actionable"] += 1
        else:
            field_mismatches["actionable"].append(
                f"  {tid} [{exp['case_type']}]: expected {expected_actionable}, got {actionable_actual}"
            )

        if not (category_ok and theme_ok):
            mismatches.append(
                f"  {tid} [{exp['case_type']}]: expected {exp_category}/{exp_theme}, "
                f"got {_actual_value(actual, 'category')}/{_actual_value(actual, 'theme')}"
            )

    total = len(scorable)
    print(f"=== Overall accuracy (n={total}) ===")
    for field in FIELDS:
        pct = 100 * correct[field] / total
        print(f"  {field:<12} {correct[field]:>3}/{total} ({pct:.1f}%)")
    print()

    print("=== Per-category accuracy (category field) ===")
    for category in sorted(per_category_total):
        t = per_category_total[category]
        c = per_category_correct.get(category, 0)
        print(f"  {category:<32} {c:>2}/{t:<2} ({100 * c / t:.1f}%)")
    print()

    print("=== Per-theme accuracy (theme field) ===")
    for theme in sorted(per_theme_total):
        t = per_theme_total[theme]
        c = per_theme_correct.get(theme, 0)
        print(f"  {theme:<28} {c:>2}/{t:<2} ({100 * c / t:.1f}%)")
    print()

    if mismatches:
        print(f"=== Category/theme mismatches ({len(mismatches)}) ===")
        print("\n".join(mismatches))
        print()

    for field in ("sentiment", "urgency", "actionable"):
        rows = field_mismatches[field]
        if rows:
            print(f"=== {field.capitalize()} mismatches ({len(rows)}) ===")
            print("\n".join(rows))
            print()

    if unlabeled:
        print(f"Note: {len(unlabeled)} classified ticket(s) have no answer-key row — not scored: {sorted(unlabeled)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate classification accuracy against a hand-labeled answer key.")
    parser.add_argument("feedback_csv", nargs="?", default=str(DEFAULT_FEEDBACK_CSV))
    parser.add_argument("answer_key_csv", nargs="?", default=str(DEFAULT_ANSWER_KEY_CSV))
    args = parser.parse_args()
    run(Path(args.feedback_csv), Path(args.answer_key_csv))
