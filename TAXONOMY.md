# Clause Taxonomy

The eight clause categories this harness reviews, and the rules used to decide
whether a clause is present. These definitions are authoritative: they appear in
the extraction prompt and govern the golden set labels, so that model output and
gold labels are measuring the same thing.

Source data: [CUAD v1](https://www.atticusprojectai.org/cuad) (The Atticus
Project), CC BY 4.0. Labels are inherited from CUAD except where noted under
*Overrides*.

## Why the definitions are written down

CUAD's category names are shorter than its operative definitions. "Cap On
Liability" does not mean what the name suggests (see below). Adopting a
definition implicitly — or worse, letting the prompt use one definition while
the gold set uses another — makes the eval measure annotation style rather than
model quality. Every definition below was derived by reading the actual
annotated spans, not the category name.

## Categories

### governing_law
The clause specifying which jurisdiction's law governs interpretation of the
contract. Nearly universal in commercial contracts (67/75 positive in the golden
set), so for this category the eval is effectively testing span selection rather
than presence detection.

### cap_on_liability
**Any contractual limitation on liability**, including exclusions of
consequential, incidental, indirect, special, or exemplary damages. A monetary
ceiling is sufficient but *not necessary*.

This is broader than the category name implies. It was derived from the
annotated spans, the majority of which contain no monetary ceiling at all —
e.g. "IN NO EVENT SHALL SELLER BE LIABLE FOR SPECIAL, INCIDENTAL, CONSEQUENTIAL
OR EXEMPLARY DAMAGES." Treating only monetary caps as qualifying would put the
prompt at odds with roughly three quarters of the gold labels.

### uncapped_liability
Categories of claim **expressly carved out** from the limitation in
`cap_on_liability` — typically indemnity obligations, breach of confidentiality,
gross negligence, willful misconduct, or fraud.

### The liability pair

`cap_on_liability` and `uncapped_liability` are two facts about one provision,
not competing labels. A single sentence commonly establishes both: the
limitation, and the exceptions that sit outside it.

    "Except in the event of (i) a Party's gross negligence or willful
     misconduct and/or (ii) a Party's breach of its confidentiality
     obligations, neither Party shall be liable for..."

In the golden set, several contracts carry the **same span** under both labels.
This is correct and must be preserved:

- Do not deduplicate evidence spans in the pipeline.
- The prompt must permit one passage to support two findings.

A prompt that treats the categories as mutually exclusive will pick one and drop
the other. This pair is the primary failure mode the harness is designed to
expose.

### termination_for_convenience
Termination without cause, at a party's election, typically on notice. Distinct
from termination on enumerated breach or trigger events, which is termination
for cause and does *not* qualify.

### anti_assignment
Restriction on assigning the agreement or rights under it, usually requiring the
counterparty's prior written consent.

### change_of_control
Rights arising on a merger, acquisition, or change in ownership of a party —
commonly a right to terminate or a consent requirement. Not to be confused with
term-and-renewal provisions.

### exclusivity
An undertaking to deal exclusively with the counterparty, or a grant of
exclusive rights within a defined field, territory, or channel.

### non_compete
A restriction on competing with the counterparty. Restrictions on *use or
disclosure* of confidential information or source code are confidentiality/IP
provisions and do **not** qualify, even though they restrict commercial
behaviour.

## Verification approach

Full manual review of 75 contracts x 8 categories (600 judgments over documents
averaging ~50k characters) was out of scope for this project's timeline.
Verification effort was concentrated where labels are most load-bearing:

1. The `cap_on_liability` / `uncapped_liability` pair was reviewed across all
   contracts where either is present.
2. A random sample of contracts was reviewed in full across all eight
   categories.
3. Remaining labels are inherited from CUAD as-is.

This is stated explicitly rather than claimed as full review, because knowing
where verification was and was not applied is part of knowing what the eval
numbers mean.

## Overrides

Labels changed from CUAD, with reasons. Each override is also recorded in a
`notes` field on the affected record in `data/golden.jsonl`.

> **TODO (Jo):** confirm each of these before committing. They are flagged
> candidates from the review pass, not yet applied.

| Contract | Category | CUAD | Override | Reason |
|---|---|---|---|---|
| TELKOMSALTD_01_30_2003 | `non_compete` | present | absent | Span restricts copying and disclosure of source code. Confidentiality/IP restriction, not a restriction on competing. |
| LECLANCHE S.A. | `change_of_control` | present | absent | Span is a term-and-renewal provision ("Initial Period of 1 year, which may be renewed"). Belongs to CUAD's `Renewal Term` category. |
| VIOLINMEMORYINC_12_12_2012 | `cap_on_liability` | present | *undecided* | Span is a waiver and release of claims, a distinct instrument from a limitation of liability. Defensible either way — decide and apply consistently. |
| AULAMERICANUNITTRUST | `anti_assignment` | absent | present | The `governing_law` span itself contains "...and is assignable only upon the written...", so an anti-assignment provision is present but unlabelled. |
| TELKOMSALTD_01_30_2003 | `termination_for_convenience` | present | *undecided* | Span reads as termination on enumerated events (for cause). Truncated in review — check full text before deciding. |

## Known data quirks

**CUAD spans are fragments, not clauses.** Annotators highlighted the salient
stretch of text, not a syntactic unit. Spans routinely begin and end
mid-sentence:

    "for any reason on at least ninety (90) days written notice to the
     other party."

**Off-by-one errors in `answer_start`.** At least one span drops its first
character (IMPCO's governing_law span begins "his Agreement shall be
governed...").

Both quirks mean exact string matching against gold spans would fail on
answers that are correct — or even *more* complete than the gold annotation.
See `DESIGN.md` for how scoring handles this.