# Scenario coverage

These are coverage scenarios, not an accuracy denominator. See `verification.md` for what has actually run.

| # | Scenario | Checks |
| --- | --- | --- |
| 1 | Direct late prerequisite and source facts | `test_direct_conflict`, `test_three_hop_conflict_and_source_chain` |
| 2 | Four-hop proof | `test_four_hop_evidence` |
| 3 | Parallel branches and forecast ordering | `test_parallel_branches_and_computed_order_warning` |
| 4 | Two routes, deduplicated exposure | `test_two_routes_deduplicate_exposure` |
| 5 | No known conflict plus limitation | `test_later_deadline_keeps_order_warning_and_other_customer_risk` |
| 6 | Unlinked commitment | `test_unlinked_is_unknown` |
| 7 | Missing forecast | `test_missing_forecast_is_unknown_without_proof` |
| 8 | Positive late proof plus another gap | `test_positive_proof_survives_other_missing_branch` |
| 9 | Approved and unknown aliases | `test_aliases_exact_only`, extraction note `approved_and_unknown_alias` |
| 10 | Negated date | `test_negation_is_not_accepted_as_affirmation`, extraction note `negated_forecast` |
| 11 | Relative dates | `test_unsupported_dates`, extraction note `relative_date` |
| 12 | New conflicting date remains pending | `test_conflicting_new_date_preserves_current` (database), `test_pending_never_removes_accepted_risk` |
| 13 | Supersession, repeat, stale, reconnect | `test_supersession_first_repeat_stale_and_reconnect` (database) |
| 14 | Reingestion idempotency | `test_ingestion_idempotent_and_provenance` (database) |
| 15 | Cycles, depth and row limits | `test_cycle_flag_and_termination_without_conflict`, `test_depth_limit_is_incomplete_not_safe`, `test_row_limit_marks_incomplete`, `test_bounded_cycle_query_terminates` (database) |
| 16 | Natural notes keep exact entity/date/quote spans | `test_natural_demo_and_review_sample_keep_valid_exact_source_spans`; saved live natural-demo attempts |
| 17 | People follow the displayed proof, excluding other branches and old facts | `test_contributors_follow_displayed_proof_and_exclude_other_branch_and_history`, `test_unlinked_commitment_only_lists_its_own_source_author` |
| 18 | Cedar review does not alter other customers or imply safety | `test_cedar_review_sample_preserves_other_customers_and_missing_work_gap` (database) |
| 19 | Repeated agent scopes retain step-specific queries and earlier opened sources | `test_trace_attaches_queries_only_to_assessment_and_retains_earlier_opened_sources` |

Sixteen deterministic Node interface checks in `tests/frontend.test.cjs` cover scope separation, stale answers, citations, safe rendering, source states, mode restrictions, request locking, outages, sample inbox actions, contributor links, and trace display. These do not replace visual browser testing.

Additional integrity: `test_read_tools_reject_writes` (database), `test_database_outage_never_returns_empty_success`, broken provenance handling, exact spans, invalid model citations, actual tool event traces, cross-origin write rejection, and assets without database access.
