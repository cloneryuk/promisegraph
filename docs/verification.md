# Verification status

This file is updated after local checks. Database and model checks require credentials; a skipped check is not a pass.

| Check | Status |
| --- | --- |
| Python syntax and browser JavaScript syntax | Passed on October 16, 2026 |
| Full test suite | **57 passed, 0 skipped**, including 6 actual Cloud integration tests; clean Python 3.12 venv on Windows, October 17, 2026. Saved JUnit report: test-results.xml. |
| Clean dependency install | Passed from requirements.txt; pip check reports no broken requirements. Exact resolved versions saved in requirements-lock.txt. |
| Fixture evaluation and saved-response replay | Both produced 5 correct, 3 deferred, 0 incorrect/missed across 7 notes; hand-authored pipeline check, not model accuracy |
| Live FalkorDB integration, guarded writes, read-only enforcement | All 6 integration tests passed against the configured Cloud instance, including the Cedar review sample and contributor/query-trace checks. Previously inspected module graph version 42200 (4.22.0); TIMEOUT_MAX=0, TIMEOUT_DEFAULT=0. Application reads explicitly request 1,000 ms. |
| Actual Gemini extraction / agent and fresh extraction scores | Latest complete-quote prompt evaluation: all 7 notes returned usable outputs; 5 correct, 3 deferred, 0 incorrect/missed/provider failures. Replay matches. All 14 natural-demo proposals passed on the final run, followed by a graph-backed agent answer without fallback. Earlier failures remain below. |
| Docker image execution | Unverified — Docker is not installed on the build machine |
| Actual browser rendering and interactions | Earlier build passed connected ingestion, review, supersession, live agent calls and citations. Current interface refinements have code-level tests, but fresh visual inspection remains blocked by browser-tool access policy. |
| Live Gemini tool protocol | Passed against explicitly labeled test-fixture tool results: model selected commitment scope, opened three evidence facts, and returned valid citations. This is not a FalkorDB-backed product demo. See agent-protocol-smoke.json. |
| App stop/restart with database persistence | Passed. Four live-extracted documents, accepted revision, old/new history and all three expected statuses persisted after restarting Uvicorn. See live-revision-result.json. |
| Public source repository and event submission | Not published / not submitted |

Initial environment finding: the machine-wide FastAPI and Starlette versions were incompatible. A new isolated virtual environment was installed from requirements.txt and its tests passed without dependency conflicts. Run the app in its own virtual environment.

## Preserved model runs

- `live-extraction-01.json` / `.jsonl`: nominated initial Gemini 3.8 Flash run. One correct forecast, six provider failures. All failures remain in the report.
- `live-extraction-02-lite.json` / `.jsonl`: attempted Gemini 3.5 Flash-Lite run while the newly launched process lacked network access. Seven transport failures. This does not measure extraction quality.
- `live-extraction-03-lite.json` / `.jsonl`: nominated paced Gemini 3.5 Flash-Lite run after network access was restored. **5 correct, 2 deferred, 0 incorrect/missed valid facts, 1 missing expected deferral because that note failed with HTTP 503.** Six of seven notes returned usable outputs. Saved-response replay reproduced the same counts. The app default was changed to this model after that result; the failed request remains recorded.
- `live-extraction-04-natural-prompt.json` / `.jsonl`: fresh seven-note run after clarifying complete verbatim quotes and commitment/work types. **5 correct, 3 deferred, 0 incorrect, 0 missed, 0 missing expected deferrals, 0 failed notes.** `replay-04-natural-prompt.json` reproduces those counts. Prompt hash `eee140bafb169019`, temperature 0, model ID and raw responses are retained. This remains the same self-authored development set, not a new held-out evaluation.

Changing models or retrying infrastructure failures does not erase the earlier runs. The data is a self-authored development set, not a held-out benchmark.

## Live demo setup

`live-demo-setup.json` records three raw synthetic documents extracted with Gemini into a separate `promisegraph_live_demo` graph. All 12 extracted baseline facts matched their expected tuples and passed exact-span validation. The synthetic QA runner invoked the normal review method after those checks; this was not human review and is not counted as model benchmark success. Acme and Beacon are at risk through three hops; Cedar remains unknown. The original rehearsal graph is retained separately.

The initially supplied TLS setting did not match the Cloud endpoint. An unauthenticated PING established its standard Redis protocol, and the user confirmed a `falkor://` / `redis://` connection prefix. Setting `FALKORDB_SSL=false` for that endpoint resolved the connection. This is endpoint-specific; use TLS for endpoints that specify `falkors://` or `rediss://`.

## Connected revision and agent checks

On October 17, the browser sent the synthetic revision note to Gemini. It returned one valid pending proposal with the new date and explicit earlier date. Codex checked the source and operated the normal review controls during QA; this must not be presented as a human review study. Acme became `no_known_conflict`, Beacon stayed `at_risk`, and Cedar stayed `unknown`. The informational forecast-order warning remained. A subsequent app restart preserved these results and the old/new history.

`live-graph-agent.json` contains an actual graph-backed Gemini run, its tool choices, answer, and raw responses. It used two tools and opened six facts. A separate browser run opened five facts and displayed working source buttons. The earlier fixture-only protocol smoke remains labeled separately.

A development browser run had used the disclosed deterministic fallback after missing the required citation format. A later live run revealed comma-grouped citations; validation now checks every grouped ID and normalizes valid groups to individual source buttons. Regression tests reject invented or unopened IDs inside a group. Citation validation checks IDs and known dates, not semantic entailment of every generated sentence. Deterministic status cards remain the authoritative assessment.

The examples deliberately use explicit years and approved aliases. The included evaluation is small and self-authored; report counts and provider failures, not generalized accuracy percentages.

## Source-card display update

The source cards now place model name, prompt version and completed processing status inside a collapsed **Extraction details** section. Original text, author, timestamp, source type and extraction mode remain on the card. Failed/in-progress extraction stays visible. **Under the hood** was renamed **Query details** and remains collapsed by default. JavaScript syntax validation passed; a fresh visual check was unavailable because the browser tool blocked page access. No backend extraction, review, or risk logic changed, and the AI-assistance disclosure is retained.

## Interface reliability review

Sixteen deterministic Node tests passed for scope isolation, stale-answer clearing, scoped evidence, safe answer formatting, source-state visibility, incompatible sample modes, input locking, outage messaging, sample review states, contributor links, and step-specific trace display. See `frontend-test-results.xml` and `submission-readiness-review.md`. These are code-level interface tests, not browser automation. The latest 57-test Python suite was rerun against Cloud. A read-only backend HTTP contract check also passed after restarting the app; see `current-api-check.json` and `readiness-state.json`.

## Natural source documents and live review sample

The four demo sources were rewritten as synthetic customer call notes, an engineering ticket, a platform chat, and an Acme follow-up. A fifth Cedar chat is the inbox review sample. They retain full explicit dates and approved names; this does not establish support for arbitrary company prose.

Three development attempts are retained as `natural-demo-run-01.json`, `natural-demo-run-02.json`, and `natural-demo-run-03.json`. The first produced a Cedar quote missing its subject. The second paraphrased the Acme replacement quote. The third mislabeled the SSO work forecast as a commitment deadline. Validation blocked each bad proposal; no invalid proposal was accepted. The extraction instructions were clarified to require complete, verbatim assertions and distinguish work forecasts from commitment deadlines. Each document records its own prompt hash and raw response. These failures have not been removed from the record.

`natural-demo-run.json` records the subsequent successful fresh-graph run: 12 baseline facts, one Acme revision, and one Cedar revision, all 14 matching the expected tuples and passing span/validation checks. Codex's synthetic QA runner used the ordinary review method for the baseline and Acme revision. This is explicitly not human review or a held-out benchmark. The Cedar proposal is left pending so a visitor can inspect and accept or reject it.

The resulting graph has five live documents, one pending proposal, and one supersession link. Acme is `no_known_conflict`, Beacon is `at_risk`, and Cedar is `unknown`. Beacon's proof has three dependency hops and links Maya, Leo, and Priya through their actual source authorship. The agent selected its read tools and returned a cited answer without template fallback; the saved report includes raw model responses and per-step query traces. Earlier graphs remain intact. The local app now uses this new graph; exports and the ZIP never include connection credentials.


## Date presentation and asset refresh

Calendar dates on history, commitment, forecast and review displays now use forms such as `Nov 4, 2026`. History keeps the old date struck through and the new date bold. Source quotes, database values, query parameters and risk arithmetic remain unchanged. A user screenshot revealed that the browser still showed the earlier script after the first edit. The page now embeds a content hash in script/style URLs and requests cache revalidation, so asset edits produce new download URLs. The focused API checks and all 16 interface checks passed; the earlier 57-test full-suite result remains recorded separately. See `asset-cache-test-results.xml` and `asset-cache-check.json` for the delivery checks. These do not claim a fresh visual browser inspection.

## Readability refactor verification

On October 17, code formatting was made consistent, risk calculations were split into named helpers, repeated agent response construction was consolidated, and contributor variables were renamed for clarity. No feature, prompt, query, interface text or styling change was intended. The HTML and CSS remain byte-for-byte identical to the preceding submission package. The browser JavaScript has the same syntax tree after excluding source positions and formatting metadata, including unchanged string and template values. Twenty-six formatting-only Python files likewise retain their syntax trees.

Comparison with the preceding implementation produced identical results for 400 seeded risk/exposure scenarios, four agent scenarios and three contributor cases. The full Python suite passed again: **57 passed, 0 skipped**, including six actual Cloud integration tests. All **16 frontend tests** also passed. These checks support behavior preservation; they are not a guarantee against every possible defect or a fresh visual browser inspection.

The app was restarted with the refactored backend. A read-only check confirmed the configured graph is connected, the current script is served, and the existing Acme, Beacon and Cedar deadlines remain November 10, November 4 and November 12, 2026. The user had accepted the Cedar revision after the saved natural-demo setup; the live graph now contains two supersession history records. No demo reset was performed. AI-assistance disclosure remains in the README.
