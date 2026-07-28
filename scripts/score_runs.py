"""
Score saved review runs against gold presence labels.

Reads every runs/<doc_id>.json, matches it by doc_id to its record in
data/golden.jsonl, re-runs validation, and reports presence-detection
accuracy separately for the auto-pass and escalated sets. No API calls --
everything comes from the saved run files.

Usage:
    python scripts/score_runs.py
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from schema import ReviewResult
from validate import validate

RUNS_DIR = Path("runs")
GOLDEN_PATH = Path("data/golden.jsonl")


def load_golden() -> dict:
    golden = {}
    with open(GOLDEN_PATH) as f:
        for line in f:
            record = json.loads(line)
            golden[record["doc_id"]] = record
    return golden


def load_runs() -> list[ReviewResult]:
    results = []
    for path in sorted(RUNS_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        results.append(ReviewResult(**data))
    return results


def classify(predicted: bool, gold: bool) -> str:
    if predicted and gold:
        return "tp"
    if predicted and not gold:
        return "fp"
    if not predicted and gold:
        return "fn"
    return "tn"


def precision_recall(tp: int, fp: int, fn: int) -> tuple:
    precision = tp / (tp + fp) if (tp + fp) else math.nan
    recall = tp / (tp + fn) if (tp + fn) else math.nan
    return precision, recall


def fmt(value: float) -> str:
    return "n/a" if math.isnan(value) else f"{value:.3f}"


def report_set(name: str, rows: list) -> None:
    tp = sum(1 for r in rows if r["outcome"] == "tp")
    fp = sum(1 for r in rows if r["outcome"] == "fp")
    fn = sum(1 for r in rows if r["outcome"] == "fn")
    precision, recall = precision_recall(tp, fp, fn)

    print(f"== {name} ==")
    print(f"  n = {len(rows)}")
    print(f"  true positives:  {tp}")
    print(f"  false positives: {fp}")
    print(f"  false negatives: {fn}")
    print(f"  precision: {fmt(precision)}")
    print(f"  recall:    {fmt(recall)}")


def main():
    golden = load_golden()
    results = load_runs()

    rows = []
    missing_gold = []

    for result in results:
        gold_record = golden.get(result.doc_id)
        if gold_record is None:
            missing_gold.append(result.doc_id)
            continue

        verdicts = validate(result, gold_record["source_text"])

        for v in verdicts:
            finding = v.finding
            clause_type = finding.clause_type.value
            gold_label = gold_record["labels"].get(clause_type)
            if gold_label is None:
                continue

            gold_present = gold_label["present"]
            predicted_present = finding.present

            rows.append(
                {
                    "doc_id": result.doc_id,
                    "clause_type": clause_type,
                    "gold": gold_present,
                    "predicted": predicted_present,
                    "verdict": v.verdict,
                    "trigger": v.trigger,
                    "outcome": classify(predicted_present, gold_present),
                }
            )

    if missing_gold:
        print(f"warning: {len(missing_gold)} run(s) had no matching golden record, skipped:")
        for doc_id in missing_gold:
            print(f"  {doc_id}")
        print()

    print(f"Total findings scored: {len(rows)}")
    print()

    auto_pass_rows = [r for r in rows if r["verdict"] == "auto_pass"]
    escalated_rows = [r for r in rows if r["verdict"] == "escalate"]

    report_set("Auto-pass set", auto_pass_rows)
    print()

    report_set("Escalated set", escalated_rows)
    genuine_catches = sum(1 for r in escalated_rows if r["outcome"] in ("fp", "fn"))
    unverifiable = sum(
        1
        for r in escalated_rows
        if r["outcome"] in ("tp", "tn") and r["trigger"] == "redacted_evidence"
    )
    false_alarms = sum(
        1
        for r in escalated_rows
        if r["outcome"] in ("tp", "tn") and r["trigger"] != "redacted_evidence"
    )
    print(f"  genuine catches (model disagreed with gold): {genuine_catches}")
    print(f"  unverifiable (source redacted; model happened to agree with gold): {unverifiable}")
    print(f"  false alarms (model agreed with gold, escalated for a non-redaction reason): {false_alarms}")
    print()

    disagreements = [r for r in rows if r["outcome"] in ("fp", "fn")]
    print(f"== Disagreements with gold ({len(disagreements)}) ==")
    if not disagreements:
        print("  none")
        return

    header = f"{'doc_id':<45} {'clause_type':<28} {'gold':<6} {'pred':<6} {'verdict':<10} trigger"
    print(header)
    print("-" * len(header))
    for r in disagreements:
        print(
            f"{r['doc_id']:<45} {r['clause_type']:<28} {str(r['gold']):<6} "
            f"{str(r['predicted']):<6} {r['verdict']:<10} {r['trigger'] or ''}"
        )


if __name__ == "__main__":
    main()
