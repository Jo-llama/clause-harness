from schema import ClauseType, Finding, ReviewResult, strip_furniture
from validate import normalize, validate, validate_finding

SOURCE = (
    "This Agreement shall be governed by the laws of the State of Delaware. "
    "The parties agree to keep this arrangement confidential."
)


def make_finding(**overrides):
    defaults = dict(
        clause_type=ClauseType.GOVERNING_LAW,
        present=True,
        evidence="This Agreement shall be governed by the laws of the State of Delaware.",
        reasoning="The contract names Delaware law in its own words.",
        confidence="high",
    )
    defaults.update(overrides)
    return Finding(**defaults)


def test_auto_pass_when_grounded_and_confident():
    verdict = validate_finding(make_finding(), normalize(SOURCE))
    assert verdict.verdict == "auto_pass"
    assert verdict.trigger is None


def test_escalates_on_ungrounded_evidence():
    finding = make_finding(evidence="This Agreement is governed by the laws of Nevada.")
    verdict = validate_finding(finding, normalize(SOURCE))
    assert verdict.verdict == "escalate"
    assert verdict.trigger == "evidence_not_grounded"


def test_escalates_on_elided_evidence():
    finding = make_finding(
        evidence="This Agreement shall be governed by the laws ... of the State of Delaware."
    )
    verdict = validate_finding(finding, normalize(SOURCE))
    assert verdict.verdict == "escalate"
    assert verdict.trigger == "elided_evidence"


def test_escalates_on_redacted_evidence():
    source = (
        "This Agreement shall be governed by the laws of the State of "
        "[***] and no other jurisdiction."
    )
    finding = make_finding(evidence=source)
    verdict = validate_finding(finding, normalize(source))
    assert verdict.verdict == "escalate"
    assert verdict.trigger == "redacted_evidence"


def test_absent_finding_skips_grounding_check():
    finding = make_finding(present=False, evidence="")
    verdict = validate_finding(finding, normalize(SOURCE))
    assert verdict.verdict == "auto_pass"


def test_escalates_on_low_confidence_even_when_grounded():
    verdict = validate_finding(make_finding(confidence="low"), normalize(SOURCE))
    assert verdict.verdict == "escalate"
    assert verdict.trigger == "low_confidence"


def test_escalates_when_reasoning_quotes_contract_text():
    finding = make_finding(
        reasoning='The clause states "shall be governed by the laws of the State of Delaware" directly.'
    )
    verdict = validate_finding(finding, normalize(SOURCE))
    assert verdict.verdict == "escalate"
    assert verdict.trigger == "reasoning_contains_quote"


def test_escalates_when_reasoning_single_quotes_contract_text():
    finding = make_finding(
        reasoning=(
            "The main body also states 'shall be governed by the laws of the "
            "State of Delaware' among other provisions."
        )
    )
    verdict = validate_finding(finding, normalize(SOURCE))
    assert verdict.verdict == "escalate"
    assert verdict.trigger == "reasoning_contains_quote"


def test_apostrophes_and_short_quoted_terms_do_not_trigger():
    finding = make_finding(
        reasoning=(
            "The clause protects both parties' rights and the vendor's "
            "discretion, and separately defines 'Buyer' as the purchasing party."
        )
    )
    verdict = validate_finding(finding, normalize(SOURCE))
    assert verdict.verdict == "auto_pass"


def test_single_quoted_word_in_reasoning_is_not_a_quote_trigger():
    finding = make_finding(reasoning='This finding concerns the "Agreement" as defined.')
    verdict = validate_finding(finding, normalize(SOURCE))
    assert verdict.verdict == "auto_pass"


def test_quoted_text_not_from_contract_does_not_trigger():
    finding = make_finding(reasoning='This reads like "a completely unrelated made up phrase".')
    verdict = validate_finding(finding, normalize(SOURCE))
    assert verdict.verdict == "auto_pass"


def test_evidence_grounding_ignores_whitespace_differences():
    finding = make_finding(
        evidence="This   Agreement shall be governed\nby the laws of the State of Delaware."
    )
    verdict = validate_finding(finding, normalize(SOURCE))
    assert verdict.verdict == "auto_pass"


def test_trigger_priority_evidence_before_confidence():
    finding = make_finding(
        evidence="This Agreement is governed by the laws of Nevada.",
        confidence="low",
    )
    verdict = validate_finding(finding, normalize(SOURCE))
    assert verdict.trigger == "evidence_not_grounded"


def test_trigger_priority_confidence_before_quote():
    finding = make_finding(
        confidence="low",
        reasoning='The clause states "shall be governed by the laws of the State of Delaware" directly.',
    )
    verdict = validate_finding(finding, normalize(SOURCE))
    assert verdict.trigger == "low_confidence"


def test_evidence_with_mid_sentence_page_furniture_matches_stripped_source():
    raw = (
        "This Agreement shall be governed by the laws\nPage 12 of 40\nof the "
        "State of Delaware."
    )
    source = strip_furniture(raw) + " The parties agree to keep this arrangement confidential."
    finding = make_finding(evidence=raw)
    result = ReviewResult(doc_id="doc-1", findings=[finding])
    verdicts = validate(result, source)
    assert verdicts[0].verdict == "auto_pass"


def test_agreeing_passes_do_not_trigger_disagreement():
    finding = make_finding()
    other = make_finding()
    verdict = validate_finding(finding, normalize(SOURCE), other_finding=other)
    assert verdict.verdict == "auto_pass"
    assert verdict.trigger is None


def test_present_disagreement_between_passes_escalates():
    finding = make_finding(present=False, evidence="")
    other = make_finding(present=True)
    verdict = validate_finding(finding, normalize(SOURCE), other_finding=other)
    assert verdict.verdict == "escalate"
    assert verdict.trigger == "pass_disagreement"


def test_validate_runs_over_all_findings_in_result():
    good = make_finding()
    bad = make_finding(evidence="fabricated span not in source")
    result = ReviewResult(doc_id="doc-1", findings=[good, bad])
    verdicts = validate(result, SOURCE)
    assert [v.verdict for v in verdicts] == ["auto_pass", "escalate"]
    assert verdicts[1].trigger == "evidence_not_grounded"
