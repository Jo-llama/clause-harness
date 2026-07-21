import re
from typing import Literal

from pydantic import BaseModel

from schema import Finding, ReviewResult, strip_furniture

Trigger = Literal[
    "elided_evidence", "evidence_not_grounded", "low_confidence", "reasoning_contains_quote", "redacted_evidence"
]

QUOTE_PATTERNS = [
    re.compile(r'"([^"]+)"'),
    re.compile(r"“([^”]+)”"),
    re.compile(r"'([^']+)'"),
    re.compile(r"‘([^’]+)’"),
]
MIN_QUOTE_WORDS = 8


class FindingVerdict(BaseModel):
    finding: Finding
    verdict: Literal["auto_pass", "escalate"]
    trigger: Trigger | None = None


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def reasoning_quotes_contract(reasoning: str, normalized_source: str) -> bool:
    for pattern in QUOTE_PATTERNS:
        for match in pattern.finditer(reasoning):
            quoted = match.group(1).strip()
            if len(quoted.split()) <= MIN_QUOTE_WORDS:
                continue  # short quotes read as defined terms, not lifted clauses
            if normalize(quoted) in normalized_source:
                return True
    return False


def validate_finding(finding: Finding, normalized_source: str) -> FindingVerdict:
    if finding.present:
        if "..." in finding.evidence or "…" in finding.evidence:
            return FindingVerdict(finding=finding, verdict="escalate", trigger="elided_evidence")
        if normalize(strip_furniture(finding.evidence)) not in normalized_source:
            return FindingVerdict(finding=finding, verdict="escalate", trigger="evidence_not_grounded")
        if finding.present and "[***]" in finding.evidence:
            return FindingVerdict(finding=finding, verdict="escalate", trigger="redacted_evidence")
    if finding.confidence == "low":
        return FindingVerdict(finding=finding, verdict="escalate", trigger="low_confidence")
    if reasoning_quotes_contract(finding.reasoning, normalized_source):
        return FindingVerdict(finding=finding, verdict="escalate", trigger="reasoning_contains_quote")
    return FindingVerdict(finding=finding, verdict="auto_pass")


def validate(result: ReviewResult, source_text: str) -> list[FindingVerdict]:
    normalized_source = normalize(strip_furniture(source_text))
    return [validate_finding(finding, normalized_source) for finding in result.findings]
