"""Small extraction evaluator. Run from the project root using python -m eval.run."""

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from app.config import ROOT, Settings
from app.schemas import Candidate, DocumentInput, Extraction
from app.ingest import prepare_document, validate_candidate
from app.llm import Gemini, PROMPT_HASH, ModelUnavailable

DATA = ROOT / "eval/extraction.jsonl"


def signature(f):
    return (f["kind"], f["subject_id"], f["object_id"], f["date"], f["old_date"])


def score(records, labels):
    counts = {
        "correct": 0,
        "incorrect": 0,
        "missed": 0,
        "deferred": 0,
        "missing_expected_deferral": 0,
        "failed_notes": 0,
    }
    failures = []
    by_id = {r["case_id"]: r for r in records}
    for label in labels:
        record = by_id.get(label["id"], {})
        proposals = record.get("extraction", {}).get("facts", [])
        if record.get("error") or not record:
            counts["failed_notes"] += 1
            failures.append(
                {
                    "case": label["id"],
                    "error": record.get("error", "Missing saved record"),
                }
            )
        doc = prepare_document(
            DocumentInput.model_validate(label["document"]),
            "evaluation",
            record.get("model", "unknown"),
            record.get("prompt_hash", "unknown"),
        )
        actual = []
        for proposal in proposals:
            try:
                actual.append(
                    validate_candidate(Candidate.model_validate(proposal), doc)
                )
            except ValueError:
                counts["incorrect"] += 1
                failures.append(
                    {"case": label["id"], "error": "Invalid candidate schema"}
                )
        unmatched = list(actual)
        for expected in label["expected"]:
            match = next(
                (f for f in unmatched if signature(f) == tuple(expected["tuple"])), None
            )
            if match is None:
                key = "missing_expected_deferral" if expected["defer"] else "missed"
                counts[key] += 1
                failures.append(
                    {"case": label["id"], "error": key, "expected": expected}
                )
                continue
            unmatched.remove(match)
            required = set(expected.get("flags", []))
            valid = (
                (
                    bool(match["validation_flags"])
                    and required <= set(match["validation_flags"])
                )
                if expected["defer"]
                else not match["validation_flags"]
            )
            if valid:
                counts["deferred" if expected["defer"] else "correct"] += 1
            else:
                counts["incorrect"] += 1
                failures.append(
                    {
                        "case": label["id"],
                        "error": "Wrong validation outcome",
                        "actual_flags": match["validation_flags"],
                    }
                )
        for extra in unmatched:
            counts["incorrect"] += 1
            failures.append(
                {
                    "case": label["id"],
                    "error": "Unexpected extra fact",
                    "actual": signature(extra),
                }
            )
    return {
        "counts": counts,
        "failures": failures,
        "notes": len(labels),
        "interpretation": "Small self-authored development set. Counts only; not a general extraction accuracy estimate. Human review is not scored as model success.",
    }


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument(
        "--fresh",
        action="store_true",
        help="Call Gemini, save all raw responses and failures",
    )
    modes.add_argument(
        "--replay", type=Path, help="Revalidate a saved run without model calls"
    )
    modes.add_argument(
        "--fixtures",
        action="store_true",
        help="Pipeline self-check using hand-authored responses; NOT model extraction evaluation",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="New JSON report path; existing reports will not be overwritten",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=12,
        help="Seconds between fresh requests (0–60); defaults to 12 to reduce bursts",
    )
    args = parser.parse_args()
    if not 0 <= args.interval <= 60:
        parser.error("Interval must be between 0 and 60 seconds.")
    if args.out.exists():
        parser.error("Output exists. Choose a new path to preserve the earlier run.")
    labels = [
        json.loads(line)
        for line in DATA.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    dataset_hash = hashlib.sha256(DATA.read_bytes()).hexdigest()
    settings = Settings.load()
    records = []
    if args.replay:
        records = [
            json.loads(line)
            for line in args.replay.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        mode = "saved-response replay"
    else:
        raw_path = args.out.with_suffix(".jsonl")
        if raw_path.exists():
            parser.error("Raw-response path exists. Choose a new output name.")
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        mode = (
            "live Gemini extraction"
            if args.fresh
            else "hand-authored fixture pipeline check; not a model run"
        )
        fixtures = json.loads((ROOT / "eval/fixtures.json").read_text(encoding="utf-8"))
        for label in labels:
            if args.fresh and records:
                time.sleep(args.interval)
            record = {
                "case_id": label["id"],
                "mode": mode,
                "model": settings.model if args.fresh else "hand-authored",
                "prompt_hash": PROMPT_HASH,
                "dataset_hash": dataset_hash,
                "schema_version": 1,
                "request_settings": {"temperature": 0, "maxOutputTokens": 6000},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "input": label["document"],
            }
            try:
                if args.fresh:
                    doc = prepare_document(
                        DocumentInput.model_validate(label["document"]),
                        "evaluation",
                        settings.model,
                        PROMPT_HASH,
                    )
                    extraction, raw = Gemini(settings).extract(doc)
                else:
                    raw = {"fixture": fixtures[label["id"]]}
                    extraction = Extraction.model_validate(fixtures[label["id"]])
                record.update(extraction=extraction.model_dump(), raw_response=raw)
            except (ModelUnavailable, ValueError) as exc:
                record.update(
                    error=str(exc), raw_response=getattr(exc, "raw_response", None)
                )
            records.append(record)
            with raw_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(
                label["id"] + ": " + ("failed" if record.get("error") else "recorded"),
                flush=True,
            )
    report = {
        "mode": mode,
        "source_modes": sorted({r.get("mode", "unknown") for r in records}),
        "dataset_hash": dataset_hash,
        "prompt_hash": PROMPT_HASH,
        **score(records, labels),
    }
    report["metadata_mismatches"] = [
        r["case_id"]
        for r in records
        if r.get("dataset_hash") != dataset_hash or r.get("prompt_hash") != PROMPT_HASH
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
