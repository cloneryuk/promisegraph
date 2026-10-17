"""Evaluate accepted graph evidence without asking a model to calculate risk."""

from collections import defaultdict

LABELS = {
    "at_risk": "At risk",
    "unknown": "Cannot assess",
    "no_known_conflict": "No deadline conflict in known forecasts",
}
INFORMATIONAL_FLAGS = {"forecast_order_conflict", "downstream_work_unassessed"}
DELIVERY_LIMITATION = (
    "Known forecasts only. Downstream work and delivery feasibility are unassessed."
)


def _path_has_evidence(path, commitment_id, facts, documents):
    node_ids = path["nodes"]
    fact_ids = path["facts"]
    if not node_ids or node_ids[0] != commitment_id:
        return False
    if len(fact_ids) != len(node_ids) - 1:
        return False

    # Every traversed edge must match an accepted assertion in a completed source.
    for position, fact_id in enumerate(fact_ids):
        fact = facts.get(fact_id)
        if (
            not fact
            or fact["status"] != "accepted"
            or fact["kind"] != "requires"
            or fact["subject_id"] != node_ids[position]
            or fact["object_id"] != node_ids[position + 1]
            or fact.get("validation_flags")
            or not fact.get("quote")
            or fact.get("start", -1) < 0
            or documents.get(fact.get("doc_id"), {}).get("state") != "ready"
        ):
            return False
    return True


def _deadline_conflicts(deadline, forecasts, paths, entities):
    if deadline is None:
        return []

    conflicts = []
    for work_id, forecast in forecasts.items():
        if forecast is None or forecast["date"] <= deadline["date"]:
            continue

        proof_paths = [path for path in paths if path["nodes"][-1] == work_id]
        shortest_proof = min(
            proof_paths, key=lambda path: len(path["facts"]), default=None
        )
        conflicts.append(
            {
                "work_id": work_id,
                "work_name": entities.get(work_id, {}).get("name", work_id),
                "forecast": forecast["date"],
                "deadline": deadline["date"],
                "forecast_fact_id": forecast["id"],
                "deadline_fact_id": deadline["id"],
                "path": shortest_proof,
            }
        )
    return conflicts


def _forecast_order_conflicts(edges, required_work, forecasts):
    conflicts = []
    for edge in edges:
        dependent = edge["source"]
        prerequisite = edge["target"]
        dependent_forecast = forecasts.get(dependent)
        prerequisite_forecast = forecasts.get(prerequisite)
        if (
            dependent in required_work
            and prerequisite in required_work
            and dependent_forecast
            and prerequisite_forecast
            and dependent_forecast["date"] < prerequisite_forecast["date"]
        ):
            conflicts.append(
                {
                    "dependent": dependent,
                    "prerequisite": prerequisite,
                    "dependent_date": dependent_forecast["date"],
                    "prerequisite_date": prerequisite_forecast["date"],
                    "fact_ids": [
                        dependent_forecast["id"],
                        prerequisite_forecast["id"],
                        edge["fact_id"],
                    ],
                }
            )
    return conflicts


def assess(snapshot, selected=None, max_depth=8, path_limit=200):
    entities = {entity["id"]: entity for entity in snapshot["entities"]}
    facts = {fact["id"]: fact for fact in snapshot["facts"]}
    documents = {document["id"]: document for document in snapshot["documents"]}

    accepted_dates = defaultdict(list)
    for fact in facts.values():
        if fact["status"] == "accepted" and fact["kind"] in ("deadline", "forecast"):
            accepted_dates[(fact["subject_id"], fact["kind"])].append(fact)

    outgoing_edges = defaultdict(list)
    for edge in snapshot["edges"]:
        outgoing_edges[edge["source"]].append(edge)

    results = []
    for entity in entities.values():
        if entity["kind"] != "commitment":
            continue
        if selected and entity["id"] not in selected:
            continue

        commitment_id = entity["id"]
        flags = set()
        valid_paths = []
        required_work = set()
        evidence_ids = set()

        def current_date(entity_id, kind):
            candidates = accepted_dates[(entity_id, kind)]
            if len(candidates) != 1:
                if len(candidates) > 1:
                    flags.add("conflicting_values")
                else:
                    flags.add(
                        "missing_deadline" if kind == "deadline" else "missing_forecast"
                    )
                return None

            fact = candidates[0]
            slot_id = entity_id + "|" + kind
            if (
                not fact.get("date")
                or fact.get("validation_flags")
                or snapshot["slots"].get(slot_id) != fact["id"]
            ):
                flags.add("conflicting_values")
                return None
            if (
                fact["id"] not in facts
                or not fact.get("quote")
                or fact.get("start", -1) < 0
                or documents.get(fact["doc_id"], {}).get("state") != "ready"
            ):
                flags.add("broken_provenance")
                return None

            evidence_ids.add(fact["id"])
            return fact

        deadline = current_date(commitment_id, "deadline")
        returned_paths = snapshot["paths"].get(commitment_id, [])
        if len(returned_paths) > path_limit:
            flags.add("result_limit")

        for path in returned_paths[:path_limit]:
            if not _path_has_evidence(path, commitment_id, facts, documents):
                flags.add("broken_provenance")
                continue

            node_ids = path["nodes"]
            fact_ids = path["facts"]
            valid_paths.append(path)
            required_work.update(node_ids[1:])
            evidence_ids.update(fact_ids)
            if len(set(node_ids)) < len(node_ids):
                flags.add("cycle_detected")
            if len(fact_ids) >= max_depth and outgoing_edges[node_ids[-1]]:
                flags.add("depth_boundary")

        if not required_work:
            flags.add("unlinked_commitment")
        forecasts = {
            work_id: current_date(work_id, "forecast") for work_id in required_work
        }
        conflicts = _deadline_conflicts(deadline, forecasts, valid_paths, entities)
        order_conflicts = _forecast_order_conflicts(
            snapshot["edges"], required_work, forecasts
        )
        if order_conflicts:
            flags.add("forecast_order_conflict")

        for fact in facts.values():
            if fact["status"] != "pending":
                continue
            if not fact["subject_id"]:
                flags.add("unresolved_entity")
            elif fact["subject_id"] in required_work | {commitment_id}:
                flags.add("pending_relevant_fact")
        if any(document["state"] != "ready" for document in documents.values()):
            flags.add("unprocessed_document")

        # A proven late branch stays at risk even when another branch lacks evidence.
        if conflicts:
            status = "at_risk"
        elif flags - INFORMATIONAL_FLAGS:
            status = "unknown"
        else:
            status = "no_known_conflict"
            flags.add("downstream_work_unassessed")

        conflicts.sort(
            key=lambda conflict: (conflict["forecast"], conflict["work_id"]),
            reverse=True,
        )
        results.append(
            {
                "id": commitment_id,
                "name": entity["name"],
                "customer": entity.get("customer", entity["name"]),
                "status": status,
                "label": LABELS[status],
                "deadline": deadline["date"] if deadline else None,
                "flags": sorted(flags),
                "conflicts": conflicts,
                "forecast_order_conflicts": order_conflicts,
                "paths": valid_paths,
                "known_work_count": len(required_work),
                "evidence_ids": sorted(evidence_ids),
                "limitation": DELIVERY_LIMITATION,
            }
        )
    return results


def exposure(snapshot, assessments):
    commitments_by_work = defaultdict(set)
    for result in assessments:
        for path in result["paths"]:
            for work_id in path["nodes"][1:]:
                commitments_by_work[work_id].add(result["id"])

    names = {entity["id"]: entity["name"] for entity in snapshot["entities"]}
    ranked_work = sorted(
        commitments_by_work.items(), key=lambda item: (-len(item[1]), item[0])
    )
    return [
        {
            "id": work_id,
            "name": names.get(work_id, work_id),
            "commitments": sorted(commitment_ids),
            "count": len(commitment_ids),
            "label": "Known linked commitments; not an at-risk count",
        }
        for work_id, commitment_ids in ranked_work
    ]
