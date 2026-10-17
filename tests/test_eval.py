import json
from app.config import ROOT
from eval.run import score


def labels():
    return [
        json.loads(line)
        for line in (ROOT / "eval/extraction.jsonl").read_text().splitlines()
    ]


def test_fixture_counts_and_missing_note_failure():
    fixtures = json.loads((ROOT / "eval/fixtures.json").read_text())
    records = [
        {"case_id": case_id, "extraction": value} for case_id, value in fixtures.items()
    ]
    report = score(records, labels())
    assert report["counts"] == dict(
        correct=5,
        incorrect=0,
        missed=0,
        deferred=3,
        missing_expected_deferral=0,
        failed_notes=0,
    )
    damaged = score(records[1:], labels())
    assert damaged["counts"]["failed_notes"] == 1 and damaged["counts"]["missed"] == 1
