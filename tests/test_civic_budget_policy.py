"""Offline status-policy fixtures; no numeric accuracy or real-model claim."""

import pytest

from app.civic_budget_policy import guard_answer, guard_request


def source(identifier="budget-introduced", **metadata):
    return {
        "chunk_id": identifier,
        "title": "Synthetic budget source",
        "text": "Synthetic amount and status fixture, not actual Newark data.",
        "metadata": {
            "kind": "budget",
            "status": "introduced",
            "year": 2031,
            "adoption_verified": False,
            "adoption_date": None,
            **metadata,
        },
    }


def adopted(identifier="budget-adopted", **metadata):
    return source(
        identifier,
        **{
            "status": "adopted",
            "adoption_verified": True,
            "adoption_date": "2030-12-12",
            **metadata,
        },
    )


def answer(text, identifiers=None, insufficient=False):
    return {
        "answer": text,
        "citation_ids": identifiers or ["budget-introduced"],
        "insufficient_evidence": insufficient,
        "model": "offline-fixture",
    }


def assert_missing(result):
    assert result["insufficient_evidence"] is True
    assert result["citation_ids"] == []
    assert "indexed sources" in result["answer"].lower()
    assert "not approved" not in result["answer"].lower()
    assert "not adopted" not in result["answer"].lower()


@pytest.mark.parametrize("status", ["approved", "adopted", "final"])
def test_introduced_cannot_establish_requested_approved_status(status):
    assert_missing(guard_request(f"What is the {status} 2031 budget?", [source()]))


@pytest.mark.parametrize(
    "metadata",
    [
        {"status": "introduced"},
        {"adoption_verified": "true"},
        {"adoption_verified": 1},
        {"adoption_date": None},
        {"adoption_date": "not established"},
        {"adoption_date": "2031-02-30"},
        {"year": 2030},
        {"year": None},
        {"year": "unknown"},
    ],
)
def test_unverified_missing_invalid_or_wrong_year_cannot_authorize(metadata):
    assert_missing(
        guard_request("What is the approved 2031 budget?", [adopted(**metadata)])
    )


def test_verified_adoption_matches_fiscal_year_not_adoption_calendar_year():
    assert guard_request("What is the approved 2031 budget?", [adopted()]) is None
    aliases = adopted(fiscal_year=2031, year=2030, budget_status="approved")
    assert guard_request("What is the final FY2031 budget?", [aliases]) is None


def test_comparison_requires_evidence_for_each_requested_fiscal_year():
    question = "Compare adopted 2031 and 2032 budgets."
    assert_missing(guard_request(question, [adopted()]))
    assert guard_request(question, [adopted(), adopted("other", year=2032)]) is None


def test_unknown_requested_year_does_not_infer_current_year():
    assert_missing(guard_request("What is the approved budget?", [source()]))
    assert guard_request("What is the approved budget?", [adopted(year=2030)]) is None
    result = answer("The 2030 approved budget is $1234.", ["budget-adopted"])
    assert (
        guard_answer("What is the approved budget?", result, [adopted(year=2030)])
        == result
    )
    assert_missing(
        guard_answer(
            "What is the approved budget?",
            answer("The approved budget is $1234.", ["budget-adopted"]),
            [adopted()],
        )
    )


def test_blank_adoption_template_and_fresh_fetch_do_not_supply_proof():
    document = source(fetched_at="2031-09-01", adoption_verified=False)
    document["text"] = "CERTIFICATION OF ADOPTED BUDGET. Adoption date: ____"
    assert_missing(guard_request("Was the 2031 budget adopted?", [document]))
    result = answer("The 2031 budget was approved.")
    assert_missing(
        guard_answer("What does the budget document show?", result, [document])
    )


def test_false_approval_is_blocked_despite_valid_introduced_citation():
    result = answer("The approved 2031 budget is $1234.")
    guarded = guard_answer("What does the budget document show?", result, [source()])
    assert_missing(guarded)
    assert guarded["model"] == "offline-fixture"
    assert result["insufficient_evidence"] is False


def test_cited_budget_metadata_prevents_resolution_wording_bypass():
    question = "What is the approved 2026 total in the resolution?"
    result = answer("The approved 2026 total in the resolution is $1234.")
    assert_missing(guard_answer(question, result, [source(year=2026)]))


def test_uncited_adopted_record_cannot_legitimize_an_introduced_citation():
    result = answer("The adopted 2031 budget is $1234.")
    assert_missing(
        guard_answer("What is the approved 2031 budget?", result, [source(), adopted()])
    )


def test_answer_year_must_also_match_cited_adoption_evidence():
    result = answer("The approved 2032 budget is $1234.", ["budget-adopted"])
    assert_missing(
        guard_answer("What is the approved 2031 budget?", result, [adopted()])
    )


@pytest.mark.parametrize(
    "text",
    [
        "The source is introduced, not adopted.",
        "The source is introduced, not adopted or approved.",
        "I cannot verify approved budget data from this source.",
        "There is no evidence that the 2031 budget was adopted.",
        "The adoption date is unknown.",
        "This is not a final approved budget.",
        "This is not a final adopted budget.",
        "The source is not **approved**.",
        "I cannot verify any approved budget from this source.",
    ],
)
def test_negated_and_uncertain_status_is_not_a_positive_approval_claim(text):
    result = answer(text, insufficient=True)
    assert (
        guard_answer("What is the approved 2031 budget?", result, [source()]) == result
    )


def test_negation_cannot_hide_a_later_affirmative_claim():
    result = answer("The PDF is not adopted, but the approved 2031 budget is $1234.")
    assert_missing(guard_answer("What does the budget show?", result, [source()]))
    result = answer("No changes were made to the approved 2031 budget.")
    assert_missing(guard_answer("What does the budget show?", result, [source()]))
    result = answer("The 2031 budget is not proposed; it is approved.")
    assert_missing(guard_answer("What does the budget show?", result, [source()]))


def test_proposed_tax_labels_and_numbers_are_preserved_not_fact_checked():
    question = "What is the proposed 2031 budget tax levy?"
    result = answer("The introduced tax levy is $9876, not a total-budget figure.")
    assert guard_request(question, [source()]) is None
    assert guard_answer(question, result, [source()]) == result
    result = answer("The 2031 approved tax levy is $9876.", ["budget-adopted"])
    assert (
        guard_answer("What is the approved 2031 budget tax levy?", result, [adopted()])
        == result
    )


@pytest.mark.parametrize(
    "question,text",
    [
        ("Was ordinance 26-1056 adopted?", "The ordinance was adopted."),
        ("Is the meeting agenda final?", "The meeting agenda is final."),
    ],
)
def test_nonbudget_status_is_not_changed_by_a_budget_neighbor(question, text):
    other = {"chunk_id": "other", "metadata": {"kind": "meeting"}, "text": text}
    chunks = [source(), other]
    result = answer(text, ["other"])
    assert guard_request(question, chunks) is None
    assert guard_answer(question, result, chunks) == result
