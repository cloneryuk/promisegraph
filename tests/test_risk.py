from app.risk import assess, exposure
from .fixtures import snapshot, build_paths, find, add_fact, add_work


def result(s, cid="acme_sso"):
    return next(r for r in assess(s) if r["id"] == cid)


def test_three_hop_conflict_and_source_chain():
    s = snapshot()
    r = result(s)
    assert r["status"] == "at_risk"
    assert r["conflicts"][0]["path"]["nodes"] == [
        "acme_sso",
        "sso",
        "identity",
        "rotation",
    ]
    assert len(r["conflicts"][0]["path"]["facts"]) == 3
    assert {
        r["conflicts"][0]["forecast_fact_id"],
        r["conflicts"][0]["deadline_fact_id"],
    } <= set(r["evidence_ids"])


def test_direct_conflict():
    s = snapshot()
    add_fact(s, "acme_sso", "requires", target="rotation")
    build_paths(s)
    assert len(result(s)["conflicts"][0]["path"]["facts"]) == 1


def test_four_hop_evidence():
    s = snapshot()
    add_work(s, "deep", "2026-11-09")
    add_fact(s, "rotation", "requires", target="deep")
    build_paths(s)
    assert len(result(s)["conflicts"][0]["path"]["facts"]) == 4


def test_parallel_branches_and_computed_order_warning():
    r = result(snapshot())
    assert r["known_work_count"] == 4
    assert r["forecast_order_conflicts"][0]["dependent"] == "identity"
    assert r["status"] == "at_risk" and "forecast_order_conflict" in r["flags"]


def test_two_routes_deduplicate_exposure():
    s = snapshot()
    add_fact(s, "security", "requires", target="rotation")
    build_paths(s)
    e = next(e for e in exposure(s, assess(s)) if e["id"] == "rotation")
    assert e["count"] == 2 and len(result(s)["conflicts"]) == 1


def test_later_deadline_keeps_order_warning_and_other_customer_risk():
    s = snapshot()
    find(s, "acme_sso", "deadline")["date"] = "2026-11-10"
    r = result(s)
    assert r["status"] == "no_known_conflict"
    assert {"forecast_order_conflict", "downstream_work_unassessed"} <= set(r["flags"])
    assert result(s, "beacon_sso")["status"] == "at_risk"


def test_unlinked_is_unknown():
    r = result(snapshot(), "cedar_export")
    assert r["status"] == "unknown" and "unlinked_commitment" in r["flags"]


def test_missing_forecast_is_unknown_without_proof():
    s = snapshot()
    find(s, "rotation", "forecast")["status"] = "rejected"
    r = result(s)
    assert r["status"] == "unknown" and "missing_forecast" in r["flags"]


def test_positive_proof_survives_other_missing_branch():
    s = snapshot()
    find(s, "security", "forecast")["status"] = "rejected"
    r = result(s)
    assert r["status"] == "at_risk" and "missing_forecast" in r["flags"]


def test_conflicting_dates_do_not_pick_convenient_value():
    s = snapshot()
    add_fact(s, "acme_sso", "deadline", date="2026-11-11")
    r = result(s)
    assert r["status"] == "unknown" and "conflicting_values" in r["flags"]


def test_broken_provenance_blocks_risk_proof():
    s = snapshot()
    find(s, "rotation", "forecast")["start"] = -1
    r = result(s)
    assert r["status"] == "unknown" and "broken_provenance" in r["flags"]


def test_cycle_flag_and_termination_without_conflict():
    s = snapshot()
    find(s, "acme_sso", "deadline")["date"] = "2026-11-12"
    add_fact(s, "rotation", "requires", target="sso")
    build_paths(s)
    r = result(s)
    assert r["status"] == "unknown" and "cycle_detected" in r["flags"]


def test_depth_limit_is_incomplete_not_safe():
    s = snapshot()
    find(s, "acme_sso", "deadline")["date"] = "2026-11-12"
    parent = "rotation"
    for i in range(7):
        child = "deep" + str(i)
        add_work(s, child)
        add_fact(s, parent, "requires", target=child)
        parent = child
    build_paths(s)
    r = result(s)
    assert r["status"] == "unknown" and "depth_boundary" in r["flags"]


def test_row_limit_marks_incomplete():
    s = snapshot()
    find(s, "acme_sso", "deadline")["date"] = "2026-11-12"
    s["paths"]["acme_sso"] *= 51
    assert "result_limit" in result(s)["flags"] and result(s)["status"] == "unknown"


def test_pending_never_removes_accepted_risk():
    s = snapshot()
    f = add_fact(s, "acme_sso", "deadline", date="2026-11-12")
    f["status"] = "pending"
    old = next(
        f
        for f in s["facts"]
        if f["subject_id"] == "acme_sso"
        and f["kind"] == "deadline"
        and f["status"] == "accepted"
    )
    s["slots"][old["slot_id"]] = old["id"]
    assert (
        result(s)["status"] == "at_risk"
        and "pending_relevant_fact" in result(s)["flags"]
    )
