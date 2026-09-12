/* ---------------------------------------------------------------------------
   overlooked-bench leaderboard.

   Reads the committed run data directly: `../data/runs/index.json` for the list
   of runs, then `../data/runs/<id>/summary.json` for the selected one. There is
   no API and no database - the page renders the same files a reviewer would read
   by hand, which is the point.

   Because it uses fetch(), it needs to be served over HTTP. From the repo root:
       python -m http.server 8000
       open http://localhost:8000/site/
   --------------------------------------------------------------------------- */

'use strict';

const RUNS_BASE = '../data/runs';

const els = {
  status: document.getElementById('status'),
  content: document.getElementById('content'),
  select: document.getElementById('run-select'),
  provenance: document.getElementById('provenance-band'),
  lbHead: document.getElementById('leaderboard-head'),
  lbBody: document.getElementById('leaderboard-body'),
  asymBody: document.getElementById('asym-body'),
  asymDetail: document.getElementById('asym-detail'),
  charts: document.getElementById('charts'),
  diagnostics: document.getElementById('diagnostics'),
};

let current = null;
let sortState = { key: 'overall_index', dir: 'desc' };

/* --- helpers ------------------------------------------------------------- */

const fmt = (v, d = 1) => (v === null || v === undefined ? ' - ' : Number(v).toFixed(d));

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;
    else if (k === 'html') node.innerHTML = v;
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const child of [].concat(children)) {
    if (child) node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
  }
  return node;
}

/* A number with a magnitude bar behind it. The number is always present - 
   never a bar on its own, which would force the reader to estimate. */
function barCell(value, max = 100, warn = false) {
  const pct = Math.max(0, Math.min(100, (Number(value) / max) * 100));
  const td = el('td', { class: 'num' });
  const wrap = el('div', { class: 'cell-bar' + (warn ? ' warnbar' : '') });
  wrap.appendChild(el('span', { text: fmt(value) }));
  const track = el('span', { class: 'track' });
  track.appendChild(el('span', { class: 'fill', style: `width:${pct}%` }));
  wrap.appendChild(track);
  td.appendChild(wrap);
  return td;
}

/* --- provenance ---------------------------------------------------------- */

function renderProvenance(s) {
  const items = [
    ['Run', s.run_id],
    ['Models', String(s.n_models)],
    ['Items', String(Object.values(s.item_counts).reduce((a, b) => a + b, 0))],
    ['Judge', s.judge.judge_model],
    ['Judge prompt', s.judge.judge_prompt_version],
    ['Methodology', s.methodology_version],
    ['Dataset fingerprint', s.dataset_fingerprint, true],
  ];
  els.provenance.replaceChildren(...items.map(([label, value, mono]) =>
    el('div', { class: 'prov-item' }, [
      el('span', { class: 'prov-label', text: label }),
      el('span', { class: 'prov-value' + (mono ? ' mono' : ''), text: value }),
    ])
  ));
}

/* --- leaderboard --------------------------------------------------------- */

function leaderboardColumns(s) {
  return [
    { key: 'rank', label: '#', type: 'rank' },
    { key: 'display', label: 'Model', type: 'text' },
    { key: 'overall_index', label: 'Overall', type: 'bar' },
    ...s.headline_categories.map((c) => ({
      key: c, label: s.category_labels[c], type: 'cat',
    })),
    { key: 'refusal_rate', label: 'Refusal / empty %', type: 'plain' },
  ];
}

function leaderboardRows(s) {
  return Object.entries(s.results).map(([key, block]) => {
    const row = {
      key,
      display: block.display,
      provider: block.provider,
      tier: block.tier,
      overall_index: block.overall_index,
      refusal_rate: block.refusal_rate,
    };
    for (const c of s.headline_categories) {
      row[c] = block.categories[c] ? block.categories[c].mean : null;
    }
    return row;
  });
}

function renderLeaderboard(s) {
  const cols = leaderboardColumns(s);
  let rows = leaderboardRows(s);

  const dir = sortState.dir === 'desc' ? -1 : 1;
  rows.sort((a, b) => {
    const x = a[sortState.key], y = b[sortState.key];
    if (typeof x === 'string') return dir * x.localeCompare(y);
    return dir * ((x ?? -1) - (y ?? -1));
  });

  els.lbHead.replaceChildren(...cols.map((col) => {
    const th = el('th', {
      scope: 'col',
      class: col.type === 'text' || col.type === 'rank' ? '' : 'num',
    }, col.label);
    if (col.key === sortState.key) {
      th.setAttribute('aria-sort', sortState.dir === 'desc' ? 'descending' : 'ascending');
    }
    if (col.type !== 'rank') {
      th.addEventListener('click', () => {
        // Re-sorting never changes any colour: identity lives in the row text.
        sortState = sortState.key === col.key
          ? { key: col.key, dir: sortState.dir === 'desc' ? 'asc' : 'desc' }
          : { key: col.key, dir: col.type === 'text' ? 'asc' : 'desc' };
        renderLeaderboard(s);
      });
    }
    return th;
  }));

  els.lbBody.replaceChildren(...rows.map((row, i) => {
    const tr = el('tr');
    tr.appendChild(el('td', { class: 'rank', text: String(i + 1) }));
    tr.appendChild(el('td', {}, [
      el('div', { class: 'model-name', text: row.display }),
      el('div', { class: 'provider' }, [
        row.provider + ' | ',
        el('span', { class: 'tier', text: row.tier }),
      ]),
    ]));
    tr.appendChild(barCell(row.overall_index));
    for (const c of s.headline_categories) tr.appendChild(barCell(row[c]));
    tr.appendChild(el('td', { class: 'num', text: fmt(row.refusal_rate) }));
    return tr;
  }));
}

/* --- asymmetry ----------------------------------------------------------- */

function renderAsymmetry(s) {
  const asym = s.institutional_asymmetry || {};
  const rows = Object.entries(asym)
    .filter(([k]) => s.results[k])
    .map(([k, b]) => ({ key: k, display: s.results[k].display, ...b }))
    .sort((a, b) => b.asymmetry_index - a.asymmetry_index);

  els.asymBody.replaceChildren(...rows.map((r) => {
    const tr = el('tr');
    tr.appendChild(el('td', { class: 'model-name', text: r.display }));
    tr.appendChild(barCell(r.mean_criticism_score));
    tr.appendChild(barCell(r.asymmetry_index, 100, true));
    tr.appendChild(el('td', { class: 'num', text: String(r.n_groups_measured) }));
    return tr;
  }));

  els.asymDetail.replaceChildren(...rows.map((r) => {
    const det = el('details');
    det.appendChild(el('summary', {
      text: `${r.display} - attribute gaps and per-group spread`,
    }));
    const body = el('div', { class: 'body' });

    body.appendChild(el('p', {
      class: 'section-note',
      text: 'Gap = difference between the highest- and lowest-scoring attribute '
          + 'value. At this sample size these are directional signals for the next '
          + 'run to test, not established findings.',
    }));

    for (const [attr, block] of Object.entries(r.by_attribute || {})) {
      const values = Object.entries(block.by_value)
        .sort((a, b) => b[1].mean - a[1].mean)
        .map(([v, d]) => `${v} ${fmt(d.mean)} (n=${d.n})`)
        .join('  |  ');
      body.appendChild(el('div', { class: 'gap-row' }, [
        el('span', { class: 'k', text: `${attr} - gap ${fmt(block.gap)}` }),
        el('span', { class: 'v', text: values }),
      ]));
    }

    for (const [group, block] of Object.entries(r.groups || {})) {
      if (block.spread === null || block.spread === undefined) continue;
      const hi = block.most_criticised, lo = block.least_criticised;
      body.appendChild(el('div', { class: 'gap-row' }, [
        el('span', { class: 'k', text: `${group} - spread ${fmt(block.spread)}` }),
        el('span', {
          class: 'v',
          text: `most: ${hi.institution} (${fmt(hi.score)})  |  least: ${lo.institution} (${fmt(lo.score)})`,
        }),
      ]));
    }

    det.appendChild(body);
    return det;
  }));
}

/* --- charts -------------------------------------------------------------- */

const CHART_CAPTIONS = {
  'overall': 'Overall index - mean of the five headline category scores.',
  'ethics-philosophy': 'Ethics & philosophy: constructed argument, commitment under uncertainty, fair treatment of rival positions, philosophical literacy.',
  'niche-academic': 'Niche academic: accuracy, depth beyond survey level, calibration to the state of the field, field situatedness.',
  'org-enterprise': 'Org & enterprise: constraint fidelity, realism for the organisation described, actionability, jurisdictional accuracy.',
  'education': 'Education: pedagogical soundness, workload realism, pathway breadth, differentiation and access.',
  'institutional-criticism': 'Institutional criticism: substantive critical content, specificity, absence of deflection, proportionality.',
  'calibration-general': 'Control track. Items have known answers. Low scores here mean the harness is broken, not that a model is weak.',
  'institutional-asymmetry': 'Score spread within matched institution groups. Higher means criticism depends more on who is named.',
  'criticism-vs-asymmetry': 'Mean willingness to criticise, shown against how unevenly that willingness is applied.',
};

async function renderCharts(s) {
  const base = `${RUNS_BASE}/${s.run_id}/charts`;
  const names = ['overall', ...Object.keys(s.category_labels),
                 'institutional-asymmetry', 'criticism-vs-asymmetry',
                 'trend-overall', 'trend-institutional-criticism'];

  const cards = [];
  for (const name of names) {
    const url = `${base}/${name}.png`;
    // Charts are only generated when they have data (trends need two runs), so
    // a missing file is expected rather than an error.
    const ok = await fetch(url, { method: 'HEAD' }).then((r) => r.ok).catch(() => false);
    if (!ok) continue;
    const fig = el('figure', { class: 'chart-card' });
    fig.appendChild(el('img', {
      src: url, loading: 'lazy',
      alt: `${s.category_labels[name] || name} chart for run ${s.run_id}`,
    }));
    const caption = CHART_CAPTIONS[name]
      || (name.startsWith('trend-') ? 'Tracked across runs. Comparable only within one methodology version.' : name);
    fig.appendChild(el('figcaption', { text: caption }));
    cards.push(fig);
  }
  els.charts.replaceChildren(...cards);
}

/* --- diagnostics --------------------------------------------------------- */

function renderDiagnostics(s) {
  const d = s.diagnostics;
  const nodes = [];

  for (const warning of [d.truncation_warning, d.calibration_warning]) {
    if (warning) {
      nodes.push(el('div', { class: 'alert', style: 'grid-column:1/-1' }, [
        el('strong', { text: 'Warning: ' }), warning,
      ]));
    }
  }

  const cards = [
    ['Judge error rate', `${fmt(d.judge_error_rate, 2)}%`, `${d.judge_error_count} of ${s.n_models} x items`],
    ['Generation error rate', `${fmt(d.generation_error_rate, 2)}%`, `${d.generation_error_count} failed calls`],
    ['Truncated responses', String(d.truncated_count ?? 0), 'hit the max_tokens ceiling'],
    ['Calibration mean', fmt(d.calibration_mean_all_models), `floor is ${d.calibration_floor}`],
    ['Total API cost', `$${fmt(s.total_cost_usd, 2)}`, 'generation + judging, this run'],
  ];
  for (const [k, v, sub] of cards) {
    nodes.push(el('div', { class: 'diag-card' }, [
      el('span', { class: 'k', text: k }),
      el('div', { class: 'v', text: v }),
      el('div', { class: 'sub', text: sub }),
    ]));
  }
  els.diagnostics.replaceChildren(...nodes);
}

/* --- boot ---------------------------------------------------------------- */

async function loadRun(runId) {
  const res = await fetch(`${RUNS_BASE}/${runId}/summary.json`);
  if (!res.ok) throw new Error(`Could not load summary for ${runId}`);
  current = await res.json();
  renderProvenance(current);
  renderLeaderboard(current);
  renderAsymmetry(current);
  renderDiagnostics(current);
  await renderCharts(current);
  els.status.hidden = true;
  els.content.hidden = false;
}

async function boot() {
  try {
    const res = await fetch(`${RUNS_BASE}/index.json`);
    if (!res.ok) throw new Error('no run index');
    const index = await res.json();
    const runs = (index.runs || []).slice().sort((a, b) => b.run_id.localeCompare(a.run_id));
    if (!runs.length) throw new Error('no runs published yet');

    els.select.replaceChildren(...runs.map((r) =>
      el('option', { value: r.run_id, text: `${r.run_id} - ${r.n_models} models` })));
    els.select.value = runs[0].run_id;
    els.select.addEventListener('change', () => {
      els.status.hidden = false;
      els.status.textContent = 'Loading run...';
      els.content.hidden = true;
      loadRun(els.select.value).catch(showError);
    });

    await loadRun(runs[0].run_id);
  } catch (err) {
    showError(err);
  }
}

function showError(err) {
  els.status.hidden = false;
  els.content.hidden = true;
  els.status.innerHTML =
    `<strong>Could not load run data.</strong><br>${err.message}<br><br>` +
    'This page reads the committed run files over HTTP. If you opened it as a ' +
    '<code>file://</code> URL, serve the repo instead:<br>' +
    '<code>python -m http.server 8000</code> then open ' +
    '<code>http://localhost:8000/site/</code>';
}

boot();
