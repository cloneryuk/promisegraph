"""Pure risk fixtures. These simulate graph query rows, not a product database fallback."""

from app.demo import examples
from app.ingest import prepare_document, validate_candidate, catalog
from app.schemas import DocumentInput, Candidate


def snapshot():
    out = {
        "entities": catalog()["entities"],
        "facts": [],
        "documents": [],
        "slots": {},
        "edges": [],
        "paths": {},
    }
    for item in examples()["baseline"]:
        doc = prepare_document(
            DocumentInput.model_validate(item["document"]),
            "rehearsal",
            "fixture",
            "test",
        )
        doc["state"] = "ready"
        out["documents"].append(doc)
        for c in item["fixture"]["facts"]:
            f = validate_candidate(Candidate.model_validate(c), doc)
            assert not f["validation_flags"]
            f["status"] = "accepted"
            out["facts"].append(f)
            if f["kind"] == "requires":
                out["edges"].append(
                    {
                        "source": f["subject_id"],
                        "target": f["object_id"],
                        "fact_id": f["id"],
                    }
                )
            else:
                out["slots"][f["slot_id"]] = f["id"]
    build_paths(out)
    return out


def build_paths(out):
    paths = {}

    def walk(nodes, facts, collected):
        if len(facts) == 8:
            return
        for e in out["edges"]:
            if e["source"] == nodes[-1] and e["fact_id"] not in facts:
                path = {"nodes": nodes + [e["target"]], "facts": facts + [e["fact_id"]]}
                collected.append(path)
                walk(path["nodes"], path["facts"], collected)

    for e in out["entities"]:
        if e["kind"] == "commitment":
            paths[e["id"]] = []
            walk([e["id"]], [], paths[e["id"]])
    out["paths"] = paths


def add_work(out, name, date="2026-11-03"):
    out["entities"].append({"id": name, "name": name, "kind": "work"})
    add_fact(out, name, "forecast", date=date)


def add_fact(out, subject, kind, date="", target=""):
    fid = "test_" + str(len(out["facts"]))
    f = {
        "id": fid,
        "subject_id": subject,
        "object_id": target,
        "kind": kind,
        "date": date,
        "status": "accepted",
        "validation_flags": [],
        "quote": "test source",
        "start": 0,
        "doc_id": out["documents"][0]["id"],
        "slot_id": subject + "|" + kind,
    }
    out["facts"].append(f)
    if kind == "requires":
        out["edges"].append({"source": subject, "target": target, "fact_id": fid})
    else:
        out["slots"][f["slot_id"]] = fid
    return f


def find(out, subject, kind):
    return next(
        f for f in out["facts"] if f["subject_id"] == subject and f["kind"] == kind
    )
