import pytest
from app.graph import DatabaseUnavailable, ReviewConflict, GraphRepository
from app.service import Service
from app.demo import examples, load_demo
from app.schemas import DocumentInput
from app.risk import assess

pytestmark = pytest.mark.integration


def test_read_tools_reject_writes(graph_repo):
    with pytest.raises(DatabaseUnavailable):
        graph_repo.query("forbidden", "CREATE (:Forbidden) RETURN 1")
    assert graph_repo.query("check", "MATCH (n:Forbidden) RETURN count(n)")[0][0] == 0


def test_supersession_first_repeat_stale_and_reconnect(graph_repo):
    s = Service(graph_repo)
    load_demo(s)
    before = {r["id"]: r["status"] for r in s.assessment()["assessments"]}
    assert before["acme_sso"] == before["beacon_sso"] == "at_risk"
    revision = examples()["revision"]
    pending = s.ingest(
        DocumentInput.model_validate(revision["document"]),
        "rehearsal",
        revision["fixture"],
    )["facts"][0]
    old = graph_repo.current("acme_sso|deadline")
    with pytest.raises(ReviewConflict):
        graph_repo.review(pending["id"], "accept")
    with pytest.raises(ReviewConflict):
        graph_repo.review(pending["id"], "accept", "stale_id", True)
    graph_repo.review(pending["id"], "accept", old["id"], True)
    assert graph_repo.review(pending["id"], "accept", old["id"], True)["idempotent"]
    assert graph_repo.fact(old["id"])["status"] == "superseded"
    assert len(graph_repo.history()) == 1
    reconnected = GraphRepository(graph_repo.settings)
    assert reconnected.current("acme_sso|deadline")["date"] == "2026-11-10"
    bundle = Service(reconnected).assessment()
    assert old["id"] in bundle["evidence"] and pending["id"] in bundle["evidence"]
    after = {r["id"]: r for r in bundle["assessments"]}
    assert after["acme_sso"]["status"] == "no_known_conflict"
    assert after["beacon_sso"]["status"] == "at_risk"
    assert "forecast_order_conflict" in after["acme_sso"]["flags"]


def test_ingestion_idempotent_and_provenance(graph_repo):
    s = Service(graph_repo)
    load_demo(s)
    n = len(graph_repo.facts())
    load_demo(s)
    assert len(graph_repo.facts()) == n
    assert all(f["status"] == "accepted" for f in graph_repo.facts())
    bundle = s.assessment()
    assert all(
        e["span"]["quote"] and e["author"]["name"] for e in bundle["evidence"].values()
    )
    r = next(r for r in bundle["assessments"] if r["id"] == "acme_sso")
    assert len(r["conflicts"][0]["path"]["facts"]) == 3


def test_conflicting_new_date_preserves_current(graph_repo):
    s = Service(graph_repo)
    load_demo(s)
    item = examples()["revision"]
    item["fixture"]["facts"][0]["replaces_date_expression"] = ""
    f = s.ingest(
        DocumentInput.model_validate(item["document"]), "rehearsal", item["fixture"]
    )["facts"][0]
    old = graph_repo.current("acme_sso|deadline")
    with pytest.raises(ReviewConflict):
        graph_repo.review(f["id"], "accept", old["id"], True)
    assert graph_repo.current("acme_sso|deadline")["id"] == old["id"]


def test_bounded_cycle_query_terminates(graph_repo):
    # This is a database traversal fixture, not accepted product knowledge.
    graph_repo.query(
        "cycle",
        "MATCH (a:Entity {id:'acme_sso'}),(b:Entity {id:'sso'}),(c:Entity {id:'identity'}) CREATE (a)-[:REQUIRES {fact_id:'a'}]->(b), (b)-[:REQUIRES {fact_id:'b'}]->(c), (c)-[:REQUIRES {fact_id:'c'}]->(b)",
        write=True,
    )
    rows = graph_repo.query("paths", params={"id": "acme_sso"})
    assert rows and all(len(fs) <= 8 for _, fs in rows)
    assert any(len(set(ns)) < len(ns) for ns, _ in rows)


def test_cedar_review_sample_preserves_other_customers_and_missing_work_gap(graph_repo):
    service = Service(graph_repo)
    load_demo(service)
    sample = examples()["review_sample"]
    proposal = service.ingest(
        DocumentInput.model_validate(sample["document"]), "rehearsal", sample["fixture"]
    )["facts"][0]
    before = {r["id"]: r for r in service.assessment()["assessments"]}
    assert "pending_relevant_fact" in before["cedar_export"]["flags"]
    assert "pending_relevant_fact" not in before["acme_sso"]["flags"]
    old = graph_repo.current("cedar_export|deadline")
    graph_repo.review(proposal["id"], "accept", old["id"], True)
    bundle = service.assessment()
    after = {r["id"]: r for r in bundle["assessments"]}
    assert after["cedar_export"]["deadline"] == "2026-11-12"
    assert after["cedar_export"]["status"] == "unknown"
    assert "unlinked_commitment" in after["cedar_export"]["flags"]
    assert after["acme_sso"]["status"] == after["beacon_sso"]["status"] == "at_risk"
    assert {p["id"] for p in after["beacon_sso"]["contributors"]} == {
        "maya",
        "leo",
        "priya",
    }
    # Each assessment trace must contain its own read operations, not setup,
    # queue checks, previous assessments, or the review write.
    assert [q["name"] for q in bundle["query_trace"]].count("entities") == 1
    assert not {"current", "fact", "document", "supersede"} & {
        q["name"] for q in bundle["query_trace"]
    }
    again = service.ingest(
        DocumentInput.model_validate(sample["document"]), "rehearsal", sample["fixture"]
    )
    assert again["duplicate"] and not graph_repo.facts("pending")
