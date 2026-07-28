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


def build_system_prompt() -> str:
    definitions = "\n".join(f"- {ct.value}: {desc}" for ct, desc in TAXONOMY.items())
    return f"""You are reviewing a commercial contract for the presence of eight clause types.

Clause definitions:
{definitions}

cap_on_liability and uncapped_liability are two facts about one provision, not
competing labels. A single passage commonly establishes both the limitation and
the carve-outs from it -- the same span may serve as evidence for both findings.

For each clause type, decide whether it is present. If present, quote the
evidence verbatim: copy the text exactly as it appears in the contract, do not
correct, shorten, paraphrase, or summarize it. If absent, leave evidence as an
empty string.

Do not quote contract text in reasoning. All quoted text belongs in evidence.
Describe your reasoning in your own words.

Contract text may contain [***] redactions. Do not infer clause content from a section heading whose body is redacted; 
treat the evidence as unavailable and lower your confidence.

Quote one contiguous passage. Never use "..." or any other marker to join
separated text. If the relevant provisions are not contiguous,
quote the single most representative passage and describe the rest
in your reasoning.

Return exactly one finding per clause type -- eight findings total."""


def load_record(path: Path, doc_id_prefix: str | None = None) -> dict:
    with open(path) as f:
        for line in f:
            record = json.loads(line)
            if doc_id_prefix is None or record["doc_id"].startswith(doc_id_prefix):
                return record
    raise SystemExit(f"no record matching {doc_id_prefix!r} in {path}")


def call_model(
    client: anthropic.Anthropic, source_text: str, temperature: float = 0.0
) -> ReviewResult | None:
    for attempt in range(PARSE_ATTEMPTS):
        try:
            response = client.messages.parse(
                model=MODEL,
                max_tokens=8192,
                system=build_system_prompt(),
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
                temperature=temperature,
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
