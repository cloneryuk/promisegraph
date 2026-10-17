import pytest
from app.demo import examples
from app.ingest import (
    prepare_document,
    validate_candidate,
    parse_date,
    resolve,
    catalog,
)
from app.schemas import DocumentInput, Candidate


def validate(quote, **kwargs):
    doc = prepare_document(
        DocumentInput(
            title="Test",
            text=quote,
            source_type="chat",
            author_id="priya",
            timestamp="2026-11-01T10:00:00+05:30",
        ),
        "rehearsal",
        "fixture",
        "test",
    )
    c = Candidate(
        kind="forecast",
        subject="signing-key rotation",
        quote=quote,
        date_expression="November 6, 2026",
        **kwargs,
    )
    return validate_candidate(c, doc)


def test_all_demo_proposals_validate():
    for item in [*examples()["baseline"], examples()["revision"]]:
        doc = prepare_document(
            DocumentInput.model_validate(item["document"]),
            "rehearsal",
            "fixture",
            "test",
        )
        for c in item["fixture"]["facts"]:
            f = validate_candidate(Candidate.model_validate(c), doc)
            assert not f["validation_flags"]
            assert doc["text"][f["start"] : f["end"]] == f["quote"]


@pytest.mark.parametrize(
    "expression", ["tomorrow", "next Friday", "Nov 6", "the 6th", "2026-02-30"]
)
def test_unsupported_dates(expression):
    assert parse_date(expression) == ""


@pytest.mark.parametrize("expression", ["November 6, 2026", "Nov 6 2026", "2026-11-06"])
def test_full_date_formats(expression):
    assert parse_date(expression) == "2026-11-06"


def test_aliases_exact_only():
    es = catalog()["entities"]
    assert resolve("single sign-on rollout", es) == "sso"
    assert resolve("Okta integration", es) == ""


def test_date_must_be_literal_in_quote():
    f = validate("signing-key rotation finishes November 7, 2026.")
    assert "date_not_in_quote" in f["validation_flags"]


def test_negation_is_not_accepted_as_affirmation():
    f = validate("signing-key rotation will not finish on November 6, 2026.")
    assert "semantic_review_required" in f["validation_flags"]


def test_fabricated_quote_blocked():
    item = examples()["baseline"][2]
    doc = prepare_document(
        DocumentInput.model_validate(item["document"]), "rehearsal", "fixture", "test"
    )
    c = Candidate.model_validate(item["fixture"]["facts"][0])
    c.quote += " invented"
    assert "quote_missing" in validate_candidate(c, doc)["validation_flags"]


def test_repeated_quote_is_ambiguous():
    quote = "signing-key rotation finishes November 6, 2026."
    doc = prepare_document(
        DocumentInput(
            title="Test",
            text=quote + " " + quote,
            source_type="chat",
            author_id="priya",
            timestamp="2026-11-01T10:00:00+05:30",
        ),
        "rehearsal",
        "fixture",
        "test",
    )
    c = Candidate(
        kind="forecast",
        subject="signing-key rotation",
        quote=quote,
        date_expression="November 6, 2026",
    )
    assert "quote_ambiguous" in validate_candidate(c, doc)["validation_flags"]


def test_document_id_deterministic():
    p = DocumentInput.model_validate(examples()["baseline"][0]["document"])
    assert (
        prepare_document(p, "live", "model", "v1")["id"]
        == prepare_document(p, "rehearsal", "fixture", "v2")["id"]
    )
