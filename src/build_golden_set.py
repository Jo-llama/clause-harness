import ast
import json
import re

import pandas as pd

CSV_PATH = "data/raw/cuad/CUAD_v1/master_clauses.csv"
OUT_PATH = "evals/golden/golden_set.jsonl"

CATEGORIES = [
    ("gl", "Governing Law", "Governing Law-Answer"),
    ("cap", "Cap On Liability", "Cap On Liability-Answer"),
]


def parse_clause_text(raw):
    try:
        spans = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return None
    text = " ".join(spans) if isinstance(spans, list) else str(spans)
    return re.sub(r"\s+", " ", text).strip()


def main():
    df = pd.read_csv(CSV_PATH)

    records = []
    skipped = 0
    for prefix, clause_col, answer_col in CATEGORIES:
        clauses = df[clause_col].fillna("").astype(str).str.strip()
        subset = df[(clauses != "") & (clauses != "[]")]
        sample = subset.sample(n=15, random_state=42)

        i = 0
        for _, row in sample.iterrows():
            clause_text = parse_clause_text(row[clause_col])
            if clause_text is None:
                skipped += 1
                continue

            i += 1
            records.append(
                {
                    "id": f"{prefix}_{i:02d}",
                    "contract_name": row["Filename"],
                    "clause_text": clause_text,
                    "category": clause_col,
                    "source_answer": row[answer_col],
                }
            )

        print(f"{clause_col}: {i}")

    print(f"Skipped (parse failure): {skipped}")

    with open(OUT_PATH, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    main()
