import json
import sys
from pathlib import Path

import anthropic
import pydantic
from dotenv import load_dotenv

from schema import ClauseType, ReviewResult
from validate import validate

GOLDEN_PATH = Path("data/golden.jsonl")
MODEL = "claude-opus-4-8"
PARSE_ATTEMPTS = 2


TAXONOMY = {
    ClauseType.GOVERNING_LAW: (
        "The clause specifying which jurisdiction's law governs interpretation "
        "of the contract."
    ),
    ClauseType.CAP_ON_LIABILITY: (
        "Any contractual limitation on liability, including exclusions of "
        "consequential, incidental, indirect, special, or exemplary damages. "
        "A monetary ceiling is sufficient but not necessary."
    ),
    ClauseType.UNCAPPED_LIABILITY: (
        "Categories of claim expressly carved out from the limitation in "
        "cap_on_liability -- typically indemnity obligations, breach of "
        "confidentiality, gross negligence, willful misconduct, or fraud."
    ),
    ClauseType.TERMINATION_FOR_CONVENIENCE: (
        "Termination without cause, at a party's election, typically on "
        "notice. Distinct from termination on enumerated breach or trigger "
        "events, which is termination for cause and does not qualify. "
        "The right must permit termination of the agreement as a whole. A "
        "right to terminate a component, programme, or fund does not qualify."
    ),
    ClauseType.ANTI_ASSIGNMENT: (
        "Restriction on assigning the agreement or rights under it, usually "
        "requiring the counterparty's prior written consent."
    ),
    ClauseType.CHANGE_OF_CONTROL: (
        "Rights arising on a merger, acquisition, or change in ownership of "
        "a party -- commonly a right to terminate or a consent requirement. "
        "Not to be confused with term-and-renewal provisions. The change in "
        "ownership must be of a party to this agreement. Provisions "
        "triggered by a change in control of a third party do not qualify."
    ),
    ClauseType.EXCLUSIVITY: (
        "An undertaking to deal exclusively with the counterparty, or a "
        "grant of exclusive rights within a defined field, territory, or "
        "channel. An undertaking expressly disclaimed or made subject to "
        '"no guarantee" is not a grant of exclusive rights and does not qualify.'
    ),
    ClauseType.NON_COMPETE: (
        "A restriction on competing with the counterparty. Restrictions on "
        "use or disclosure of confidential information or source code are "
        "confidentiality/IP provisions and do not qualify, even though they "
        "restrict commercial behaviour."
    ),
}


# Shared verbatim across both prompt variants -- only the intro and the
# present/absent framing sentence differ between "a" and "b" (see
# build_system_prompt). Keeping these as constants, rather than duplicating
# the text in each variant, makes byte-identity structural rather than a
# matter of careful copy-pasting.
LIABILITY_PAIR_NOTE = (
    "cap_on_liability and uncapped_liability are two facts about one provision, not\n"
    "competing labels. A single passage commonly establishes both the limitation and\n"
    "the carve-outs from it -- the same span may serve as evidence for both findings."
)

VERBATIM_INSTRUCTION = (
    "If present, quote the\n"
    "evidence verbatim: copy the text exactly as it appears in the contract, do not\n"
    "correct, shorten, paraphrase, or summarize it. If absent, leave evidence as an\n"
    "empty string."
)

NO_QUOTE_IN_REASONING = (
    "Do not quote contract text in reasoning. All quoted text belongs in evidence.\n"
    "Describe your reasoning in your own words."
)

REDACTION_INSTRUCTION = (
    "Contract text may contain [***] redactions. Do not infer clause content from a section heading whose body is redacted; \n"
    "treat the evidence as unavailable and lower your confidence."
)

NO_ELISION_INSTRUCTION = (
    'Quote one contiguous passage. Never use "..." or any other marker to join\n'
    "separated text. If the relevant provisions are not contiguous,\n"
    "quote the single most representative passage and describe the rest\n"
    "in your reasoning."
)

CLOSING_INSTRUCTION = "Return exactly one finding per clause type -- eight findings total."


def build_system_prompt(variant: str = "a") -> str:
    """variant "a" is the reported pass. variant "b" asks for the same eight
    findings under the same definitions, but reworded and reordered to force
    an independent read for the pass_disagreement trigger -- see validate.py.
    """
    items = list(TAXONOMY.items())
    if variant == "b":
        items = list(reversed(items))
    definitions = "\n".join(f"- {ct.value}: {desc}" for ct, desc in items)

    if variant == "b":
        intro = "Scan the following contract and report which of these eight clause types appear in it."
        framing = "Scan the contract and report which of these clause types appear."
    else:
        intro = "You are reviewing a commercial contract for the presence of eight clause types."
        framing = "For each clause type, decide whether it is present."

    return f"""{intro}

Clause definitions:
{definitions}

{LIABILITY_PAIR_NOTE}

{framing} {VERBATIM_INSTRUCTION}

{NO_QUOTE_IN_REASONING}

{REDACTION_INSTRUCTION}

{NO_ELISION_INSTRUCTION}

{CLOSING_INSTRUCTION}"""


def load_record(path: Path, doc_id_prefix: str | None = None) -> dict:
    with open(path) as f:
        for line in f:
            record = json.loads(line)
            if doc_id_prefix is None or record["doc_id"].startswith(doc_id_prefix):
                return record
    raise SystemExit(f"no record matching {doc_id_prefix!r} in {path}")


def call_model(
    client: anthropic.Anthropic, source_text: str, variant: str = "a"
) -> ReviewResult | None:
    # Opus 4.7+ rejects temperature/top_p/top_k with a 400 -- omitted
    # entirely, not passed as 0. Pass B's independence comes from
    # build_system_prompt's variant wording instead (see validate.py,
    # pass_disagreement).
    for attempt in range(PARSE_ATTEMPTS):
        try:
            response = client.messages.parse(
                model=MODEL,
                max_tokens=8192,
                system=build_system_prompt(variant),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": source_text,
                                # Cache breakpoint on the contract text so a
                                # second pass over the same contract (see
                                # trigger 4) only pays full input cost once.
                                "cache_control": {"type": "ephemeral"},
                            }
                        ],
                    }
                ],
                output_format=ReviewResult,
            )
            return response.content[0].parsed_output
        except (pydantic.ValidationError, ValueError):
            if attempt == PARSE_ATTEMPTS - 1:
                return None
    return None


def main():
    load_dotenv()
    client = anthropic.Anthropic()

    record = load_record(GOLDEN_PATH, sys.argv[1] if len(sys.argv) > 1 else None)

    result = call_model(client, record["source_text"])

    if result is None:
        print(
            json.dumps(
                {
                    "doc_id": record["doc_id"],
                    "verdict": "escalate",
                    "trigger": "schema_or_parse_failure",
                },
                indent=2,
            )
        )
        return

    result.doc_id = record["doc_id"]

    verdicts = validate(result, record["source_text"])
    output = {
        "doc_id": result.doc_id,
        "findings": [
            {**v.finding.model_dump(), "verdict": v.verdict, "trigger": v.trigger}
            for v in verdicts
        ],
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
