# Design

## What this project is testing

The interesting question in LLM contract review is not *can a model classify
clauses* — it can, adequately, and demonstrating that proves little. The
question is **can the system tell when it is wrong**.

A reviewer of an automated contract-review tool cares about exactly one thing:
when the output says a clause is present and quotes supporting text, can that be
trusted without opening the contract? A system that is 92% accurate and silent
about which 8% is unreliable is worse than useless in a legal setting — it
transfers the review burden back to the human while looking like it removed it.

So the harness is built around **escalation**: the output is partitioned into
findings that passed every validator (auto-pass) and findings routed to human
review. The design goal is that the auto-pass set is trustworthy and the
escalation rate is low enough to be worth having.

Extraction quality matters only insofar as it moves those two numbers.

## Output schema

```python
class Finding(BaseModel):
    clause_type: ClauseType
    present: bool
    evidence: str      # verbatim span from the contract; empty if not present
    reasoning: str
    confidence: Literal["high", "medium", "low"]

class ReviewResult(BaseModel):
    doc_id: str
    findings: list[Finding]
```

Enforced via the API's structured outputs rather than parsed out of prose.

**`evidence` is the load-bearing field.** Because the model is required to
return a verbatim span, correctness of the citation is checkable
programmatically — `evidence in source_text` — with no second model call and no
judgement. That single constraint converts hallucinated citations from an
invisible failure into a caught one.

The prompt states the requirement explicitly ("Copy the text exactly as it
appears; do not correct, shorten, or rephrase it"), because models paraphrase by
default.

## Escalation triggers

A finding is escalated to human review if any of these fire, in ascending order
of cost to check:

1. **Schema or parse failure.** Retry once, then escalate.
2. **Evidence not found verbatim in the source.** Fabricated or altered
   citation.
3. **`confidence == "low"`.** Model self-report.
4. **Disagreement between two independent passes on `present`.**

Everything else auto-passes.

### The tradeoff, stated deliberately

Trigger 2 will escalate some findings that are substantively correct — a model
that paraphrases accurately gets flagged. That is the intended trade. In legal
review, a fabricated quotation attributed to a contract is the failure mode with
real consequences; a correct answer sent for human confirmation costs a minute.
The system is tuned to be wrong in the cheap direction.

Whitespace is normalized on both sides before comparison, since contracts
extracted from PDF carry stray newlines and double spaces that would otherwise
cause constant cosmetic escalations.

## Two different checks, deliberately not the same

This distinction is easy to collapse and expensive to get wrong.

| | Runtime validator | Eval scorer |
|---|---|---|
| Question | Is the evidence really in the contract? | Did the model find the right clause? |
| Compared against | The source contract | The gold span |
| Type | Binary | Graded |
| Purpose | Catch hallucination | Measure quality |

The runtime validator is exact substring matching. The eval scorer **must not
be**, because CUAD gold spans are mid-sentence fragments (see `TAXONOMY.md`,
*Known data quirks*). A model returning a complete, correct sentence would score
zero against a truncated gold span, and at least one gold span is missing its
first character outright.

Scoring therefore uses containment:

```python
def spans_agree(pred: str, gold: str) -> bool:
    p, g = normalize(pred), normalize(gold)
    return g in p or p in g
```

Using exact match here would produce a metric that tracks annotation style
rather than model quality — and prompt iteration would then optimize against
noise.

## Asymmetry: false positives vs false negatives

The validators are not evenly matched across the two error types.

**False positives** — a clause reported present that isn't there — are well
defended. Trigger 2 requires the cited evidence to appear verbatim in the
source, so a fabricated or altered citation is caught deterministically.

**False negatives** — a clause missed entirely — are harder. On `present:
false` the `evidence` field is empty, so there is nothing for trigger 2 to
check. A missed clause produces output that is confident, well-reasoned,
schema-valid, and unverifiable by string comparison.

Coverage for false negatives comes from two weaker signals:

- **Trigger 3 (low confidence).** Partial but real. On CARDAX the model missed
  an exclusive licence grant because the section headed "Exclusivity" was
  redacted to `[***]`; it reported absent but flagged itself `low`, and the
  finding escalated. Self-report works when the model can tell its evidence is
  inadequate — not when it is confidently wrong.
- **Trigger 4 (two-pass disagreement).** The only signal that fires when the
  model is confidently wrong, which makes it load-bearing rather than
  optional.

Consequence for metrics: **precision and recall are reported separately, never
folded into a single accuracy figure.** They rest on different amounts of
validation and conflating them would overstate how much of the output is
actually checked.

## Metrics

The eval reports, per category and in aggregate:

- **Precision / recall on presence detection**, computed over the auto-pass set.
- **Escalation rate**, overall and by trigger. Broken out by trigger because the
  triggers mean different things: a high rate on trigger 2 is a model problem, a
  high rate on trigger 3 is a calibration problem.
- **Hallucinated evidence count** reaching auto-pass. Should be structurally
  zero, not empirically rare.
- **Span agreement** on true positives, via the containment scorer.

Accuracy and escalation rate must be read together. A harness that escalates
everything is perfectly safe and completely worthless; one that escalates
nothing has no reason to be trusted. The number that matters is accuracy on
what it chose not to escalate.

Metrics are committed at each prompt iteration so the README can show movement
rather than a single final figure.

## Out of scope for v1

Deliberately excluded, each because it does not test the hypothesis:

- Multi-document batching
- Any user interface
- PDF parsing (CUAD provides extracted text)
- Fine-tuning
- Retrieval / RAG over long contracts
- Response caching
- The remaining 33 CUAD categories

## Done criteria

- `python -m harness review <contract>` runs end-to-end and emits schema-valid
  JSON.
- `python -m harness eval` prints the metrics table and writes it to a file.
- Zero hallucinated evidence spans reach the auto-pass set.
- README shows the metrics table and explains why escalation exists.