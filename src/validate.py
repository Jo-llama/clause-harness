import re
from typing import Literal

from pydantic import BaseModel

from review import Finding, ReviewResult

Trigger = Literal["evidence_not_grounded", "low_confidence", "reasoning_contains_quote"]

QUOTE_PATTERN = re.compile(r'["“]([^"”]+)["”]')


class FindingVerdict(BaseModel):
    finding: Finding
    verdict: Literal["auto_pass", "escalate"]
    trigger: Trigger | None = None


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def reasoning_quotes_contract(reasoning: str, normalized_source: str) -> bool:
    for match in QUOTE_PATTERN.finditer(reasoning):
        quoted = match.group(1).strip()
        if " " not in quoted:
            continue  # a single quoted word reads as a defined term, not a lifted clause
        if normalize(quoted) in normalized_source:
            return True
    return False


def validate_finding(finding: Finding, normalized_source: str) -> FindingVerdict:
    if finding.present and normalize(finding.evidence) not in normalized_source:
        return FindingVerdict(finding=finding, verdict="escalate", trigger="evidence_not_grounded")
    if finding.confidence == "low":
        return FindingVerdict(finding=finding, verdict="escalate", trigger="low_confidence")
    if reasoning_quotes_contract(finding.reasoning, normalized_source):
        return FindingVerdict(finding=finding, verdict="escalate", trigger="reasoning_contains_quote")
    return FindingVerdict(finding=finding, verdict="auto_pass")


def validate(result: ReviewResult, source_text: str) -> list[FindingVerdict]:
    normalized_source = normalize(source_text)
    return [validate_finding(finding, normalized_source) for finding in result.findings]
