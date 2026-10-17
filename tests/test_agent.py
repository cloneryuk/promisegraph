from types import SimpleNamespace
from app.agent import run_agent
from app.risk import assess
from app.ingest import catalog
from .fixtures import snapshot
import pytest
from app.agent import normalize_citations


def test_grouped_citations_preserve_each_opened_source():
    assert (
        normalize_citations("Proof [fact_abc, fact_def].", {"fact_abc", "fact_def"})
        == "Proof [fact_abc] [fact_def]."
    )


@pytest.mark.parametrize("group", ["fact_abc, fact_invented", "fact_abc, fact_fff"])
def test_grouped_citation_cannot_hide_an_unopened_source(group):
    with pytest.raises(ValueError):
        normalize_citations("One [fact_abc]. More [" + group + "].", {"fact_abc"})


class ServiceDouble:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.model = SimpleNamespace(
            generate=lambda *a, **k: (next(self.responses), {})
        )
        self.snap = snapshot()

    def assessment(self, ids):
        results = assess(self.snap, ids)
        ids = {fid for r in results for fid in r["evidence_ids"]}
        evidence = {f["id"]: {"fact": f} for f in self.snap["facts"] if f["id"] in ids}
        return {"assessments": results, "evidence": evidence}


def call(name, args):
    return {"role": "model", "parts": [{"functionCall": {"name": name, "args": args}}]}


def test_actual_tool_events_and_citation_validation():
    f = next(
        f
        for f in snapshot()["facts"]
        if f["subject_id"] == "rotation" and f["kind"] == "forecast"
    )
    service = ServiceDouble(
        [
            call("assess_commitments", {"ids": ["acme_sso"]}),
            call("read_evidence", {"fact_ids": [f["id"]]}),
            {
                "role": "model",
                "parts": [
                    {"text": "Rotation is forecast for 2026-11-06 [" + f["id"] + "]."}
                ],
            },
        ]
    )
    result = run_agent(service, "Explain Acme conflicts", scope=["acme_sso"])
    assert not result["warning"] and len(result["agent_trace"]) == 2
    assert result["agent_trace"][0]["source"] == "Gemini"


def test_invalid_evidence_falls_back_after_computation():
    service = ServiceDouble(
        [
            call("assess_commitments", {"ids": []}),
            call("read_evidence", {"fact_ids": ["fact_invented"]}),
        ]
    )
    result = run_agent(service, "What conflicts exist?")
    assert result["warning"].startswith("Grounded template used:")
    assert result["assessments"][0]["status"] == "at_risk"


def test_rehearsal_is_explicit_and_uses_no_model_call():
    result = run_agent(ServiceDouble([]), "Explain commitments", mode="rehearsal")
    assert result["agent_mode"] == "rehearsal"
    assert all(t["source"] == "scripted rehearsal" for t in result["agent_trace"])


def test_mixed_valid_and_invented_citations_are_rejected():
    f = next(
        f
        for f in snapshot()["facts"]
        if f["subject_id"] == "rotation" and f["kind"] == "forecast"
    )
    service = ServiceDouble(
        [
            call("assess_commitments", {"ids": []}),
            call("read_evidence", {"fact_ids": [f["id"]]}),
            {
                "role": "model",
                "parts": [{"text": "Sources [" + f["id"] + "] and [fact_invented]."}],
            },
        ]
    )
    result = run_agent(service, "Explain conflicts")
    assert result["warning"].startswith("Grounded template used:")


def test_trace_attaches_queries_only_to_assessment_and_retains_earlier_opened_sources():
    service = ServiceDouble([])
    original = service.assessment

    def assessment(ids):
        return {
            **original(ids),
            "query_trace": [
                {
                    "name": "paths",
                    "cypher": "MATCH p RETURN p",
                    "parameters": {"ids": ids},
                    "elapsed_ms": 1,
                }
            ],
        }

    service.assessment = assessment
    acme = next(
        f["id"]
        for f in service.snap["facts"]
        if f["subject_id"] == "acme_sso" and f["kind"] == "deadline"
    )
    beacon = next(
        f["id"]
        for f in service.snap["facts"]
        if f["subject_id"] == "beacon_sso" and f["kind"] == "deadline"
    )
    service.responses = iter(
        [
            call("assess_commitments", {"ids": ["acme_sso"]}),
            call("read_evidence", {"fact_ids": [acme]}),
            call("assess_commitments", {"ids": ["beacon_sso"]}),
            call("read_evidence", {"fact_ids": [beacon]}),
            {
                "role": "model",
                "parts": [{"text": "Beacon has a deadline conflict [" + beacon + "]."}],
            },
        ]
    )
    result = run_agent(service, "Trace the commitments")
    assert not result["warning"]
    assert [len(t["queries"]) for t in result["agent_trace"]] == [1, 0, 1, 0]
    assert len(result["query_trace"]) == 2
    assert set(result["trace_evidence"]) == {acme, beacon}
    assert result["opened_evidence"] == [beacon]
    assert "no additional database query" in result["agent_trace"][1]["operation"]
