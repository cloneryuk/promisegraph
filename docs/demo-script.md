# Record a real demonstration

Target the story at about two minutes, allowing more time for live model latency. This is a storytelling target, not an event video duration rule. Spend about 30 seconds showing the actual agent operations and opening their evidence.

An existing 113-second captioned walkthrough is included as `demo-walkthrough.mp4`. It holds actual screenshots from an earlier successful Cloud/Gemini run and cuts waits/navigation; it is not a continuous recording and predates the natural-source, contributor, and per-step trace improvements. The baseline was prepared beforehand, and Codex performed the synthetic-data QA review. Record a new continuous take using this script to show the current version and explain the code yourself.

## Before recording

- Configure FalkorDB Cloud and Gemini. Check the database connection.
- Use a fresh `FALKORDB_GRAPH=promisegraph_live_demo_01` so a previous rehearsal does not get mislabeled as extraction.
- Click **Extract demo notes with Gemini** and review the proposals against their original source text. Fix failures honestly by adding a correction source; do not substitute hand-authored responses for a failed live request.
- Verify Acme and Beacon are at risk, the conflict is three hops away, and Cedar cannot be assessed.
- Run unit and actual graph integration checks. Save a nominated fresh extraction evaluation, including failures. Use the real counts in narration.
- Avoid recording `.env` or Cloud credentials. Record a full successful take before the final submission day. Any edits or latency cuts should be disclosed.

## Opening sequence

| Time | Action and narration |
| --- | --- |
| 0–15 s | Show the radar's three-hop proof. “These synthetic promises depend on shared engineering work. Signing-key rotation puts both deadlines at risk. Cedar has no known dependency path, so we cannot assess it.” |
| 15–30 s | Open Sources & history and read a customer note and the platform chat. Show the source contributors on Beacon's card. “These people authored the relevant sources; we have not established work ownership.” |
| 30–50 s | Add knowledge → Fill the revision note → Extract with Gemini. Show the actual prose and wait for the live result. “This meeting note changes Acme's deadline. The proposal is still pending.” |
| 50–65 s | Inspect the exact quote and both dates in Review inbox. Confirm and accept. Show Acme's changed status and Beacon's remaining conflict. “The earlier decision is preserved, and the forecast-order warning remains.” |
| 65–95 s | Run the live agent: “Why is Beacon still at risk after Acme changed its deadline?” Expand the assessment step's Cypher and parameters, then open a source chip on the evidence step. “Gemini selected these tools. The first reads FalkorDB; the second opens evidence already retrieved. Code computes risk.” |
| 95–110 s | Open decision history and the earlier deadline. Show that Cedar remains unknown. “No detected conflict does not prove delivery feasibility.” |
| 110–125 s | Show the README's actual checks and limitations, then explain the schema and your contribution. State the synthetic-data and AI-assistance disclosures. |

The examples deliberately use full dates and approved names. State this limitation. The base workspace was extracted and reviewed before the recording; disclose that preparation. If you demonstrate **rehearsal mode**, say “hand-authored fixtures and scripted calls” explicitly and also record a successful live model run for the agents submission.

For an interactive walkthrough after the Acme revision, leave the genuine Cedar sample proposal pending. Or use **Review inbox → Try reviewing a sample → Extract with Gemini** when the inbox is empty and Cedar still has its original deadline. Accepting it changes Cedar's date while leaving its missing-work warning and the Acme/Beacon outcomes intact. If already processed, its source and review history remain available; do not claim repeated ingestion was a new extraction.

## Explain these pieces yourself

1. Why `REQUIRES*1..8` is a traversal over real graph relationships.
2. How every edge carries an accepted fact ID linked to a document span.
3. Why the deadline comparison proves a conflict but absence of conflict cannot prove delivery.
4. How the Slot guard plus `SUPERSEDES` keeps the previous decision and prevents stale replacement.
5. Why a missing forecast or a database failure never becomes a “safe” result.
6. What the agent selected, what code fixed in advance, and what Codex helped implement.
