"""
Run the harness over a subset of the golden set and report validation outcomes.

Usage:
    python scripts/run_batch.py --limit 5
    python scripts/run_batch.py --limit 5 --doc-ids Healthcentral,Cardax,IbioInc
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import anthropic
from dotenv import load_dotenv

from review import GOLDEN_PATH, call_model
from validate import validate

RUNS_DIR = Path("runs")
TRIGGERS = ["elided_evidence", "evidence_not_grounded", "low_confidence", "reasoning_contains_quote"]


def load_records(path: Path, limit: int, doc_id_prefixes: list[str] | None) -> list[dict]:
    records = []
    with open(path) as f:
        for line in f:
            record = json.loads(line)
            if doc_id_prefixes and not any(record["doc_id"].startswith(p) for p in doc_id_prefixes):
                continue
            records.append(record)
            if len(records) >= limit:
                break
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5, help="max contracts to process (cost control)")
    parser.add_argument(
        "--doc-ids",
        type=str,
        default=None,
        help="comma-separated doc_id prefixes to filter to",
    )
    args = parser.parse_args()

    doc_id_prefixes = [p.strip() for p in args.doc_ids.split(",")] if args.doc_ids else None

    load_dotenv()
    client = anthropic.Anthropic()

    records = load_records(GOLDEN_PATH, args.limit, doc_id_prefixes)

    RUNS_DIR.mkdir(exist_ok=True)

    total_findings = 0
    auto_pass_count = 0
    escalate_count = 0
    trigger_counts = Counter()
    elided_survivors = []

    for record in records:
        result = call_model(client, record["source_text"])
        if result is None:
            print(f"{record['doc_id']}: schema/parse failure after retry -- skipped")
            continue
        result.doc_id = record["doc_id"]

        (RUNS_DIR / f"{result.doc_id}.json").write_text(result.model_dump_json(indent=2))

        verdicts = validate(result, record["source_text"])
        for v in verdicts:
            total_findings += 1
            if v.verdict == "auto_pass":
                auto_pass_count += 1
            else:
                escalate_count += 1
                trigger_counts[v.trigger] += 1
                if v.trigger == "elided_evidence":
                    elided_survivors.append((result.doc_id, v.finding.clause_type.value))

        print(f"{result.doc_id}: {len(verdicts)} findings")

    print()
    print(f"{'total findings':<26} {total_findings:>6}")
    print(f"{'auto-pass':<26} {auto_pass_count:>6}")
    print(f"{'escalated':<26} {escalate_count:>6}")
    print()
    print("by trigger:")
    for t in TRIGGERS:
        print(f"  {t:<28} {trigger_counts.get(t, 0):>6}")

    rate = (escalate_count / total_findings * 100) if total_findings else 0.0
    print()
    print(f"escalation rate: {rate:.1f}%")

    if elided_survivors:
        print()
        print(f"elided_evidence survivors ({len(elided_survivors)}):")
        for doc_id, clause_type in elided_survivors:
            print(f"  {doc_id}: {clause_type}")


if __name__ == "__main__":
    main()
