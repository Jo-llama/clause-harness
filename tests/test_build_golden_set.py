import pytest

from build_golden_set import apply_overrides


def make_selected():
    return [
        {
            "doc_id": "REAL_CONTRACT",
            "labels": {"non_compete": {"present": True, "evidence": ["some span"]}},
        }
    ]


def test_matching_override_is_applied():
    selected = make_selected()
    known_doc_ids = {"REAL_CONTRACT"}
    overrides = [
        {"doc_id": "REAL_CONTRACT", "clause_type": "non_compete", "present": False, "note": "reason"}
    ]

    applied, skipped = apply_overrides(selected, overrides, known_doc_ids)

    assert applied == 1
    assert skipped == []
    assert selected[0]["labels"]["non_compete"]["present"] is False
    assert selected[0]["labels"]["non_compete"]["notes"] == "reason"


def test_unknown_doc_id_raises():
    selected = make_selected()
    known_doc_ids = {"REAL_CONTRACT"}
    overrides = [
        {"doc_id": "TYPO_CONTRACT", "clause_type": "non_compete", "present": False, "note": "x"}
    ]

    with pytest.raises(SystemExit):
        apply_overrides(selected, overrides, known_doc_ids)


def test_unselected_doc_id_is_skipped_not_applied():
    selected = make_selected()
    known_doc_ids = {"REAL_CONTRACT", "OTHER_CONTRACT_NOT_SAMPLED"}
    overrides = [
        {
            "doc_id": "OTHER_CONTRACT_NOT_SAMPLED",
            "clause_type": "non_compete",
            "present": False,
            "note": "x",
        }
    ]

    applied, skipped = apply_overrides(selected, overrides, known_doc_ids)

    assert applied == 0
    assert skipped == ["OTHER_CONTRACT_NOT_SAMPLED"]
