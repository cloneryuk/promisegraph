# Submission readiness review — October 17, 2026

This review covers the page code, interface state handling, existing captured screens, current service health and a read-only check of the live graph. Fresh browser inspection was blocked by the browser tool; the new layout has not been visually rechecked. The event pages describe track focus but do not publish numerical scoring weights. This is a practical readiness assessment, not a prediction of placement.

## Fixed in this review

| Finding | Change |
| --- | --- |
| `ready` on a source card could be mistaken for fact approval | Processing status is inside collapsed **Extraction details**. It explicitly separates extraction completion from fact review. Failed/in-progress extraction stays prominent. |
| A previous agent answer could remain after graph changes | Refresh, new graph data, new questions and scope/mode changes clear the previous answer and its citation state. |
| An agent-selected customer scope could replace the complete dashboard | Answers now have their own scope, evidence and query trace; dashboard totals and cards remain unchanged. The scope selector says **Automatic scope**. |
| Changing inputs during an API request could confuse which question was answered | Inputs and selects are disabled during requests, along with buttons. |
| Rehearsal controls invited an incompatible write into a live workspace | The UI disables incompatible sample-ingestion buttons and explains how to use a fresh graph. Backend validation remains in place. |
| Raw Markdown appeared in generated answers | Safe bold/list formatting is rendered after escaping HTML; only opened citations become source buttons. |
| An outage could leave old cards looking current | A visible stale-results notice appears, the connection indicator changes, and the previous answer is cleared. |
| Small metadata and risk/path labels were hard to read | Increased selected font sizes and darkened metadata. Mobile navigation now has explicit accessible names. |
| Model, prompt and query information distracted from the documents | Model/prompt/processing fields remain in collapsed details. Executed Cypher remains available in **Query details** and alongside each agent answer. |

Sixteen deterministic Node tests cover the consequential interface changes, including narrow scope, stale state, evidence access, escaping, mode restrictions, outage handling, review samples, contributors, and trace steps. They do not substitute for visual browser testing. JavaScript syntax checks passed. The latest backend run passed 57 tests, including six actual FalkorDB Cloud integration tests.

## Submission improvements added

- Replaced rigid demo sentences with synthetic call notes, a delivery handoff, a platform chat, and a customer revision. Full dates and approved names remain explicit.
- Added an empty-inbox sample action and prepared a genuinely Gemini-extracted Cedar replacement for immediate review. Processed samples link back to their retained source rather than silently duplicating facts.
- Added source contributors to commitment cards, selecting authors only from the displayed path's accepted evidence. Source chips open exact quotes; ownership remains unverified.
- Added numbered actual tool steps with their executed Cypher, parameters and evidence links. Evidence-opening steps clearly report that they reuse the assessment's retrieved sources.
- Added exact core queries and the Python/graph computation boundary to the README. Named demo/test graphs are distinguished from authenticated tenant isolation. The AI-assistance disclosure remains intact.

Live natural-note QA uncovered three rejected extraction attempts before a successful fresh run. All reports are preserved and described in `verification.md`; no model errors were replaced with fixtures.

## Current connected workspace

The current graph contains five live-extracted documents, one valid pending Cedar deadline replacement and one accepted Acme supersession. Acme's current deadline is November 10 with `no_known_conflict`; Beacon remains `at_risk` with November 4; Cedar remains `unknown`. See `readiness-state.json` and the restarted app's `current-api-check.json`. This revision created and activated a separate verified graph; the earlier graph remains intact.

## Finish before submitting

1. **Publish the repository and video, then submit their actual URLs.** The local ZIP does not complete event submission. These uploads are still pending.
2. **Personally rehearse and explain the project.** Know the risk comparison, missing-evidence behavior, `REQUIRES*1..8`, source-span links and guarded `SUPERSEDES` update. Retain the AI-assistance disclosure and accurately describe your contribution.
3. **Make the demo understandable without this conversation.** The included 113-second video is a disclosed edited sequence of actual screenshots. A participant-narrated recording showing the clicks and explaining the result would better demonstrate understanding. Use a fresh demo graph to replay the initial risk -> reviewed revision sequence; the current graph already contains the accepted revision. Do not present repeated ingestion as a new extraction.
4. **Inspect the final UI after refresh.** Check source details collapsed/expanded, review controls, an actual agent answer, citations, and a narrow customer question. Browser automation was blocked during this review.

## Scope to explain honestly

- This is a focused Company Brain use case for promises, engineering dependencies and decision history. It does not implement general company search, extracted ownership, team coordination or external task execution.
- Authorship means who supplied a source, not who owns the work. Full dates and approved aliases are required; relative dates and unknown identities remain pending.
- Graph queries, evidence gaps, synthetic-data labels and the live/rehearsal distinction help explain the implementation and should stay available.
- The evaluation is a small self-authored development set. Report the actual counts and provider failure; do not call them generalized accuracy.
- Local setup is included. The event prefers a live deployment, but permits complete local setup instructions with a working demo video. This single-user app has not been prepared for public hosting.

Sources checked: [Event overview and track focus](https://www.wemakedevs.org/hackathons/falkordb), [Rules and required submission artifacts](https://www.wemakedevs.org/hackathons/falkordb/rules), [Official resources](https://www.wemakedevs.org/hackathons/falkordb/resources).
