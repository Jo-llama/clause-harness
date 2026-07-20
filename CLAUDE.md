# clause-harness

Portfolio project. Interview evidence, not a product.
Target: showable within one week.

## Scope — do not exceed
- Two CUAD clause types, ~30 golden-set cases
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
- More than two clause types

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