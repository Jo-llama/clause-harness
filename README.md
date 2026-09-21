# clause-harness

LLM harness for contract clause review. Extracts eight CUAD clause types from
commercial contracts, validates every citation against the source text, and
routes anything it can't verify to human review instead of guessing.

Portfolio project — see [DESIGN.md](DESIGN.md) for the question it's built to
answer: not *can a model classify clauses*, but *can the system tell when it's
wrong*.

## What it does

1. **Extract.** For each contract, ask the model for a finding per clause type
   (present/absent, verbatim evidence span, reasoning, confidence) as
   schema-validated structured output. A second pass, reworded and reordered,
   runs over the same contract to catch cases where a single read gets a
   confident wrong answer.
2. **Validate.** Every finding is checked deterministically, no second model
   call:
   - cited evidence must appear verbatim in the source (catches fabricated or
     altered quotes)
   - evidence can't stitch separated text together with "..."
   - `confidence: low` escalates
   - disagreement between the two passes on `present` escalates
   - evidence sitting behind a `[***]` redaction escalates as unverifiable,
     not as a model error
3. **Escalate or auto-pass.** Findings that clear every check are trustworthy
   without opening the contract. Everything else is flagged for a lawyer, with
   the specific reason attached.

Full rationale for each trigger, and the asymmetry between how well false
positives vs. false negatives are covered, is in [DESIGN.md](DESIGN.md).

## The eight clause types

`governing_law` · `cap_on_liability` · `uncapped_liability` ·
`termination_for_convenience` · `anti_assignment` · `change_of_control` ·
`exclusivity` · `non_compete`

Definitions are authoritative in [TAXONOMY.md](TAXONOMY.md) — they're shared
verbatim between the extraction prompt and the golden-set labels so the eval
measures model quality, not disagreement about what a category means.

## Setup

```bash
uv sync

cp .env.example .env   # then add your Anthropic API key
uv run scripts/smoke_api.py   # smoke test
```

## Usage

```bash
# Review one contract from the golden set, print schema-valid JSON to stdout
uv run src/review.py <doc_id_prefix>

# Run the harness over a subset (two passes per contract, saved to runs/<doc_id>.json)
uv run scripts/run_batch.py --limit 15
uv run scripts/run_batch.py --limit 5 --doc-ids Healthcentral,Cardax,IbioInc

# Score saved runs against gold labels — no API calls, reads runs/ + data/golden.jsonl
uv run scripts/score_runs.py

# Rebuild the golden set from raw CUAD data
uv run scripts/build_golden_set.py --n 75
```

CUAD contracts run ~15k tokens each; two passes × eight categories per
contract adds up on Opus. Iterate with `--limit 15`; run the full 75 only for
numbers that get committed.

## Current results

`scripts/score_runs.py` on the **25 contracts currently in `runs/`** (partial
golden set — not yet the committed full-75 number):

| | n | precision | recall |
|---|---|---|---|
| Auto-pass set | 189 | 0.915 | 0.980 |
| Escalated set | 11 | 0.364 | 1.000 |

Of the 11 escalations: 7 were genuine catches (model disagreed with gold), 3
were unverifiable redactions, 1 was a false alarm. Zero hallucinated evidence
spans reached auto-pass.

Read these two numbers together, not separately — a harness that escalates
everything is safe and worthless; the number that matters is accuracy on what
it *chose not to* escalate. See DESIGN.md, *Metrics*.

## Layout

```
src/review.py           prompt construction, model call, single-contract CLI
src/schema.py            ReviewResult / Finding schema, ClauseType enum
src/validate.py          escalation triggers, auto-pass/escalate logic
scripts/build_golden_set.py   CUAD v1 -> data/golden.jsonl
scripts/run_batch.py     batch extraction + validation, writes runs/
scripts/score_runs.py    offline scoring of saved runs against gold labels
data/golden.jsonl        75-contract golden set
prompts/, runs/          versioned prompts, per-contract run logs
```

## Data

Golden set derived from [CUAD v1](https://www.atticusprojectai.org/cuad) (The
Atticus Project), CC BY 4.0.

## Out of scope

No web UI, API server, or database. No vector search / RAG — the taxonomy is
a fixed eight-category dict, not a retrieval problem. No agent framework. Full
list and reasoning in [DESIGN.md](DESIGN.md#out-of-scope-for-v1).
