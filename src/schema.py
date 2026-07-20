import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel

FURNITURE = [
    re.compile(r"^\s*Page \d+ of \d+\s*$", re.M),
    re.compile(r"^\s*Source: .{0,100}\d{1,2}/\d{1,2}/\d{4}\s*$", re.M),
    re.compile(r"^\s*\d{1,4}\s*$", re.M),
]


def strip_furniture(text: str) -> str:
    """Remove page numbers and EDGAR footers that appear mid-sentence in extracted text.

    Must run on raw text, before whitespace normalization, while line
    structure still exists — the bare-number rule is only safe line-anchored.
    """
    for pattern in FURNITURE:
        text = pattern.sub("", text)
    return text


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
