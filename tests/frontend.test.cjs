// Deterministic UI-state tests; no browser, model API, or database dependency.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');
const functions = source.slice(0, source.indexOf("document.addEventListener('click'"));

function page() {
  const elements = new Map();
  const element = (id) => {
    if (!elements.has(id))
      elements.set(id, {
        innerHTML: '',
        textContent: '',
        value: '',
        hidden: false,
        disabled: false,
        isConnected: true,
        dataset: {},
        className: '',
        classList: { toggle() {} },
        showModal() {
          this.open = true;
        },
      });
    return elements.get(id);
  };
  const controls = [
    'question',
    'scope',
    'agent-mode',
    'load-rehearsal',
    'fixture-revision',
    'load-live',
  ].map(element);
  const context = vm.createContext({
    document: { getElementById: element, querySelectorAll: () => controls },
    window: { scrollTo() {} },
    console,
  });
  vm.runInContext(functions, context);
  vm.runInContext('state.health={catalog:{people:[]}}', context);
  return { context, element, controls, evaluate: (code) => vm.runInContext(code, context) };
}
function bundle() {
  return {
    assessments: ['Acme', 'Beacon', 'Cedar'].map((name, i) => ({
      id: 'c' + i,
      name,
      customer: name,
      status: 'unknown',
      label: 'Cannot assess',
      deadline: null,
      flags: [],
      conflicts: [],
      paths: [],
      forecast_order_conflicts: [],
      known_work_count: 0,
      evidence_ids: [],
    })),
    documents: [],
    exposure: [],
    history: [],
    query_trace: [],
    entities: [],
    evidence: {},
    source_modes: ['live'],
  };
}
function answer() {
  return {
    assessments: [{ id: 'c0', name: 'Acme' }],
    answer: '**Acme** needs review [fact_abc].',
    agent_mode: 'live',
    opened_evidence: ['fact_abc'],
    warning: '',
    agent_trace: [],
    query_trace: [],
    evidence: {
      fact_abc: {
        fact: { kind: 'deadline', status: 'superseded' },
        document: {
          title: 'Earlier deadline',
          source_type: 'meeting',
          timestamp: '2026-11-01',
          mode: 'live',
        },
        author: { name: 'Maya' },
        span: { quote: 'Original promise', start: 0, end: 16 },
      },
    },
  };
}

test('agent-selected customer scope never replaces the full dashboard', () => {
  const p = page();
  p.context.renderBundle(bundle());
  const dashboard = p.element('commitments').innerHTML;
  p.context.renderAnswer(answer());
  assert.equal(p.element('stat-total').textContent, 3);
  assert.equal(p.element('commitments').innerHTML, dashboard);
  assert.match(p.element('answer').innerHTML, /Assessed: Acme/);
});
test('refreshing graph data removes old answers and their citation state', () => {
  const p = page();
  p.context.renderBundle(bundle());
  p.context.renderAnswer(answer());
  p.context.renderBundle(bundle());
  assert.equal(p.element('answer').hidden, true);
  assert.equal(p.element('answer').innerHTML, '');
  assert.equal(p.evaluate('Object.keys(state.answerEvidence).length'), 0);
});
test('scoped answer citations can open evidence absent from workspace snapshot', () => {
  const p = page();
  p.context.renderBundle(bundle());
  p.context.renderAnswer(answer());
  p.context.openEvidence(['fact_abc']);
  assert.equal(p.element('evidence-dialog').open, true);
  assert.match(p.element('evidence-content').innerHTML, /Original promise/);
});
test('markdown formatting cannot create HTML or an unopened citation button', () => {
  const p = page();
  const html = p.context.formatAnswer(
    '* **Acme** <img src=x onerror=alert(1)> [fact_abc] [fact_def]',
    ['fact_abc'],
  );
  assert.match(html, /<strong>Acme<\/strong>/);
  assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /data-evidence="fact_abc"/);
  assert.doesNotMatch(html, /data-evidence="fact_def"/);
});
test('completed processing is kept in collapsed details, separate from fact approval', () => {
  const p = page();
  const html = p.context.sourceCard({
    title: 'Launch notes',
    text: 'A source quote.',
    state: 'ready',
    mode: 'live',
    source_type: 'meeting',
    model: 'gemini-test',
    prompt_hash: 'abc',
    timestamp: '2026-11-01',
  });
  const [card, details] = html.split('<details');
  assert.doesNotMatch(card, /Extraction completed|gemini-test/);
  assert.match(details, /Facts are reviewed separately/);
  assert.match(details, /gemini-test/);
  assert.doesNotMatch(details, /\bopen(?:>|\s)/);
});
test('failed extraction stays prominent and its error is escaped', () => {
  const p = page();
  const html = p.context.sourceCard({
    title: 'Failed note',
    text: 'Text',
    state: 'failed',
    error: '<script>bad</script>',
    mode: 'live',
  });
  const card = html.split('<details')[0];
  assert.match(card, /Extraction failed/);
  assert.match(card, /&lt;script&gt;/);
  assert.doesNotMatch(card, /<script>/);
});
test('live source mode disables rehearsal writes without disabling live reads', () => {
  const p = page();
  p.context.renderBundle(bundle());
  assert.equal(p.element('load-rehearsal').disabled, true);
  assert.equal(p.element('fixture-revision').disabled, true);
  assert.equal(p.element('load-live').disabled, false);
});
test('changing to rehearsal data updates the button restrictions', () => {
  const p = page();
  p.context.renderBundle(bundle());
  p.context.renderBundle({ ...bundle(), source_modes: ['rehearsal'] });
  assert.equal(p.element('load-rehearsal').disabled, false);
  assert.equal(p.element('load-live').disabled, true);
});
test('in-flight request locks inputs and preserves restrictions computed during it', async () => {
  const p = page();
  let release;
  const pending = p.context.run(async () => {
    p.context.setAvailability('load-rehearsal', true);
    await new Promise((resolve) => {
      release = resolve;
    });
  });
  assert.equal(p.element('question').disabled, true);
  assert.equal(p.element('scope').disabled, true);
  release();
  await pending;
  assert.equal(p.element('question').disabled, false);
  assert.equal(p.element('load-rehearsal').disabled, true);
});
test('database failure clearly labels retained results as stale and hides old answer', async () => {
  const p = page();
  p.context.renderBundle(bundle());
  p.context.renderAnswer(answer());
  await p.context.run(async () => {
    const e = new Error('Database unavailable');
    e.code = 'database_unavailable';
    throw e;
  });
  assert.equal(p.element('snapshot-note').hidden, false);
  assert.match(p.element('snapshot-note').textContent, /Previous results/);
  assert.equal(p.element('answer').hidden, true);
  assert.equal(p.element('db-status').textContent, 'Connection unavailable');
});
test('a model failure does not falsely mark the database unavailable', async () => {
  const p = page();
  p.context.renderBundle(bundle());
  await p.context.run(async () => {
    const e = new Error('Gemini unavailable');
    e.code = 'model_unavailable';
    throw e;
  });
  assert.equal(p.element('db-status').textContent, 'Graph connected');
  assert.equal(p.element('snapshot-note').hidden, true);
});
test('empty live inbox offers a sample only against its expected current deadline', () => {
  const p = page();
  const b = bundle();
  b.assessments[2].id = 'cedar_export';
  b.assessments[2].deadline = '2026-11-08';
  p.context.renderBundle(b);
  assert.match(p.context.reviewEmptyState(), /data-review-sample="live"/);
  b.assessments[2].deadline = '2026-11-15';
  p.context.renderBundle(b);
  assert.doesNotMatch(p.context.reviewEmptyState(), /data-review-sample/);
});
test('processed sample links to history rather than silently duplicating a proposal', () => {
  const p = page();
  p.evaluate('state.health.examples={review_sample:{document:{text:"Cedar sample"}}}');
  const b = bundle();
  b.documents = [{ text: 'Cedar sample', state: 'ready' }];
  p.context.renderBundle(b);
  assert.match(p.context.reviewEmptyState(), /already processed/);
  assert.match(p.context.reviewEmptyState(), /data-view="sources"/);
  assert.doesNotMatch(p.context.reviewEmptyState(), /data-review-sample/);
});
test('rehearsal inbox never offers an unlabeled live sample', () => {
  const p = page();
  const b = bundle();
  b.source_modes = ['rehearsal'];
  b.assessments[0].id = 'acme_sso';
  b.assessments[0].deadline = '2026-11-04';
  p.context.renderBundle(b);
  assert.match(p.context.reviewEmptyState(), /data-review-sample="rehearsal"/);
  assert.match(p.context.reviewEmptyState(), /hand-authored/);
  assert.doesNotMatch(p.context.reviewEmptyState(), /data-review-sample="live"/);
});
test('contributor links open cited spans without asserting work ownership', () => {
  const p = page();
  const html = p.context.renderContributors({
    paths: [{}],
    contributors: [
      {
        name: 'Maya <x>',
        role: 'Customer success',
        sources: [
          { title: 'Launch note', fact_ids: ['fact_abc', 'fact_def'], context: ['Deadline'] },
        ],
      },
    ],
  });
  assert.match(html, /People with relevant context/);
  assert.match(html, /Maya &lt;x&gt;/);
  assert.match(html, /data-evidence-ids="fact_abc,fact_def"/);
  assert.match(html, /work ownership is unverified/);
});
test('tool trace distinguishes database reads from evidence already retrieved', () => {
  const p = page();
  const a = answer();
  a.agent_trace = [
    {
      tool: 'assess_commitments',
      arguments: { ids: ['acme_sso'] },
      source: 'Gemini',
      summary: '1 commitment',
      operation: 'FalkorDB reads',
      queries: [
        {
          name: 'paths',
          cypher: 'MATCH p RETURN p',
          parameters: { id: 'acme_sso' },
          elapsed_ms: 1,
        },
      ],
    },
    {
      tool: 'read_evidence',
      arguments: { fact_ids: ['fact_abc'] },
      source: 'Gemini',
      summary: '1 source',
      operation: 'No additional database query',
      queries: [],
      evidence_ids: ['fact_abc', 'fact_missing'],
    },
  ];
  p.context.renderAnswer(a);
  const html = p.element('answer').innerHTML;
  assert.match(html, /Executed Cypher · 1 reads/);
  assert.match(html, /No additional database query/);
  assert.match(html, /Earlier deadline · deadline/);
  assert.doesNotMatch(html, /data-evidence="fact_missing"/);
});
