import json
import threading
import time
from datetime import datetime
from pathlib import Path
from falkordb import FalkorDB
from .config import ROOT, Settings
from .ingest import catalog

LOCK = threading.RLock()


class DatabaseUnavailable(RuntimeError):
    pass


class ReviewConflict(ValueError):
    pass


class GraphRepository:
    """All authoritative application records and relationship traversals live in FalkorDB."""

    def __init__(self, settings=None):
        self.settings = settings or Settings.load()
        try:
            self.db = FalkorDB(
                host=self.settings.host,
                port=self.settings.port,
                username=self.settings.username,
                password=self.settings.password or None,
                ssl=self.settings.ssl,
                ssl_check_hostname=True,
                socket_connect_timeout=3,
                socket_timeout=6,
            )
        except Exception as exc:
            raise DatabaseUnavailable(
                "Cannot connect to FalkorDB. Check the host, port, credentials and TLS setting in .env."
            ) from exc
        self.graph = self.db.select_graph(self.settings.graph)
        self.trace = []

    def query(self, name, cypher=None, params=None, write=False):
        query = cypher or (ROOT / "app/queries" / (name + ".cypher")).read_text(
            encoding="utf-8"
        )
        started = time.perf_counter()
        try:
            if write:
                result = self.graph.query(query, params or {})
            else:
                result = self.graph.ro_query(
                    query, params or {}, timeout=self.settings.read_timeout_ms
                )
        except Exception as exc:
            raise DatabaseUnavailable(
                f"FalkorDB operation '{name}' failed ({type(exc).__name__}). Check the connection and server logs."
            ) from exc
        if not write:
            self.trace.append(
                {
                    "name": name,
                    "cypher": query,
                    "parameters": params or {},
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            )
        return result.result_set

    def initialize(self):
        with LOCK:
            for e in catalog()["entities"]:
                self.query(
                    "entity",
                    "MERGE (e:Entity {id:$id}) SET e += $props RETURN e.id",
                    {"id": e["id"], "props": e},
                    write=True,
                )
                kind = "deadline" if e["kind"] == "commitment" else "forecast"
                self.query(
                    "slot",
                    "MERGE (s:Slot {id:$id}) ON CREATE SET s.current = '' RETURN s.id",
                    {"id": e["id"] + "|" + kind},
                    write=True,
                )
            for p in catalog()["people"]:
                self.query(
                    "person",
                    "MERGE (p:Person {id:$id}) SET p += $props RETURN p.id",
                    {"id": p["id"], "props": p},
                    write=True,
                )

    def check_connection(self):
        try:
            self.db.execute_command("GRAPH.LIST")
        except Exception as exc:
            raise DatabaseUnavailable(
                "FalkorDB is unreachable or GRAPH commands are unavailable. Check the connection details."
            ) from exc

    def document(self, doc_id):
        rows = self.query(
            "document",
            "MATCH (d:Document {id:$id}) RETURN properties(d)",
            {"id": doc_id},
        )
        return rows[0][0] if rows else None

    def save_document(self, doc):
        self.query(
            "save_document",
            """MATCH (p:Person {id:$author})
MERGE (d:Document {id:$id}) ON CREATE SET d += $props
MERGE (p)-[:AUTHORED {basis:'user_supplied'}]->(d) RETURN properties(d)""",
            {"author": doc["author_id"], "id": doc["id"], "props": doc},
            write=True,
        )

    def update_document(self, doc_id, values):
        self.query(
            "update_document",
            "MATCH (d:Document {id:$id}) SET d += $props RETURN d.id",
            {"id": doc_id, "props": values},
            write=True,
        )

    def save_facts(self, doc_id, facts):
        # A document is not reviewable until all candidate writes complete.
        for f in facts:
            self.query(
                "candidate",
                """MATCH (d:Document {id:$doc})
MERGE (s:Span {id:$span}) ON CREATE SET s.start=$start, s.end=$end, s.quote=$quote
MERGE (d)-[:HAS_SPAN]->(s)
MERGE (f:Fact {id:$id}) ON CREATE SET f += $props
MERGE (f)-[:SUPPORTED_BY]->(s) RETURN f.id""",
                {
                    "doc": doc_id,
                    "span": f["span_id"],
                    "start": f["start"],
                    "end": f["end"],
                    "quote": f["quote"],
                    "id": f["id"],
                    "props": f,
                },
                write=True,
            )
            for relation, field in (("SUBJECT", "subject_id"), ("OBJECT", "object_id")):
                if f[field]:
                    self.query(
                        "fact_entity",
                        f"""MATCH (f:Fact {{id:$id}}), (e:Entity {{id:$entity}})
MERGE (f)-[:{relation}]->(e) RETURN f.id""",
                        {"id": f["id"], "entity": f[field]},
                        write=True,
                    )
        self.update_document(doc_id, {"state": "ready", "error": ""})

    def facts(self, status=None):
        rows = self.query("facts", "MATCH (f:Fact) RETURN properties(f)")
        facts = [r[0] for r in rows]
        return [f for f in facts if not status or f["status"] == status]

    def fact(self, fact_id):
        rows = self.query(
            "fact", "MATCH (f:Fact {id:$id}) RETURN properties(f)", {"id": fact_id}
        )
        return rows[0][0] if rows else None

    def current(self, slot_id):
        rows = self.query(
            "current",
            """MATCH (s:Slot {id:$id})
OPTIONAL MATCH (f:Fact {id:s.current}) RETURN properties(f)""",
            {"id": slot_id},
        )
        return rows[0][0] if rows and rows[0][0] else None

    def review(
        self, fact_id, action, expected_old_id="", confirm_replacement=False, reason=""
    ):
        with LOCK:
            f = self.fact(fact_id)
            if not f:
                raise ReviewConflict("Fact not found.")
            if f["status"] == "accepted" and action == "accept":
                return {"fact": f, "idempotent": True}
            if f["status"] == "rejected" and action == "reject":
                return {"fact": f, "idempotent": True}
            if f["status"] != "pending":
                raise ReviewConflict(
                    "This fact is no longer pending. Refresh the review queue."
                )
            doc = self.document(f["doc_id"])
            if not doc or doc["state"] != "ready":
                raise ReviewConflict("Document extraction is incomplete.")
            now = datetime.now().astimezone().isoformat()
            if action == "reject":
                self.query(
                    "reject",
                    """MATCH (f:Fact {id:$id}) WHERE f.status='pending'
SET f.status='rejected', f.reviewed_at=$now, f.review_reason=$reason RETURN f.id""",
                    {
                        "id": fact_id,
                        "now": now,
                        "reason": reason or "Rejected during review",
                    },
                    write=True,
                )
            else:
                if f["validation_flags"]:
                    raise ReviewConflict(
                        "Validation blocks acceptance: "
                        + ", ".join(f["validation_flags"])
                    )
                if f["kind"] == "requires":
                    rows = self.query(
                        "accept_dependency",
                        params={
                            "id": fact_id,
                            "subject": f["subject_id"],
                            "object": f["object_id"],
                            "now": now,
                            "reason": reason or "Accepted by local reviewer",
                        },
                        write=True,
                    )
                else:
                    old = self.current(f["slot_id"])
                    if old:
                        if not confirm_replacement or expected_old_id != old["id"]:
                            raise ReviewConflict(
                                "An active value exists. Review and explicitly confirm its replacement."
                            )
                        if f["old_date"] != old["date"]:
                            raise ReviewConflict(
                                "The quoted replacement does not match the current date."
                            )
                        rows = self.query(
                            "supersede",
                            params={
                                "id": fact_id,
                                "old_id": old["id"],
                                "slot": f["slot_id"],
                                "now": now,
                                "reason": reason
                                or "Replacement confirmed by local reviewer",
                            },
                            write=True,
                        )
                    else:
                        if expected_old_id or f["old_date"]:
                            raise ReviewConflict(
                                "The expected earlier fact is absent; cannot apply replacement."
                            )
                        rows = self.query(
                            "accept_date",
                            params={
                                "id": fact_id,
                                "slot": f["slot_id"],
                                "now": now,
                                "reason": reason or "Accepted by local reviewer",
                            },
                            write=True,
                        )
                if not rows:
                    raise ReviewConflict(
                        "Guarded write made no changes. The fact is stale or duplicates an accepted dependency."
                    )
            return {"fact": self.fact(fact_id), "idempotent": False}

    def evidence(self, ids):
        if not ids:
            return {}
        rows = self.query("evidence", params={"ids": list(set(ids))})
        out = {}
        for f, s, d, p in rows:
            out[f["id"]] = {
                "fact": f,
                "span": s,
                "document": {
                    k: d.get(k)
                    for k in (
                        "id",
                        "title",
                        "source_type",
                        "timestamp",
                        "timezone",
                        "mode",
                        "model",
                    )
                },
                "author": p or {},
            }
        return out

    def history(self):
        rows = self.query("history")
        return [{"new": a, "old": b} for a, b in rows]

    def snapshot(self):
        with LOCK:
            entities = [
                r[0]
                for r in self.query("entities", "MATCH (e:Entity) RETURN properties(e)")
            ]
            facts = self.facts()
            docs = [
                r[0]
                for r in self.query(
                    "documents", "MATCH (d:Document) RETURN properties(d)"
                )
            ]
            slots = {
                r[0]: r[1]
                for r in self.query("slots", "MATCH (s:Slot) RETURN s.id, s.current")
            }
            edges = [
                {"source": r[0], "target": r[1], "fact_id": r[2]}
                for r in self.query(
                    "dependencies",
                    "MATCH (a:Entity)-[r:REQUIRES]->(b:Entity) RETURN a.id,b.id,r.fact_id",
                )
            ]
            paths = {}
            for e in entities:
                if e["kind"] == "commitment":
                    rows = self.query("paths", params={"id": e["id"]})
                    paths[e["id"]] = [{"nodes": r[0], "facts": r[1]} for r in rows]
            return {
                "entities": entities,
                "facts": facts,
                "documents": docs,
                "slots": slots,
                "edges": edges,
                "paths": paths,
            }

    def delete_test_graph(self):
        if not self.settings.graph.startswith("pg_test_"):
            raise ValueError("Only explicitly named test graphs can be deleted.")
        self.graph.delete()
