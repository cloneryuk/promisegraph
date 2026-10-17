const $ = (id) => document.getElementById(id);
const esc = (value) =>
  String(value ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
  );
const state = { health: null, bundle: null, answerEvidence: {}, facts: [], busy: false };
const names = {
  overview: 'Commitments',
  ingest: 'Add knowledge',
  review: 'Review inbox',
  sources: 'Sources & history',
  setup: 'Connection settings',
};
const flagNames = {
  forecast_order_conflict: 'Forecast order inconsistent',
  downstream_work_unassessed: 'Downstream work unassessed',
  unlinked_commitment: 'No linked work',
  missing_forecast: 'Forecast missing',
  pending_relevant_fact: 'Unreviewed evidence',
  unresolved_entity: 'Unresolved identity',
  depth_boundary: 'Traversal depth reached',
  result_limit: 'Path limit reached',
  cycle_detected: 'Dependency cycle',
};
function show(view) {
  document.querySelectorAll('.view').forEach((e) => (e.hidden = e.id !== `view-${view}`));
  document
    .querySelectorAll('.nav')
    .forEach((e) => e.classList.toggle('active', e.dataset.view === view));
  $('page-name').textContent = names[view];
  window.scrollTo({ top: 0, behavior: 'instant' });
  if (view === 'review') run(loadQueue);
}
function notice(text, error = false) {
  $('notice').textContent = text;
  $('notice').hidden = !text;
  $('notice').classList.toggle('error', error);
}
async function api(url, body) {
  let response;
  try {
    response = await fetch(
      url,
      body === undefined
        ? {}
        : {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          },
    );
  } catch (_) {
    const error = new Error(
      'The app server could not be reached. Reconnect, then refresh the graph.',
    );
    error.code = 'service_unavailable';
    throw error;
  }
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(
      typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail || result),
    );
    error.code = result.code;
    throw error;
  }
  return result;
}
async function run(fn, message = '') {
  if (state.busy) return;
  state.busy = true;
  const controls = [...document.querySelectorAll('button,input,textarea,select')].map((control) => [
    control,
    control.disabled,
  ]);
  controls.forEach(([control]) => (control.disabled = true));
  if (message) notice(message);
  try {
    await fn();
  } catch (e) {
    if (['database_unavailable', 'service_unavailable'].includes(e.code)) markUnavailable();
    notice(e.message, true);
  } finally {
    controls.forEach(([control, disabled]) => {
      if (control.isConnected)
        control.disabled = control.dataset.availability
          ? control.dataset.availability === 'disabled'
          : disabled;
    });
    state.busy = false;
  }
}
function clearAnswer() {
  $('answer').hidden = true;
  $('answer').innerHTML = '';
  state.answerEvidence = {};
}
function markUnavailable() {
  clearAnswer();
  $('db-status').textContent = 'Connection unavailable';
  $('db-dot').className = 'dot amber';
  $('snapshot-note').hidden = false;
  $('snapshot-note').textContent = state.bundle
    ? 'Previous results are shown below. The latest graph read failed; refresh before relying on these results.'
    : 'The graph is unavailable. No assessment has been loaded.';
}
function setAvailability(id, blocked, reason = '') {
  const control = $(id);
  control.dataset.availability = blocked ? 'disabled' : 'enabled';
  control.disabled = state.busy || blocked;
  control.title = reason;
}
function updateDemoControls() {
  const modes = state.bundle?.source_modes || [];
  const live = modes.includes('live'),
    rehearsal = modes.includes('rehearsal');
  const explanation = live
    ? 'This workspace uses live extraction. Use a fresh graph for rehearsal.'
    : rehearsal
      ? 'This workspace uses rehearsal data. Use a fresh graph for live sample extraction.'
      : 'Choose live extraction or the labeled rehearsal dataset.';
  setAvailability('load-rehearsal', live, live ? explanation : '');
  setAvailability('fixture-revision', live, live ? explanation : '');
  setAvailability('load-live', rehearsal, rehearsal ? explanation : '');
  $('demo-mode-note').textContent = explanation;
  $('revision-mode-note').textContent = live
    ? 'Use Fill the revision note and Extract with Gemini in this live workspace.'
    : 'The rehearsal button loads a hand-authored proposal. It does not call Gemini.';
}
function renderQueries(trace) {
  return trace
    .map(
      (q) =>
        `<details><summary>${esc(q.name)} · ${q.elapsed_ms} ms</summary><pre>${esc(q.cypher)}\n\nParameters: ${esc(JSON.stringify(q.parameters, null, 2))}</pre></details>`,
    )
    .join('');
}
function formatAnswer(text, opened) {
  return esc(text)
    .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
    .replace(/^[ \t]*[-*] /gm, '• ')
    .replace(/\[(fact_[a-f0-9]+)\]/g, (match, id) =>
      opened.includes(id)
        ? `<button class="evidence-button" data-evidence="${id}">[source ↗]</button>`
        : match,
    );
}
function renderTrace(trace, evidence) {
  return trace
    .map(
      (t, i) =>
        `<div class="trace-entry"><div class="trace-heading"><span class="step-number">${i + 1}</span><strong>${esc(t.tool)}</strong><span>${esc(t.source)}</span></div><p>${esc(t.summary)}</p><p class="subtle">${esc(t.operation || '')}</p><details><summary>Tool arguments</summary><pre>${esc(JSON.stringify(t.arguments, null, 2))}</pre></details>${t.queries?.length ? `<details><summary>Executed Cypher · ${t.queries.length} reads</summary>${renderQueries(t.queries)}</details>` : ''}<div class="trace-sources">${(
          t.evidence_ids || []
        )
          .filter((id) => evidence[id])
          .map(
            (id) =>
              `<button class="source-chip" data-evidence="${esc(id)}">${esc(evidence[id].document.title)} · ${esc(evidence[id].fact.kind)} ↗</button>`,
          )
          .join('')}</div></div>`,
    )
    .join('');
}
function renderAnswer(answer) {
  state.answerEvidence = { ...answer.trace_evidence, ...answer.evidence };
  const cited = formatAnswer(answer.answer, answer.opened_evidence || []);
  $('answer').hidden = false;
  $('answer').innerHTML =
    `<span class="eyebrow">${esc(answer.agent_mode)} ANSWER</span><p class="answer-scope">Assessed: ${esc(answer.assessments.map((r) => r.name).join(', '))}</p><p>${cited}</p>${answer.warning ? `<p class="answer-warning">${esc(answer.warning)}</p>` : ''}<details open><summary>Observed tool calls · ${answer.agent_trace.length} steps</summary>${renderTrace(answer.agent_trace, state.answerEvidence)}</details><details class="answer-queries"><summary>Queries for this answer</summary>${renderQueries(answer.query_trace || [])}</details>`;
}
function renderContributors(row) {
  if (!row.contributors?.length) return '';
  return `<div class="contributors"><p class="contributors-title">People with relevant context</p>${row.contributors.map((p) => `<div class="contributor"><div><strong>${esc(p.name)}</strong><span> · ${esc(p.role)}</span></div>${p.sources.map((s) => `<button class="source-chip" data-evidence-ids="${esc(s.fact_ids.join(','))}" title="${esc(s.context.join('; '))}">${esc(s.title)} ↗</button>`).join('')}</div>`).join('')}<small>Authors of ${row.paths.length ? 'sources on the displayed path' : 'this commitment’s sources'}; work ownership is unverified.</small></div>`;
}
function sourceCard(d) {
  const sourceNames = { meeting: 'Meeting note', ticket: 'Ticket', chat: 'Chat message' };
  const modes = { live: 'Live extraction', rehearsal: 'Scripted rehearsal' };
  const processing = {
    ready: 'Extraction completed',
    failed: 'Extraction failed',
    extracting: 'Extraction in progress',
  };
  const author = state.health.catalog.people.find((p) => p.id === d.author_id)?.name || d.author_id;
  const status =
    d.state === 'ready'
      ? ''
      : `<p class="source-status" role="status">${esc(processing[d.state] || 'Processing status unknown')}</p>`;
  return `<article class="panel"><span class="eyebrow">${esc(sourceNames[d.source_type] || d.source_type)} · ${esc(modes[d.mode] || d.mode)}</span><h3 class="space">${esc(d.title)}</h3><p>${esc(author)} · ${esc(d.timestamp)}</p>${status}<pre>${esc(d.text)}</pre>${d.error ? `<p class="source-status">${esc(d.error)}</p>` : ''}<details class="extraction-details"><summary>Extraction details</summary><dl><dt>Processing</dt><dd>${esc(processing[d.state] || d.state)}. Facts are reviewed separately.</dd><dt>Model</dt><dd>${esc(d.model || 'Not recorded')}</dd><dt>Prompt version</dt><dd>${esc(d.prompt_hash || 'Not recorded')}</dd></dl></details></article>`;
}
function date(value) {
  if (!value) return 'Not established';
  const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!parts) return value;
  const months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ];
  const month = months[Number(parts[2]) - 1];
  return month ? `${month} ${Number(parts[3])}, ${parts[1]}` : value;
}
function entity(id) {
  return state.bundle?.entities.find((e) => e.id === id)?.name || id;
}
function flags(list) {
  return list
    .map((f) => `<span class="flag">${esc(flagNames[f] || f.replaceAll('_', ' '))}</span>`)
    .join('');
}
async function health() {
  state.health = await api('/api/health');
  const h = state.health;
  $('db-status').textContent = h.database_connected ? 'Graph connected' : 'Graph offline';
  $('db-dot').className = 'dot ' + (h.database_connected ? 'green' : 'amber');
  $('setup-banner').hidden = h.database_connected;
  $('connection-details').innerHTML =
    `<p><b>FalkorDB:</b> ${h.database_connected ? 'Connected' : 'Not connected'}<br><b>Gemini:</b> ${h.gemini_configured ? 'Key configured' : 'Key missing'}<br><b>Model:</b> ${esc(h.model)}<br><b>Graph:</b> ${esc(h.graph)}</p>${h.error ? `<p>${esc(h.error)}</p>` : ''}`;
  const author = $('doc-author').value,
    scope = $('scope').value;
  $('doc-author').innerHTML = h.catalog.people
    .map((p) => `<option value="${esc(p.id)}">${esc(p.name)} · ${esc(p.role)}</option>`)
    .join('');
  if (h.catalog.people.some((p) => p.id === author)) $('doc-author').value = author;
  $('scope').innerHTML =
    '<option value="">Automatic scope</option>' +
    h.catalog.entities
      .filter((e) => e.kind === 'commitment')
      .map((e) => `<option value="${esc(e.id)}">${esc(e.name)}</option>`)
      .join('');
  if (h.catalog.entities.some((e) => e.id === scope && e.kind === 'commitment'))
    $('scope').value = scope;
  if (!h.gemini_configured) $('agent-mode').value = 'rehearsal';
  if (!h.database_connected) markUnavailable();
  return h;
}
function renderBundle(bundle) {
  clearAnswer();
  state.bundle = bundle;
  $('snapshot-note').hidden = true;
  $('db-status').textContent = 'Graph connected';
  $('db-dot').className = 'dot green';
  updateDemoControls();
  const rows = bundle.assessments;
  $('stat-total').textContent = rows.length;
  $('stat-risk').textContent = rows.filter((r) => r.status === 'at_risk').length;
  $('stat-gaps').textContent = rows.filter((r) =>
    r.flags.some((f) => !['forecast_order_conflict', 'downstream_work_unassessed'].includes(f)),
  ).length;
  $('stat-docs').textContent = bundle.documents.length;
  $('commitments').innerHTML = rows.length
    ? rows
        .map((r) => {
          const conflict = r.conflicts[0];
          const path =
            conflict?.path || [...r.paths].sort((a, b) => b.nodes.length - a.nodes.length)[0];
          const sentence = conflict
            ? `${esc(conflict.work_name)} is forecast for <strong>${esc(date(conflict.forecast))}</strong>, after the promised <strong>${esc(date(conflict.deadline))}</strong>.`
            : r.status === 'unknown'
              ? 'The graph does not contain enough accepted evidence to assess this commitment.'
              : 'No deadline conflict in the accepted forecasts. Delivery feasibility remains unassessed.';
          return `<article class="commitment"><div class="card-top"><div class="customer"><span class="customer-logo">${esc(r.customer[0])}</span><div><h3>${esc(r.name)}</h3><small>Promised ${esc(date(r.deadline))} · ${r.known_work_count} linked work items</small></div></div><span class="badge ${esc(r.status)}">${esc(r.label)}</span></div><p class="conflict-line">${sentence}</p>${path ? `<div class="path">${path.nodes.map((id, i) => `${i ? '<i>→</i>' : ''}${i ? `<button data-evidence="${esc(path.facts[i - 1])}" class="${conflict && i === path.nodes.length - 1 ? 'late' : ''}">${esc(entity(id))}</button>` : `<span class="path-node">${esc(r.customer)}</span>`}`).join('')}</div>` : ''}<div class="flags">${flags(r.flags)}</div>${r.forecast_order_conflicts.length ? `<details class="subtle"><summary>Why the forecasts disagree</summary>${r.forecast_order_conflicts.map((f) => `<p>${esc(entity(f.dependent))}: ${esc(date(f.dependent_date))} → requires ${esc(entity(f.prerequisite))}: ${esc(date(f.prerequisite_date))}. Informational; does not change the deadline verdict.</p>`).join('')}</details>` : ''}${renderContributors(r)}<div class="card-bottom"><small>${path ? `${path.facts.length} hops on the displayed proof` : 'No known dependency path'}</small><button class="evidence-button" data-commitment="${esc(r.id)}">View source evidence ↗</button></div></article>`;
        })
        .join('')
    : '<div class="empty"><h3>Ready for your first source.</h3><p>Load the synthetic workspace or add a note.</p></div>';
  $('exposure').innerHTML = bundle.exposure.length
    ? bundle.exposure
        .map((e) => `<div class="exposure-row"><span>${esc(e.name)}</span><b>${e.count}</b></div>`)
        .join('')
    : '<p class="muted">No accepted dependencies yet.</p>';
  $('queries').innerHTML = renderQueries(bundle.query_trace);
  $('source-list').innerHTML =
    bundle.documents.map(sourceCard).join('') || '<p class="muted">No documents yet.</p>';
  $('history-list').innerHTML =
    bundle.history
      .map(
        (h) =>
          `<article class="history-item"><strong>${esc(entity(h.new.subject_id))}</strong><p><s>${esc(date(h.old.date))}</s> → <b>${esc(date(h.new.date))}</b></p><p>SUPERSEDES · The earlier fact is retained with superseded status.</p><blockquote>${esc(h.new.quote)}</blockquote><details><summary>Earlier source</summary><blockquote>${esc(h.old.quote)}</blockquote></details></article>`,
      )
      .join('') || '<p class="muted">No accepted replacements yet.</p>';
}
async function refresh() {
  clearAnswer();
  const bundle = await api('/api/overview');
  renderBundle(bundle);
  await loadQueue();
}
function reviewEmptyState() {
  const rehearsal = state.bundle?.source_modes.includes('rehearsal');
  const sample = rehearsal ? state.health.examples?.revision : state.health.examples?.review_sample;
  const done =
    sample &&
    state.bundle?.documents.some((d) => d.text === sample.document.text && d.state === 'ready');
  const subject = rehearsal ? 'acme_sso' : 'cedar_export';
  const expected = rehearsal ? '2026-11-04' : '2026-11-08';
  const current = state.bundle?.assessments.find((r) => r.id === subject);
  let action;
  if (done)
    action =
      '<p>The sample was already processed. Its review decision is retained in the graph.</p><button class="secondary" data-view="sources">View sample sources & history ↗</button>';
  else if (current?.deadline === expected)
    action = rehearsal
      ? '<p>Try the labeled Acme rehearsal revision. It uses a hand-authored proposal.</p><button class="secondary" data-review-sample="rehearsal">Queue rehearsal revision ↗</button>'
      : '<p>Try a Cedar date revision: inspect the note, extract with Gemini, then accept or reject. Acme and Beacon stay unchanged.</p><button class="primary" data-review-sample="live">Try reviewing a sample ↗</button>';
  else
    action =
      '<p>Add a source document, or load and review the baseline demo notes first.</p><button class="secondary" data-view="ingest">Add a source note ↗</button>';
  return `<div class="empty"><span class="empty-icon">✓</span><h3>Nothing awaiting review.</h3>${action}</div>`;
}
async function loadQueue() {
  state.facts = await api('/facts?status=pending');
  $('queue-count').textContent = state.facts.length;
  $('review-list').innerHTML = state.facts.length
    ? state.facts
        .map((f) => {
          const invalid = f.validation_flags.length > 0;
          return `<article class="review-item"><div class="review-head"><div><span class="eyebrow">${esc(f.kind)} · ${esc(f.mode)}</span><h3 style="margin-top:10px">${esc(f.raw_subject)} ${f.kind === 'requires' ? '→ ' + esc(f.raw_object) : '→ ' + esc(date(f.date || f.date_expression))}</h3></div><span class="badge pending">Pending review</span></div><blockquote>${esc(f.quote)}</blockquote><p class="subtle">${esc(f.evidence?.document?.title || 'Source unavailable')} · ${esc(f.evidence?.author?.name || '')} · span ${f.start}–${f.end}</p>${invalid ? `<div class="flags">${flags(f.validation_flags)}</div><p class="subtle">Acceptance blocked. Reject this proposal or submit a corrected source as a new document.</p>` : ''}${f.current ? `<p>Current accepted date: <strong>${esc(date(f.current.date))}</strong>. Proposed date: <strong>${esc(date(f.date))}</strong>.</p>` : ''}<div class="review-actions">${f.current ? `<label><input type="checkbox" data-confirm="${esc(f.id)}"> I checked the explicit replacement and earlier date.</label>` : '<span class="subtle">Verify the meaning, not only the quote.</span>'}<button class="secondary reject" data-review="reject" data-id="${esc(f.id)}">Reject</button><button class="primary" data-review="accept" data-id="${esc(f.id)}" ${invalid ? 'disabled' : ''}>${f.current ? 'Accept replacement' : 'Accept fact'}</button></div></article>`;
        })
        .join('')
    : reviewEmptyState();
}
function openEvidence(ids) {
  const evidence = { ...state.bundle?.evidence, ...state.answerEvidence };
  $('evidence-content').innerHTML =
    ids
      .filter((id) => evidence[id])
      .map((id) => {
        const e = evidence[id];
        return `<article class="evidence-entry"><h3>${esc(e.document.title)}</h3><small>${esc(e.document.source_type)} · ${esc(e.author.name || 'Unknown author')} · ${esc(e.document.timestamp)}</small><blockquote>${esc(e.span.quote)}</blockquote><small>${esc(e.fact.kind)} · ${esc(e.fact.status)} · ${esc(e.document.mode)}<br>${esc(id)}<br>Document → span ${e.span.start}–${e.span.end} → fact</small></article>`;
      })
      .join('') || '<p>No accepted source evidence is linked to this selection.</p>';
  $('evidence-dialog').showModal();
}
function fillDocument(d) {
  $('doc-title').value = d.title;
  $('doc-text').value = d.text;
  $('doc-time').value = d.timestamp;
  $('doc-zone').value = d.timezone;
  $('doc-type').value = d.source_type;
  $('doc-author').value = d.author_id;
  show('ingest');
}
function fillRevision() {
  fillDocument(state.health.examples.revision.document);
}
function fillReviewSample() {
  fillDocument(state.health.examples.review_sample.document);
  notice(
    'Synthetic review sample filled. Inspect the note, then Extract with Gemini. Acceptance changes only Cedar’s deadline; its missing work links remain visible.',
  );
}
document.addEventListener('click', (e) => {
  const button = e.target.closest('button');
  if (!button) return;
  if (button.dataset.view) show(button.dataset.view);
  if (button.dataset.evidence) openEvidence([button.dataset.evidence]);
  if (button.dataset.evidenceIds) openEvidence(button.dataset.evidenceIds.split(','));
  if (button.dataset.reviewSample === 'live') fillReviewSample();
  if (button.dataset.reviewSample === 'rehearsal') $('fixture-revision').click();
  if (button.dataset.commitment)
    openEvidence(
      state.bundle.assessments.find((r) => r.id === button.dataset.commitment).evidence_ids,
    );
  if (button.dataset.review)
    run(async () => {
      const f = state.facts.find((f) => f.id === button.dataset.id);
      const confirmed = !!document.querySelector(`[data-confirm="${f.id}"]`)?.checked;
      if (button.dataset.review === 'accept' && f.current && !confirmed)
        throw new Error('Check the replacement confirmation after reviewing both dates.');
      await api(`/facts/${f.id}/review`, {
        action: button.dataset.review,
        expected_old_id: f.current?.id || '',
        confirm_replacement: confirmed,
      });
      await refresh();
      notice(
        button.dataset.review === 'accept'
          ? 'Fact accepted. The graph assessment has been refreshed.'
          : 'Proposal rejected.',
      );
    }, 'Saving review decision…');
});
$('close-dialog').onclick = () => $('evidence-dialog').close();
$('refresh').onclick = () =>
  run(async () => {
    await health();
    await refresh();
    notice('Graph refreshed.');
  }, 'Reading the graph…');
$('refresh-queue').onclick = () => run(loadQueue);
$('check-connection').onclick = () =>
  run(async () => {
    const h = await health();
    notice(
      h.database_connected
        ? 'FalkorDB connected. Gemini key ' +
            (h.gemini_configured ? 'is configured.' : 'is still missing.')
        : 'FalkorDB is not connected. Check the local .env fields.',
      !h.database_connected,
    );
    if (h.database_connected) await refresh();
  }, 'Checking connections…');
for (const [id, mode] of [
  ['load-rehearsal', 'rehearsal'],
  ['load-live', 'live'],
])
  $(id).onclick = () =>
    run(
      async () => {
        const result = await api('/api/demo', { mode, include_revision: false });
        await refresh();
        notice(
          mode === 'rehearsal'
            ? 'Loaded pre-reviewed, hand-authored synthetic fixtures into FalkorDB. No model extraction was used.'
            : 'Gemini extraction finished. Review each proposal before assessing.',
        );
        if (result.review_required) show('review');
      },
      mode === 'live'
        ? 'Extracting three synthetic source documents with Gemini. This may take a few minutes…'
        : 'Loading reviewed rehearsal facts into FalkorDB…',
    );
$('fill-revision').onclick = fillRevision;
$('fixture-revision').onclick = () =>
  run(async () => {
    await api('/api/demo', { mode: 'rehearsal', include_revision: true });
    await refresh();
    show('review');
    notice('Hand-authored rehearsal revision queued. Inspect and accept the replacement.');
  }, 'Adding the rehearsal revision…');
$('document-form').onsubmit = (e) => {
  e.preventDefault();
  run(async () => {
    const result = await api('/documents', {
      title: $('doc-title').value,
      text: $('doc-text').value,
      source_type: $('doc-type').value,
      author_id: $('doc-author').value,
      timestamp: $('doc-time').value,
      timezone: $('doc-zone').value,
    });
    await refresh();
    show('review');
    notice(
      result.duplicate
        ? 'This document was already ingested; its review state was preserved.'
        : `${result.facts.length} proposals extracted with Gemini. Check each source before accepting.`,
    );
  }, 'Extracting source facts with Gemini…');
};
$('ask-form').onsubmit = (e) => {
  e.preventDefault();
  run(async () => {
    clearAnswer();
    const request = {
      question: $('question').value,
      mode: $('agent-mode').value,
      scope: $('scope').value ? [$('scope').value] : [],
    };
    const answer = await api('/assess', request);
    // The agent may choose a narrower scope when the selector uses Automatic scope.
    // Its answer and query trace must never replace the full-workspace dashboard.
    renderAnswer(answer);
    notice('Assessment complete. Computed statuses are independent of the generated explanation.');
  }, 'Tracing commitments and opening source evidence…');
};
$('question').oninput = clearAnswer;
$('scope').onchange = clearAnswer;
$('agent-mode').onchange = clearAnswer;
$('export').onclick = () =>
  run(async () => {
    const records = await api('/api/export');
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(records, null, 2)], { type: 'application/json' }),
    );
    const a = document.createElement('a');
    a.href = url;
    a.download = 'promisegraph-records.json';
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    notice('Graph records exported, including source documents and saved model responses.');
  });
run(async () => {
  const h = await health();
  if (h.database_connected) await refresh();
});
