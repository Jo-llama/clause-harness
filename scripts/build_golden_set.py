"""
Build a golden set for the clause-review harness from CUAD v1.

Reads the SQuAD-format CUADv1.json, keeps only the eight clause categories
we care about, and writes one JSON object per contract to data/golden.jsonl.

Usage:
    python scripts/build_golden_set.py --n 50
"""

import argparse
import json
import random
import re
from pathlib import Path

# Maps our schema's clause_type -> the label as it appears in CUAD questions.
CATEGORIES = {
    "governing_law": "Governing Law",
    "cap_on_liability": "Cap On Liability",
    "uncapped_liability": "Uncapped Liability",
    "termination_for_convenience": "Termination For Convenience",
    "anti_assignment": "Anti-Assignment",
    "change_of_control": "Change Of Control",
    "exclusivity": "Exclusivity",
    "non_compete": "Non-Compete",
}

RAW = Path("data/raw/CUADv1.json")
OUT = Path("data/golden.jsonl")


def normalize(text: str) -> str:
    """Collapse whitespace so verbatim comparisons survive PDF extraction noise."""
    return re.sub(r"\s+", " ", text).strip()


def category_of(question: str) -> str | None:
    """CUAD questions embed the label in double quotes: ...related to "Governing Law" that..."""
    match = re.search(r'"([^"]+)"', question)
    if not match:
        return None
    label = match.group(1).strip()
    for key, cuad_label in CATEGORIES.items():
        if label.lower() == cuad_label.lower():
            return key
    return None


def extract_contract(entry: dict) -> dict | None:
    para = entry["paragraphs"][0]
    source_text = para["context"]

    labels = {}
    for qa in para["qas"]:
        key = category_of(qa["question"])
        if key is None:
            continue
        spans = [a["text"] for a in qa.get("answers", []) if a.get("text")]
        labels[key] = {
            "present": bool(spans) and not qa.get("is_impossible", False),
            "evidence": [normalize(s) for s in spans],
        }

    # Skip anything where CUAD didn't cover all eight — keeps the eval honest.
    if len(labels) != len(CATEGORIES):
        return None

    return {
        "doc_id": entry["title"],
        "source_text": source_text,
        "labels": labels,
    }


def verify(record: dict) -> list[str]:
    """Every gold evidence span must appear verbatim in the source. Same rule the harness obeys."""
    problems = []
    haystack = normalize(record["source_text"])
    for clause_type, label in record["labels"].items():
        for span in label["evidence"]:
            if span not in haystack:
                problems.append(f"{record['doc_id']}: {clause_type} span not found in source")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=50, help="how many contracts to keep")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    raw = json.loads(RAW.read_text(encoding="utf-8"))
    contracts = [c for c in (extract_contract(e) for e in raw["data"]) if c]

    random.seed(args.seed)
    random.shuffle(contracts)

    # Stratify: keep taking contracts until every category has at least 5 positives
    # and 8 negatives, then fill the rest at random. Avoids an eval set where a
    # category is all-absent and precision is undefined.
    target = 8
    pos = {k: 0 for k in CATEGORIES}
    neg = {k: 0 for k in CATEGORIES}
    selected, leftover = [], []

    for c in contracts:
        if len(selected) >= args.n:
            break
        useful = any(
            (c["labels"][k]["present"] and pos[k] < target)
            or (not c["labels"][k]["present"] and neg[k] < target)
            for k in CATEGORIES
        )
        if useful:
            selected.append(c)
            for k in CATEGORIES:
                if c["labels"][k]["present"]:
                    pos[k] += 1
                else:
                    neg[k] += 1
        else:
            leftover.append(c)

    selected.extend(leftover[: args.n - len(selected)])

    problems = [p for c in selected for p in verify(c)]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for c in selected:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"wrote {len(selected)} contracts to {OUT}")
    print(f"{'category':<32} {'present':>8} {'absent':>8}")
    for k in CATEGORIES:
        p = sum(c["labels"][k]["present"] for c in selected)
        print(f"{k:<32} {p:>8} {len(selected) - p:>8}")

    if problems:
        print(f"\n{len(problems)} gold spans failed the verbatim check:")
        for p in problems[:10]:
            print("  " + p)


if __name__ == "__main__":
    main()