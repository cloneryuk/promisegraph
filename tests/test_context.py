from copy import deepcopy
from app.demo import examples
from app.ingest import catalog, prepare_document, validate_candidate
from app.schemas import DocumentInput, Candidate
from app.risk import assess
from app.service import source_contributors
from .fixtures import snapshot


def test_contributors_follow_displayed_proof_and_exclude_other_branch_and_history():
    snap = snapshot()
    row = next(r for r in assess(snap) if r["id"] == "beacon_sso")
    docs = {d["id"]: d for d in snap["documents"]}
    people = {p["id"]: p for p in catalog()["people"]}
    evidence = {
        f["id"]: {
            "fact": f,
            "document": docs[f["doc_id"]],
            "author": people[docs[f["doc_id"]]["author_id"]],
        }
        for f in snap["facts"]
    }
    # A separately authored forecast on a parallel branch must not become a
    # contributor to the displayed rotation proof.
    security = next(f for f in snap["facts"] if f["subject_id"] == "security")
    evidence[security["id"]]["author"] = {"id": "other", "name": "Other branch author"}
    old = deepcopy(evidence[row["conflicts"][0]["deadline_fact_id"]])
    old["fact"]["status"] = "superseded"
    old["author"] = {"id": "former", "name": "Earlier author"}
    evidence["old"] = old
    row["evidence_ids"].append("old")
    contributors = source_contributors(row, evidence, snap["entities"])
    assert {p["id"] for p in contributors} == {"maya", "leo", "priya"}
    ids = {fid for p in contributors for s in p["sources"] for fid in s["fact_ids"]}
    assert security["id"] not in ids and "old" not in ids
    assert set(row["conflicts"][0]["path"]["facts"]) <= ids
    assert row["conflicts"][0]["forecast_fact_id"] in ids
    assert row["conflicts"][0]["deadline_fact_id"] in ids


def test_unlinked_commitment_only_lists_its_own_source_author():
    snap = snapshot()
    row = next(r for r in assess(snap) if r["id"] == "cedar_export")
    f = next(f for f in snap["facts"] if f["id"] in row["evidence_ids"])
    evidence = {
        f["id"]: {
            "fact": f,
            "document": {"id": f["doc_id"], "title": "Call notes"},
            "author": {"id": "maya", "name": "Maya Chen", "role": "Customer success"},
        }
    }
    assert [p["id"] for p in source_contributors(row, evidence, snap["entities"])] == [
        "maya"
    ]
    evidence[f["id"]]["author"] = {}
    assert source_contributors(row, evidence, snap["entities"]) == []


def test_natural_demo_and_review_sample_keep_valid_exact_source_spans():
    sample = examples()
    documents = sample["baseline"] + [sample["revision"], sample["review_sample"]]
    for item in documents:
        doc = prepare_document(
            DocumentInput.model_validate(item["document"]),
            "rehearsal",
            "fixture",
            "test",
        )
        for raw in item["fixture"]["facts"]:
            fact = validate_candidate(Candidate.model_validate(raw), doc)
            assert not fact["validation_flags"]
            assert doc["text"][fact["start"] : fact["end"]] == fact["quote"]
    assert len(sample["review_sample"]["fixture"]["facts"]) == 1
    assert (
        sample["review_sample"]["fixture"]["facts"][0]["replaces_date_expression"]
        == "November 8, 2026"
    )
