import json
import os
import sys
import textwrap

GOLDEN_PATH = "evals/golden/golden_set.jsonl"


def load_records(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def save_records(records, path):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    os.replace(tmp_path, path)


def main():
    records = load_records(GOLDEN_PATH)

    for record in records:
        if "expected_escalation" in record:
            continue

        print(f"\n{record['id']} | {record['category']} | source_answer={record['source_answer']}")
        print(textwrap.fill(record["clause_text"], width=100))

        while True:
            answer = input("escalate? [y/n/q]: ").strip().lower()
            if answer == "y":
                record["expected_escalation"] = True
                break
            if answer == "n":
                record["expected_escalation"] = False
                break
            if answer == "q":
                save_records(records, GOLDEN_PATH)
                print("Progress saved. Exiting.")
                sys.exit(0)
            print("Please enter y, n, or q.")

    save_records(records, GOLDEN_PATH)
    print("All records labelled.")


if __name__ == "__main__":
    main()
