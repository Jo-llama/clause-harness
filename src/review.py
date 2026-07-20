import json
from enum import Enum
from pathlib import Path
from typing import Literal

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

import sys

GOLDEN_PATH = Path("data/golden.jsonl")
MODEL = "claude-opus-4-8"


class ClauseType(str, Enum):
    GOVERNING_LAW = "governing_law"
    CAP_ON_LIABILITY = "cap_on_liability"
    UNCAPPED_LIABILITY = "uncapped_liability"
    TERMINATION_FOR_CONVENIENCE = "termination_for_convenience"
    ANTI_ASSIGNMENT = "anti_assignment"
    CHANGE_OF_CONTROL = "change_of_control"
    EXCLUSIVITY = "exclusivity"
    NON_COMPETE = "non_compete"


class Finding(BaseModel):
    clause_type: ClauseType
    present: bool
    evidence: str
    reasoning: str
    confidence: Literal["high", "medium", "low"]


class ReviewResult(BaseModel):
    doc_id: str
    findings: list[Finding]


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
        "events, which is termination for cause and does not qualify."
    ),
    ClauseType.ANTI_ASSIGNMENT: (
        "Restriction on assigning the agreement or rights under it, usually "
        "requiring the counterparty's prior written consent."
    ),
    ClauseType.CHANGE_OF_CONTROL: (
        "Rights arising on a merger, acquisition, or change in ownership of "
        "a party -- commonly a right to terminate or a consent requirement. "
        "Not to be confused with term-and-renewal provisions."
    ),
    ClauseType.EXCLUSIVITY: (
        "An undertaking to deal exclusively with the counterparty, or a "
        "grant of exclusive rights within a defined field, territory, or "
        "channel."
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

Return exactly one finding per clause type -- eight findings total."""


def load_record(path: Path, doc_id_prefix: str | None = None) -> dict:
    with open(path) as f:
        for line in f:
            record = json.loads(line)
            if doc_id_prefix is None or record["doc_id"].startswith(doc_id_prefix):
                return record
    raise SystemExit(f"no record matching {doc_id_prefix!r} in {path}")


def main():
    load_dotenv()
    client = anthropic.Anthropic()

    record = load_record(GOLDEN_PATH, sys.argv[1] if len(sys.argv) > 1 else None)

    response = client.messages.parse(
        model=MODEL,
        max_tokens=8192,
        system=build_system_prompt(),
        messages=[{"role": "user", "content": record["source_text"]}],
        output_format=ReviewResult,
    )

    result = response.content[0].parsed_output
    result.doc_id = record["doc_id"]

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
