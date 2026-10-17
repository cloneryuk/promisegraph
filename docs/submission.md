# Submission checklist

Track: **03 — Company Brain**

Latest [readiness review](submission-readiness-review.md): interface fixes are included; public uploads, participant walkthrough and final visual check remain outstanding.

Suggested title: **PromiseGraph — Every promise has a path**

Suggested description:

> PromiseGraph connects promises hidden in customer notes to the engineering work behind them. Gemini proposes source-backed facts; a person reviews them. FalkorDB stores the knowledge, traverses required dependencies, and preserves superseded decisions. A bounded agent selects commitments and source evidence while deterministic code identifies deadline conflicts and uncertainty. One approved deadline update changes the relevant customer assessment without rewriting history or declaring unlinked commitments safe.

- [x] Configure FalkorDB Cloud and Gemini in local `.env`.
- [x] Run the full graph integration suite against the actual instance; 57 Python tests passed, including 6 Cloud integrations. Previously inspected server module version 42200. Another 16 JavaScript interface tests passed.
- [x] Run and preserve a real extraction evaluation; failures are retained in `docs/`.
- [x] Test a clean dependency install and app stop/restart against the same graph.
- [ ] Review the risk logic and supersession query so you can explain them.
- [x] Create a connected demonstration with live extraction and actual agent calls: `docs/demo-walkthrough.mp4`. This is an edited, captioned sequence of actual screenshots, not a continuous recording. See `docs/verification.md` for preparation and QA-review disclosure.
- [x] Verify natural demo notes and a genuine pending Cedar review proposal with Gemini and FalkorDB; see `docs/natural-demo-run.json`, including links to earlier failed attempts in the verification notes.
- [ ] Record the current natural-note, contributor, and per-step trace UI using `docs/demo-script.md`. The included MP4 shows an earlier build.
- [ ] Upload the source to a public repository. Never upload `.env`, local credentials, caches, or private data.
- [x] Include README, graph model, query files, AI disclosure, and local setup instructions in the source package. Verify their accessibility again after publishing.
- [ ] Add the public repo URL and working video URL to the event submission.
- [ ] Choose Track 03 — Company Brain. Submit before the event deadline.

The official rules list October 18, 2026 at 11:59 PM IST as the submission close and allow Cloud, Docker, or self-hosted FalkorDB. Check the event page for changes: https://www.wemakedevs.org/hackathons/falkordb/rules

No public repository or video URL is pre-filled because those uploads have not happened. Upload the local MP4 to your chosen video host and the packaged source to a public repository, then place the resulting URLs in the event form. Never include the local `.env`.
