import hashlib
import json
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .config import ROOT
from .schemas import Candidate, DocumentInput


def catalog():
    return json.loads((ROOT / "data/entities.json").read_text(encoding="utf-8"))


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:24]


def normalize(value):
    return " ".join(value.casefold().split())


def resolve(mention, entities):
    hits = [
        e["id"]
        for e in entities
        if normalize(mention)
        in {
            normalize(e["id"]),
            normalize(e["name"]),
            *(normalize(a) for a in e.get("aliases", [])),
        }
    ]
    return hits[0] if len(hits) == 1 else ""


def parse_date(expression):
    text = expression.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            return ""
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def prepare_document(doc: DocumentInput, mode, model, prompt_hash):
    try:
        ZoneInfo(doc.timezone)
    except ZoneInfoNotFoundError:
        raise ValueError("Unknown document timezone.")
    if doc.author_id not in {p["id"] for p in catalog()["people"]}:
        raise ValueError("Select a supplied author from the fixed roster.")
    identity = [
        doc.text,
        doc.timestamp.isoformat(),
        doc.timezone,
        doc.author_id,
        doc.source_type,
    ]
    return {
        "id": "doc_" + digest(identity),
        "title": doc.title,
        "text": doc.text,
        "timestamp": doc.timestamp.isoformat(),
        "timezone": doc.timezone,
        "author_id": doc.author_id,
        "source_type": doc.source_type,
        "content_hash": digest(identity),
        "state": "extracting",
        "mode": mode,
        "model": model,
        "prompt_hash": prompt_hash,
        "created_at": datetime.now().astimezone().isoformat(),
        "error": "",
    }


def validate_candidate(candidate: Candidate, doc, entities=None):
    entities = entities or catalog()["entities"]
    c = candidate.model_dump()
    flags = []
    quote = c["quote"]
    positions = [m.start() for m in re.finditer(re.escape(quote), doc["text"])]
    if len(positions) != 1:
        flags.append("quote_missing" if not positions else "quote_ambiguous")
    start = positions[0] if len(positions) == 1 else -1
    subject_id, object_id = resolve(c["subject"], entities), (
        resolve(c["object"], entities) if c["object"] else ""
    )
    entity_map = {e["id"]: e for e in entities}
    if not subject_id:
        flags.append("unresolved_entity")
    if normalize(c["subject"]) not in normalize(quote):
        flags.append("subject_not_in_quote")
    if c["polarity"] != "affirmed":
        flags.append("not_affirmed")
    # This conservative check supplements, never replaces, human semantic review.
    if re.search(
        r"\b(not|never|no longer|unlikely|might|maybe|tentative)\b", quote, re.I
    ):
        flags.append("semantic_review_required")
    value = ""
    if c["kind"] == "requires":
        if not object_id:
            flags.append("unresolved_dependency")
        if normalize(c["object"]) not in normalize(quote):
            flags.append("object_not_in_quote")
        if object_id and entity_map[object_id]["kind"] != "work":
            flags.append("invalid_dependency_target")
        if subject_id == object_id and subject_id:
            flags.append("self_dependency")
        if re.search(r"\b(optional|either|alternatively)\b", quote, re.I):
            flags.append("unsupported_dependency")
    else:
        value = parse_date(c["date_expression"])
        if not value:
            flags.append("unsupported_date")
        if not c["date_expression"] or c["date_expression"] not in quote:
            flags.append("date_not_in_quote")
        expected_kind = "commitment" if c["kind"] == "deadline" else "work"
        if subject_id and entity_map[subject_id]["kind"] != expected_kind:
            flags.append("invalid_subject_type")
    old_date = ""
    if c["replaces_date_expression"]:
        old_date = parse_date(c["replaces_date_expression"])
        if not old_date or c["replaces_date_expression"] not in quote:
            flags.append("replacement_date_invalid")
        if not re.search(
            r"\b(replace[sd]?|changing|changed|revised|instead|moved|rescheduled)\b",
            quote,
            re.I,
        ):
            flags.append("replacement_not_explicit")
    fid = "fact_" + digest([doc["id"], c])
    return {
        "id": fid,
        "kind": c["kind"],
        "subject_id": subject_id,
        "object_id": object_id,
        "raw_subject": c["subject"],
        "raw_object": c["object"],
        "date": value,
        "date_expression": c["date_expression"],
        "quote": quote,
        "old_date": old_date,
        "status": "pending",
        "validation_flags": sorted(set(flags)),
        "doc_id": doc["id"],
        "span_id": "span_" + digest([doc["id"], start, quote]),
        "start": start,
        "end": start + len(quote) if start >= 0 else -1,
        "mode": doc["mode"],
        "slot_id": subject_id + "|" + c["kind"],
        "reviewed_at": "",
        "review_reason": "",
    }
