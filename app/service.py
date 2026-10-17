import json
from .graph import GraphRepository, LOCK, ReviewConflict
from .ingest import prepare_document, validate_candidate
from .schemas import DocumentInput, Extraction
from .llm import Gemini, PROMPT_HASH
from .risk import assess, exposure


def source_contributors(result, evidence, entities):
    """Authors of accepted evidence on the displayed proof, never inferred owners."""
    conflict = next(iter(result["conflicts"]), None)
    path = (
        conflict["path"]
        if conflict
        else max(result["paths"], key=lambda item: len(item["nodes"]), default=None)
    )
    path_fact_ids = set(path["facts"]) if path else set()
    path_node_ids = set(path["nodes"]) if path else {result["id"]}
    entity_names = {entity["id"]: entity["name"] for entity in entities}
    people = {}
    for fact_id in result["evidence_ids"]:
        source_evidence = evidence.get(fact_id)
        if not source_evidence or source_evidence["fact"]["status"] != "accepted":
            continue
        fact = source_evidence["fact"]
        relevant = (
            fact_id in path_fact_ids
            or (fact["kind"] == "deadline" and fact["subject_id"] == result["id"])
            or (fact["kind"] == "forecast" and fact["subject_id"] in path_node_ids)
        )
        author = source_evidence.get("author") or {}
        if not relevant or not author.get("id"):
            continue
        person = people.setdefault(
            author["id"],
            {
                "id": author["id"],
                "name": author["name"],
                "role": author.get("role", ""),
                "sources": {},
            },
        )
        document = source_evidence["document"]
        source = person["sources"].setdefault(
            document["id"],
            {
                "document_id": document["id"],
                "title": document["title"],
                "fact_ids": [],
                "context": [],
            },
        )
        source["fact_ids"].append(fact_id)
        context = (
            entity_names.get(fact["subject_id"], fact["subject_id"])
            + " · "
            + fact["kind"]
        )
        if context not in source["context"]:
            source["context"].append(context)
    return [
        {
            **person,
            "sources": sorted(
                person["sources"].values(), key=lambda source: source["title"]
            ),
        }
        for person in sorted(people.values(), key=lambda person: person["name"])
    ]


class Service:
    def __init__(self, repo=None, model=None):
        self.repo = repo or GraphRepository()
        self.model = model or Gemini(self.repo.settings)

    def ingest(self, payload: DocumentInput, mode="live", fixture=None):
        doc = prepare_document(
            payload,
            mode,
            self.repo.settings.model if mode == "live" else "hand-authored-fixture",
            PROMPT_HASH,
        )
        with LOCK:
            self.repo.initialize()
            existing = self.repo.document(doc["id"])
            if existing and existing["state"] == "ready":
                if existing.get("mode") != mode:
                    raise ReviewConflict(
                        "This document already exists in a different extraction mode. Use a new graph name to compare live extraction and rehearsal."
                    )
                return {
                    "document": existing,
                    "facts": [f for f in self.repo.facts() if f["doc_id"] == doc["id"]],
                    "duplicate": True,
                }
            if existing and existing["state"] == "extracting":
                raise ReviewConflict(
                    "This document is already extracting. Wait for that request to finish."
                )
            if existing and existing.get("mode") != mode:
                raise ReviewConflict(
                    "Use a new graph to change this document's extraction mode."
                )
            if existing and any(f["doc_id"] == doc["id"] for f in self.repo.facts()):
                raise ReviewConflict(
                    "This failed ingestion left partial proposals. Use a new correction document or a fresh graph; partial reprocessing is not supported."
                )
            self.repo.save_document(doc)
            metadata = {
                "state": "extracting",
                "error": "",
                "model": doc["model"],
                "prompt_hash": doc["prompt_hash"],
            }
            if existing and existing.get("raw_response"):
                earlier = json.loads(existing.get("previous_attempts", "[]"))
                earlier.append(
                    {
                        "model": existing.get("model"),
                        "prompt_hash": existing.get("prompt_hash"),
                        "raw_response": existing["raw_response"],
                        "error": existing.get("error"),
                    }
                )
                metadata["previous_attempts"] = json.dumps(earlier)
            self.repo.update_document(doc["id"], metadata)
        try:
            if mode == "live":
                extraction, raw = self.model.extract(doc)
            else:
                if fixture is None:
                    raise ValueError(
                        "Rehearsal accepts only the supplied, explicitly labeled fixtures."
                    )
                extraction = Extraction.model_validate(fixture)
                raw = {
                    "source": "hand-authored fixture; not a model run",
                    "response": fixture,
                }
            facts = [validate_candidate(c, doc) for c in extraction.facts]
            with LOCK:
                self.repo.update_document(
                    doc["id"],
                    {
                        "raw_response": json.dumps(raw, ensure_ascii=False),
                        "request_settings": json.dumps(
                            {"temperature": 0, "schema_version": 1}
                        ),
                    },
                )
                self.repo.save_facts(doc["id"], facts)
            return {
                "document": self.repo.document(doc["id"]),
                "facts": facts,
                "duplicate": False,
            }
        except Exception as exc:
            with LOCK:
                values = {"state": "failed", "error": str(exc)[:400]}
                if hasattr(exc, "raw_response"):
                    values["raw_response"] = json.dumps(exc.raw_response)
                self.repo.update_document(doc["id"], values)
            raise

    def assessment(self, selected=None):
        with LOCK:
            trace_start = len(self.repo.trace)
            snap = self.repo.snapshot()
            known = {e["id"] for e in snap["entities"] if e["kind"] == "commitment"}
            if selected and not set(selected) <= known:
                raise ValueError("Unknown commitment scope.")
            results = assess(snap, selected)
            ids = {fid for result in results for fid in result["evidence_ids"]}
            subjects = {result["id"] for result in results}
            history = [
                h for h in self.repo.history() if h["new"]["subject_id"] in subjects
            ]
            ids.update(f["id"] for h in history for f in (h["new"], h["old"]))
            evidence = self.repo.evidence(ids)
            for result in results:
                result["contributors"] = source_contributors(
                    result, evidence, snap["entities"]
                )
            # Evidence reads are part of the same application-level read critical section.
            return {
                "assessments": results,
                "evidence": evidence,
                "history": history,
                "entities": snap["entities"],
                "edges": snap["edges"],
                "exposure": exposure(snap, results),
                "query_trace": list(self.repo.trace[trace_start:]),
                "source_modes": sorted(
                    {d.get("mode", "unknown") for d in snap["documents"]}
                ),
                "documents": [
                    {
                        k: v
                        for k, v in d.items()
                        if k
                        not in ("raw_response", "request_settings", "previous_attempts")
                    }
                    for d in snap["documents"]
                ],
            }

    def queue(self):
        facts = self.repo.facts()
        evidence = self.repo.evidence([f["id"] for f in facts])
        for f in facts:
            f["evidence"] = evidence.get(f["id"])
            f["current"] = (
                self.repo.current(f["slot_id"])
                if f["kind"] != "requires" and f["subject_id"]
                else None
            )
        return facts
