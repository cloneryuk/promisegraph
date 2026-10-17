"""Synthetic documents and explicitly hand-authored rehearsal proposals."""

from .schemas import DocumentInput


def candidate(kind, subject, quote, date="", target="", old=""):
    return {
        "kind": kind,
        "subject": subject,
        "quote": quote,
        "date_expression": date,
        "object": target,
        "replaces_date_expression": old,
        "polarity": "affirmed",
    }


def document(title, lines, source, author, facts, day=1):
    return {
        "document": {
            "title": title,
            "text": "\n".join(lines),
            "source_type": source,
            "author_id": author,
            "timestamp": f"2026-11-{day:02d}T10:00:00+05:30",
            "timezone": "Asia/Kolkata",
        },
        "fixture": {"facts": facts},
    }


def examples():
    deadlines = [
        ("Acme SSO launch", "November 4, 2026"),
        ("Beacon SSO launch", "November 4, 2026"),
        ("Cedar data export", "November 8, 2026"),
    ]
    lines = [
        "Acme's CTO asked us to keep the Acme SSO launch on November 4, 2026; that's the date we committed to on the call.",
        "Beacon has already booked its onboarding session, so the promised date for the Beacon SSO launch remains November 4, 2026.",
        "For the separate Cedar data export, we agreed to deliver by November 8, 2026.",
    ]
    meeting = document(
        "Customer launch commitments",
        [
            "Customer check-in notes / Maya\n",
            *lines,
            "\nFollow-up for me: chase the export delivery plan before the next check-in. The customers only saw the launch dates, not the engineering board.",
        ],
        "meeting",
        "maya",
        [
            candidate("deadline", name, line, date)
            for (name, date), line in zip(deadlines, lines)
        ],
    )
    dependencies = [
        ("Acme SSO launch", "SSO rollout"),
        ("Beacon SSO launch", "SSO rollout"),
        ("SSO rollout", "identity migration"),
        ("identity migration", "signing-key rotation"),
        ("SSO rollout", "security review"),
    ]
    lines = [
        "Customer Success needs the SSO rollout completed before we can deliver the Acme SSO launch.",
        "The Beacon SSO launch is waiting on that same SSO rollout, so treat both customer launches as blocked on it.",
        "For the SSO rollout to ship, the identity migration has to be finished first.",
        "Platform also confirmed that the identity migration must wait for the signing-key rotation to finish.",
        "The security review is another required gate for the SSO rollout, alongside the migration work.",
    ]
    facts = [
        candidate("requires", a, line, target=b)
        for (a, b), line in zip(dependencies, lines)
    ]
    for work, line in [
        (
            "SSO rollout",
            "The board still lists November 3, 2026 as the expected finish for the SSO rollout.",
        ),
        (
            "identity migration",
            "For the identity migration, the engineering estimate is completion on November 3, 2026.",
        ),
        (
            "security review",
            "The security review is also expected to wrap up on November 3, 2026.",
        ),
    ]:
        lines.append(line)
        facts.append(candidate("forecast", work, line, "November 3, 2026"))
    tickets = document(
        "SSO delivery plan · required work",
        [
            "Delivery handoff / Leo\n",
            *lines,
            "\nThese estimates came from planning. Please cross-check the platform thread before repeating them in a customer update.",
        ],
        "ticket",
        "leo",
        facts,
    )
    line = "Quick update from platform: our revised finish estimate for the signing-key rotation is November 6, 2026."
    chat = document(
        "Platform delivery update",
        [
            line,
            "The staging check took longer than expected. Posting here because the delivery ticket still has the earlier planning estimates. Please bring this up at the handoff.",
        ],
        "chat",
        "priya",
        [candidate("forecast", "signing-key rotation", line, "November 6, 2026")],
        2,
    )
    line = "Their CTO approved a revised deadline for the Acme SSO launch, replacing November 4, 2026 with November 10, 2026."
    revision = document(
        "Acme approves a revised deadline",
        [
            "Just finished the Acme call.",
            line,
            "Beacon is still holding firm on its existing launch date. I've added the Acme agreement here so the next customer update uses the right date.",
        ],
        "meeting",
        "maya",
        [
            candidate(
                "deadline",
                "Acme SSO launch",
                line,
                "November 10, 2026",
                old="November 4, 2026",
            )
        ],
        3,
    )
    line = "Cedar confirmed a revised deadline for the Cedar data export: November 12, 2026 replaces November 8, 2026."
    review_sample = document(
        "Cedar confirms a revised export date",
        [
            "Customer Success follow-up / Maya",
            line,
            "Their analyst is away during the original delivery window. I still need the engineering delivery plan before we can assess feasibility.",
        ],
        "chat",
        "maya",
        [
            candidate(
                "deadline",
                "Cedar data export",
                line,
                "November 12, 2026",
                old="November 8, 2026",
            )
        ],
        3,
    )
    return {
        "baseline": [meeting, tickets, chat],
        "revision": revision,
        "review_sample": review_sample,
    }


def load_demo(service, mode="rehearsal", revision=False):
    docs = [examples()["revision"]] if revision else examples()["baseline"]
    results = []
    for item in docs:
        result = service.ingest(
            DocumentInput.model_validate(item["document"]), mode, item["fixture"]
        )
        # Only this pre-reviewed, hand-authored baseline is automatically accepted.
        # Live model proposals and the revision always require the review table.
        if mode == "rehearsal" and not revision:
            for f in result["facts"]:
                if f["status"] == "pending" and not f["validation_flags"]:
                    service.repo.review(
                        f["id"],
                        "accept",
                        reason="Pre-reviewed synthetic rehearsal fixture",
                    )
        results.append(
            {
                "id": result["document"]["id"],
                "fact_count": len(result["facts"]),
                "duplicate": result["duplicate"],
            }
        )
    return {
        "documents": results,
        "mode": mode,
        "review_required": mode == "live" or revision,
    }
