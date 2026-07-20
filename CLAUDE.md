# clause-harness

Portfolio project. Interview evidence, not a product.
Target: showable within one week.

## Scope — do not exceed
- Eight CUAD clause types (see TAXONOMY.md), 75-contract golden set (data/golden.jsonl)
- Structured output + schema validation + retry on failure
- Grounding check: cited span must exist in source text
- Confidence threshold → auto-clear / flag / escalate
- Run logging to JSONL, versioned prompts
- eval.py: per-class precision/recall, version comparison

## Explicitly out of scope — do not add
- Web UI, API server, auth, database
- Vector search / RAG (playbook is a dict lookup)
- LangChain or any agent framework
- Async, caching, retries beyond the validation loop
- Abstract base classes, plugin systems, config frameworks
- More clause types beyond the eight in TAXONOMY.md

## Cost
CUAD contracts run ~50k characters (~15k tokens) each. 75 contracts × 8 categories in
one call each × two passes for the disagreement trigger × however many prompt
iterations you run adds up fast on Opus.
- `eval.py` must take a `--limit` flag. Iterate against 15 contracts; run the full 75
  only for numbers that get committed.
- Consider Sonnet for extraction passes. If the harness only works well on the most
  expensive model, that's a finding worth reporting, not hiding.

## Style
- Plain functions over classes unless state demands it
- Standard library first; a dependency needs justification
- No premature abstraction — duplicate twice before extracting
- Every file should be explainable in an interview in 60 seconds

## Escalation labelling rule (golden set)
escalate = true when a lawyer must see the clause before it can be relied on:
- the finding depends on carve-outs, exceptions, or cross-references
- the value is a formula rather than a stated figure
- multiple jurisdictions / caps are named
- the clause is ambiguous or internally inconsistent
escalate = false when the finding is stated plainly and self-contained.

## Context

Read `DESIGN.md` before changing the harness — it explains why escalation
exists and why the eval scorer uses containment rather than exact match.

Read `TAXONOMY.md` before changing the prompt — the clause definitions there
are authoritative and must match the golden set labels.