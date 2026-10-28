/* Who Showed Up? — client.
 * All statistics come from analysis/engine.py: over HTTP when run locally
 * (server.py), or on the static GitHub Pages build from precomputed.json,
 * falling back to the same Python code running in the browser (worker.js).
 */
"use strict";

// ───────────────────────── utilities ─────────────────────────
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmt = (x, d = 1) => (x === null || x === undefined || Number.isNaN(x) ? "n/a" : Number(x).toFixed(d));
const fmtP = (p) => (p === null || p === undefined ? "n/a" : p < 0.001 ? "< 0.001" : Number(p).toFixed(3));
const signed = (x, d = 2) => (x === null || x === undefined ? "n/a" : (x > 0 ? "+" : "") + Number(x).toFixed(d));
const fmtInt = (x) => (x === null || x === undefined ? "n/a" : Math.round(x).toLocaleString());
const fmtM = (x) => (x / 1e6).toFixed(1) + "M";
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("on");
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("on"), 2400);
}

// Plain-language tooltips for stats words
const TERMS = {
  r: "Correlation (r): how tightly two things move together, from −1 (perfectly opposite) through 0 (no link) to +1 (perfectly together).",
  p: "p-value: if there were truly no link, how often would we see a pattern at least this strong by luck? Below 0.05 (5%) is the usual ‘probably not luck’ bar.",
  ci: "95% range (confidence interval): the range of values that fit the data. Narrow = precise, wide = uncertain.",
  q: "Adjusted p-value (q): a p-value made stricter because we checked many things at once. More checks means more chances to get lucky.",
  control: "Controlling for X: comparing states that are similar on X, to see whether a link survives once X is taken into account.",
  vep: "VEP = voting-eligible population: adults who are legally allowed to vote (citizens, not barred by a felony conviction), plus Americans living abroad.",
  vap: "VAP = voting-age population: everyone aged 18+ living in the state, including people who aren't allowed to vote.",
};
const term = (k, text) => `<span class="term" tabindex="0" data-tip="${esc(TERMS[k])}">${text}</span>`;

// ───────────────────────── mascots (original artwork) ─────────────────────────
const INK = "#3b3355";
function mouth(mood, dy = 0) {
  const y = 66 + dy;
  return {
    happy: `<path d="M44 ${y - 2} q6 7 12 0" stroke="${INK}" stroke-width="3" fill="none" stroke-linecap="round"/>`,
    surprised: `<ellipse cx="50" cy="${y}" rx="3.6" ry="4.6" fill="${INK}"/>`,
    thinking: `<path d="M45 ${y} q5 -3 10 1" stroke="${INK}" stroke-width="3" fill="none" stroke-linecap="round"/><circle cx="84" cy="22" r="3" fill="${INK}" opacity=".35"/><circle cx="91" cy="13" r="4.5" fill="${INK}" opacity=".35"/>`,
    shrug: `<path d="M45 ${y} h10" stroke="${INK}" stroke-width="3" stroke-linecap="round"/><text x="80" y="30" font-family="Baloo 2, sans-serif" font-weight="800" font-size="20" fill="${INK}" opacity=".5">?</text>`,
    wobbly: `<path d="M42 ${y} l4 -3 l4 3 l4 -3 l4 3" stroke="${INK}" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/><path d="M80 38 q5 7 0 10 q-5 -3 0 -10z" fill="#a9cbf5" stroke="${INK}" stroke-width="1.5"/>`,
  }[mood] || "";
}
const eyes = (y = 56) => `<ellipse cx="38" cy="${y}" rx="3.8" ry="4.6" fill="${INK}"/><ellipse cx="62" cy="${y}" rx="3.8" ry="4.6" fill="${INK}"/><circle cx="39.3" cy="${y - 1.6}" r="1.3" fill="#fff"/><circle cx="63.3" cy="${y - 1.6}" r="1.3" fill="#fff"/>`;
const cheeks = (y = 64) => `<ellipse cx="28" cy="${y}" rx="6.5" ry="3.8" fill="#f7a8b4" opacity=".85"/><ellipse cx="72" cy="${y}" rx="6.5" ry="3.8" fill="#f7a8b4" opacity=".85"/>`;
function mascot(kind = "ballo", mood = "happy", size = 80) {
  let body;
  if (kind === "ballo") {
    // Ballo: a little ballot box with a ballot peeking out
    body = `<g transform="rotate(-9 50 18)"><rect x="37" y="2" width="27" height="30" rx="4" fill="#fff" stroke="${INK}" stroke-width="2.6"/>
        <path d="M43.5 17 l5 5 l9 -11" stroke="#4f8bdb" stroke-width="3.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g>
      <ellipse cx="34" cy="90" rx="9" ry="4.5" fill="${INK}"/><ellipse cx="66" cy="90" rx="9" ry="4.5" fill="${INK}"/>
      <rect x="13" y="26" width="74" height="62" rx="22" fill="#fffdf8" stroke="${INK}" stroke-width="3"/>
      <rect x="31" y="27.5" width="38" height="5.5" rx="2.75" fill="${INK}"/>
      <path d="M22 80 q28 8 56 0" stroke="#f7b2b7" stroke-width="5" fill="none" stroke-linecap="round" opacity=".9"/>
      <path d="M22 74 q28 8 56 0" stroke="#a9cbf5" stroke-width="5" fill="none" stroke-linecap="round" opacity=".9"/>
      ${eyes()}${cheeks()}${mouth(mood)}`;
  } else {
    // Bloo (blue) and Rosie (red): round mochi friends
    const fill = kind === "bloo" ? "#a9cbf5" : "#f7b2b7";
    const extra = kind === "bloo"
      ? `<circle cx="80" cy="70" r="9" fill="#fff" stroke="${INK}" stroke-width="2"/><path d="M75.5 70 l3 3 l6 -6" stroke="#e0606c" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`
      : `<path d="M50 30 q-7 -11 0 -16 q7 5 0 16z" fill="#3faf84" stroke="${INK}" stroke-width="2"/>`;
    body = `<path d="M12 72 C12 30 88 30 88 72 C88 90 12 90 12 72Z" fill="${fill}" stroke="${INK}" stroke-width="3"/>
      <ellipse cx="13" cy="70" rx="5" ry="7" fill="${fill}" stroke="${INK}" stroke-width="2.5"/><ellipse cx="87" cy="70" rx="5" ry="7" fill="${fill}" stroke="${INK}" stroke-width="2.5"/>
      ${eyes(60)}${cheeks(68)}${mouth(mood, 4)}${extra}`;
  }
  return `<svg width="${size}" height="${size}" viewBox="0 0 100 100" role="img" aria-label="${kind} mascot">${body}</svg>`;
}
function hydrateMascots(root = document) {
  $$(".mascot-slot[data-mascot]", root).forEach((el) => { const [k, m, s] = el.dataset.mascot.split(":"); el.innerHTML = mascot(k, m, +s); });
}

// ───────────────────────── data layer ─────────────────────────
const STATIC = !!window.TURNOUT_STATIC;
let PRE = null, worker = null, wseq = 0;
const waiting = new Map();
function cleanPayload(o) { const c = {}; Object.keys(o).sort().forEach((k) => { const v = o[k]; if (v !== undefined && v !== null && v !== "") c[k] = v; }); return c; }
const reqKey = (path, payload) => path + "|" + JSON.stringify(cleanPayload(payload)); // mirrors api.request_key
async function loadPre() { if (!PRE) PRE = await (await fetch("precomputed.json")).json(); }
function busy(on, msg) { $("#busy").hidden = !on; if (msg) $("#busy-msg").textContent = msg; }
function callWorker(method, path, payload) {
  if (!worker) {
    worker = new Worker("worker.js");
    busy(true, "Waking up Ballo's calculator in your browser… (first time takes ~20 seconds)");
    worker.onmessage = (e) => {
      const m = e.data;
      if ("ready" in m) { if (!m.ready) toast("Couldn't start the in-browser calculator: " + m.error); renderGlobalBar(); return; }
      const w = waiting.get(m.id); waiting.delete(m.id);
      if (!waiting.size) busy(false);
      m.ok ? w.res(m.data) : w.rej(new Error(m.error));
    };
  } else busy(true, "Crunching numbers…");
  return new Promise((res, rej) => { const id = ++wseq; waiting.set(id, { res, rej }); worker.postMessage({ id, method, path, payload: cleanPayload(payload) }); });
}
const api = {
  async get(path, params = {}) {
    if (STATIC) { await loadPre(); const k = reqKey(path, params); return k in PRE ? PRE[k] : callWorker("GET", path, params); }
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== ""));
    const r = await fetch(path + (q.toString() ? "?" + q : ""));
    const j = await r.json(); if (!r.ok) throw new Error(j.error || r.statusText); return j;
  },
  async post(path, body) {
    if (STATIC) { await loadPre(); const k = reqKey(path, body); return k in PRE ? PRE[k] : callWorker("POST", path, body); }
    const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const j = await r.json(); if (!r.ok) throw new Error(j.error || r.statusText); return j;
  },
};

// ───────────────────────── state ─────────────────────────
const S = {
  outcome: "turnout_rate_vep",
  exclude: new Set(), selected: new Set(), focus: null,
  data: [], meta: null, overview: null, findings: [],
  ex: { x: "prison_pct_vap", y: null, color: "region", mapVar: null, histVar: null, grpVar: "region", rankVar: null, heat: "spearman", sortKey: null, sortDir: -1 },
  inv: { id: null, history: [] },
  tab: "overview",
};
const exParam = () => [...S.exclude].join(",");
const FRIENDLY = {
  turnout_rate_vep: "Turnout % (of eligible voters)", turnout_rate_vap: "Turnout % (of all adults)", pct_noncitizen: "Non-citizens (% of adults)",
  vep_vap_gap_pct: "Adults who can't vote (%)", prison_pct_vap: "In prison (% of adults)", community_inelig_pct_vap: "Barred on probation/parole (% of adults)",
  felon_inelig_pct_vap: "Barred by felony, total (% of adults)", log10_vep: "State size (log scale)", vep: "Eligible voters", is_south: "Southern state",
  alt_num: "Counts top race only (*)", region: "Region", felony_regime: "Felony voting rules", status_group: "Result status", alt_numerator: "Counting method",
};
const label = (v) => FRIENDLY[v] || S.meta?.vars[v]?.label || S.meta?.groups[v]?.label || v;
const active = () => S.data.filter((d) => !d.excluded);

const REGIONS = ["Midwest", "Northeast", "South", "West"];
const SYMBOLS = ["circle", "square", "diamond", "triangle-up", "x", "star"];
const VERDICT_CLASS = { "Robust association": "good", "Measurement artifact": "warn", "Likely confounded": "warn", "Fragile": "bad", "Measurement caveat": "warn", "No association": "meh", "Model ceiling": "meh", "Re-check": "bad" };

function theme() {
  return {
    paper: css("--surface"), ink: css("--ink"), ink2: css("--ink-2"), muted: css("--muted"), grid: css("--grid"), axis: css("--axis"),
    blue: css("--blue-deep"), red: css("--red-deep"), blueSoft: css("--blue"), redSoft: css("--red"),
    series: [css("--s1"), css("--s2"), css("--s3"), css("--s4")],
    divNeg: css("--div-neg"), divMid: css("--div-mid"), divPos: css("--div-pos"), seqLo: css("--seq-lo"), seqHi: css("--seq-hi"),
  };
}
function groupValues(key) { return key === "region" ? REGIONS : [...new Set(S.data.map((d) => String(d[key])))].sort(); }
function groupLabel(key, v) { return key === "alt_numerator" ? (v === "true" ? "Top race only (*)" : "All ballots") : v; }
const colorFor = (key, v) => theme().series[groupValues(key).indexOf(String(v)) % 4];
const symbolFor = (key, v) => SYMBOLS[groupValues(key).indexOf(String(v)) % SYMBOLS.length];
const hexA = (hex, a) => { const h = hex.replace("#", ""); return h.length !== 6 ? hex : `rgba(${parseInt(h.slice(0, 2), 16)},${parseInt(h.slice(2, 4), 16)},${parseInt(h.slice(4, 6), 16)},${a})`; };

function layout(extra = {}) {
  const T = theme();
  const ax = { gridcolor: T.grid, linecolor: T.axis, zerolinecolor: T.axis, tickfont: { color: T.ink2, size: 11 }, title: { font: { color: T.ink2, size: 12.5 } }, automargin: true };
  return Object.assign({
    paper_bgcolor: T.paper, plot_bgcolor: T.paper, font: { family: "Nunito, system-ui, sans-serif", color: T.ink, size: 12.5 },
    margin: { l: 52, r: 16, t: 10, b: 46 }, barcornerradius: 7,
    hoverlabel: { bgcolor: T.paper, bordercolor: T.axis, font: { color: T.ink, size: 13, family: "Nunito, sans-serif" } },
    legend: { orientation: "h", y: 1.1, x: 0, font: { size: 12, color: T.ink2 } },
    xaxis: { ...ax, ...(extra.xaxis || {}) }, yaxis: { ...ax, ...(extra.yaxis || {}) },
  }, Object.fromEntries(Object.entries(extra).filter(([k]) => k !== "xaxis" && k !== "yaxis")));
}
const CFG = { displaylogo: false, responsive: true, modeBarButtonsToRemove: ["autoScale2d", "toggleSpikelines", "hoverCompareCartesian", "select2d"] };

// ───────────────────────── state changes ─────────────────────────
function setSelected(arr, { focus } = {}) {
  S.selected = new Set(arr);
  if (focus !== undefined) S.focus = focus;
  renderGlobalBar();
  if (S.tab === "explore") { drawExploreCharts(); renderSelectionPanel(); renderProfile(); }
}
function toggleSelect(abv, additive) {
  let s;
  if (additive) { s = new Set(S.selected); s.has(abv) ? s.delete(abv) : s.add(abv); }
  else s = S.selected.size === 1 && S.selected.has(abv) ? new Set() : new Set([abv]);
  setSelected([...s], { focus: abv });
}
async function setExclude(set) {
  S.exclude = new Set(set);
  for (const a of S.exclude) S.selected.delete(a);
  try { S.data = await api.get("/api/data", { exclude: exParam() }); } catch (e) { toast(e.message); return; }
  renderGlobalBar();
  if (S.tab === "explore") renderExplore();
  if (S.tab === "investigate" && S.inv.id) renderInvestigation(S.inv.id);
  toast(S.exclude.size ? `Leaving out ${[...S.exclude].join(", ")} from every calculation` : "All 51 back in ♡");
}
function setOutcome(o) {
  S.outcome = o;
  for (const k of ["y", "mapVar", "histVar", "rankVar"]) if (!S.ex[k] || S.meta.outcomes.includes(S.ex[k])) S.ex[k] = o;
  for (const [id, k] of [["#map-var", "mapVar"], ["#hist-var", "histVar"], ["#rank-var", "rankVar"], ["#sc-y", "y"]]) if ($(id).options.length) $(id).value = S.ex[k];
  renderGlobalBar();
  if (S.tab === "explore") renderExplore();
}

function renderGlobalBar() {
  const el = $("#globalbar");
  const sel = [...S.selected].sort(), ex = [...S.exclude].sort();
  el.innerHTML = `
    <div class="grp"><span class="lbl">Count turnout out of</span>
      <span class="seg"><button data-o="turnout_rate_vep" class="vep ${S.outcome === "turnout_rate_vep" ? "on" : ""}" title="${esc(TERMS.vep)}">people who can vote (VEP)</button><button data-o="turnout_rate_vap" class="vap ${S.outcome === "turnout_rate_vap" ? "on" : ""}" title="${esc(TERMS.vap)}">all adults (VAP)</button></span></div>
    <div class="grp"><span class="lbl">Picked</span>
      ${sel.length ? sel.map((a) => `<span class="chip sel" data-unsel="${a}" title="Unpick">${a} ×</span>`).join("") : '<span class="muted">none yet</span>'}
      ${sel.length ? `<button class="btn sm" id="gb-clear">Clear</button><button class="btn sm" id="gb-exsel" title="Leave the picked states out of every calculation">Hide picked</button>` : ""}</div>
    <div class="grp"><span class="lbl">Hidden</span>
      ${ex.length ? ex.map((a) => `<span class="chip ex" data-unex="${a}" title="Bring back">${a} ↺</span>`).join("") : '<span class="muted">none · all 51</span>'}
      ${ex.length ? `<button class="btn sm" id="gb-reset">Show all</button>` : ""}
      <button class="btn sm" id="gb-exdc" title="DC is a single city, so it's often unusual">${S.exclude.has("DC") ? "Show DC" : "Hide DC"}</button></div>
    ${STATIC && worker ? `<span class="engine">🧮 in-browser calculator on</span>` : ""}`;
  $$("[data-o]", el).forEach((b) => (b.onclick = () => setOutcome(b.dataset.o)));
  $$("[data-unsel]", el).forEach((b) => (b.onclick = () => { S.selected.delete(b.dataset.unsel); setSelected([...S.selected]); }));
  $$("[data-unex]", el).forEach((b) => (b.onclick = () => { const s = new Set(S.exclude); s.delete(b.dataset.unex); setExclude(s); }));
  $("#gb-clear") && ($("#gb-clear").onclick = () => setSelected([]));
  $("#gb-exsel") && ($("#gb-exsel").onclick = () => setExclude(new Set([...S.exclude, ...S.selected])));
  $("#gb-reset") && ($("#gb-reset").onclick = () => setExclude(new Set()));
  $("#gb-exdc").onclick = () => { const s = new Set(S.exclude); s.has("DC") ? s.delete("DC") : s.add("DC"); setExclude(s); };
}

function showTab(name) {
  S.tab = name;
  $$(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $$(".tab").forEach((t) => t.classList.toggle("active", t.id === "tab-" + name));
  if (name === "overview") renderOverview();
  if (name === "explore") renderExplore();
  if (name === "discover") renderFeed();
  if (name === "investigate") { renderInvList(); renderInvestigation(S.inv.id || S.findings[0].id); }
  if (name === "ask") renderAsk();
  window.scrollTo({ top: 0 });
}

const verdictBadge = (f) => `<span class="badge ${VERDICT_CLASS[f.verdict] || "meh"}" title="Technical label: ${esc(f.verdict)}">${esc(f.verdict_plain || f.verdict)}</span>`;
const nameOf = (abv) => S.data.find((d) => d.abv === abv)?.state || abv;

// ───────────────────────── overview ─────────────────────────
function renderOverview() {
  const O = S.overview, N = O.national, t = O.desc.turnout_rate_vep;
  const eligibleResidents = N.vap - N.noncitizen - N.ineligible_felon;
  $("#tab-overview").innerHTML = `
    <div class="bubble-row">
      <span class="mascot-slot wiggle" data-mascot="ballo:happy:110"></span>
      <div class="speech"><h2>Hi! I'm Ballo ♡</h2>
        <p>This site looks at <b>how many people voted</b> in each U.S. state in the November 2022 election, and tries to figure out <b>why some states vote more than others</b>. There are 51 places in the data: all 50 states plus Washington, DC.</p></div>
    </div>
    <div class="tiles">
      <div class="tile"><div class="k">Across the whole country</div><div class="v">${fmt(N.rate, 0)} in 100</div><div class="d">eligible people voted (${fmtM(N.turnout)} votes)</div></div>
      <div class="tile"><div class="k">Biggest gap between states</div><div class="v">${fmt(t.min, 0)}% → ${fmt(t.max, 0)}%</div><div class="d">${esc(nameOf(t.min_state))} lowest · ${esc(nameOf(t.max_state))} highest</div></div>
      <div class="tile"><div class="k">The typical state</div><div class="v">${fmt(t.median, 0)}%</div><div class="d">half the states were between ${fmt(t.q1, 0)}% and ${fmt(t.q3, 0)}%</div></div>
      <div class="tile"><div class="k">Adults who couldn't vote</div><div class="v">${fmtM(N.noncitizen + N.ineligible_felon)}</div><div class="d">mostly non-citizens</div></div>
    </div>

    <div class="grid g-1-1">
      <div class="card blue"><h3>🧮 First, what does “turnout” mean?</h3>
        <p>Turnout is just <b>votes ÷ people</b>. The tricky part is <i>which</i> people you divide by. This data gives two choices:</p>
        <div class="eq"><span class="pill red">VAP</span><span>= <b>all adults</b> (18+) living in the state</span></div>
        <div class="eq"><span class="pill blue">VEP</span><span>= only adults who are <b>legally allowed to vote</b></span></div>
        <p>VEP leaves out adults who <b>aren't citizens</b> and people <b>barred because of a felony conviction</b> (rules differ by state), and adds back Americans living abroad. This site uses <b>VEP</b> by default, because it only counts people who could have voted. You can switch anytime with the toggle at the top.</p>
        <div id="ov-vep" class="plot h-220"></div>
        <p class="hint">Nationally, ${fmtM(N.overseas)} Americans living abroad are also eligible. That's why national VEP (${fmtM(N.vep)}) isn't exactly the “can vote” bar above.</p>
      </div>
      <div class="card"><h3>📍 Turnout in every state</h3><div id="ov-strip" class="plot h-300"></div>
        <p class="hint">Each dot is a state, grouped by region. Hover to see which one, or click to explore it. Notice the Southern states sitting further left?</p></div>
    </div>

    <div class="card"><div class="card-head"><h3>✨ The headline discoveries</h3><button class="btn primary" id="ov-go">See all 8 →</button></div>
      <div id="ov-top" class="grid g-1-1" style="margin:8px 0 0"></div></div>

    <div class="card red"><h3>📚 Stats cheat sheet</h3>
      <p>You don't need to know statistics to use this site, but here's what the few technical words mean. Hover any <span class="term" tabindex="0" data-tip="Like this!">dotted word</span> for a reminder.</p>
      <div class="gloss">
        <div><b>Link / correlation (r)</b>Do two things rise and fall together? r runs from −1 (opposite) to +1 (together). Around 0 = no link. 0.3 is weak-ish, 0.5+ is strong for real-world data.</div>
        <div><b>“Probably not luck” (p-value)</b>With only 51 states, patterns can appear by chance. A p-value under 0.05 means a pattern this strong would show up by luck less than 5% of the time.</div>
        <div><b>Range (95% CI)</b>Our best guess comes with wiggle room. A range like “−11 to −4” means the true value is very likely somewhere in there.</div>
        <div><b>“Controlling for” something</b>Comparing like with like. If the South has both more prisoners and lower turnout, we check whether prisons still matter <i>within</i> similar states.</div>
        <div><b>Correlation ≠ causation</b>Two things moving together doesn't mean one causes the other. Something else might cause both!</div>
        <div><b>Robustness</b>If a finding survives lots of reasonable re-checks (dropping states, changing the measure), it's sturdy. If it vanishes, it's shaky.</div>
      </div>
    </div>

    <details class="card"><summary>🔧 For the curious: columns & data quality checks</summary>
      <div class="grid g-1-1" style="margin-top:10px">
        <div><table><thead><tr><th>Column</th><th>Meaning</th></tr></thead><tbody>
          ${O.columns.map(([c, m]) => `<tr><td><b>${esc(c)}</b></td><td>${esc(m)}</td></tr>`).join("")}</tbody></table></div>
        <div><ul class="clean">${O.quality.map((q) => `<li>${esc(q)}</li>`).join("")}</ul>
          <p class="small muted">Source footnote: ${esc(O.footnote)}</p></div>
      </div></details>`;
  hydrateMascots($("#tab-overview"));
  $("#ov-top").innerHTML = S.findings.slice(0, 4).map((f) => `
    <div class="result" style="margin:0"><div class="row">${verdictBadge(f)}</div><p class="p" style="margin:6px 0">${esc(f.title)}</p>
      <p class="small">${esc(f.plain)}</p><button class="btn sm blue" data-inv="${f.id}">Dig deeper →</button></div>`).join("");
  $$("[data-inv]", $("#ov-top")).forEach((b) => (b.onclick = () => { S.inv.id = b.dataset.inv; showTab("investigate"); }));
  $("#ov-go").onclick = () => showTab("discover");
  const T = theme();
  Plotly.react($("#ov-vep"), [
    { type: "bar", orientation: "h", y: [""], x: [eligibleResidents / 1e6], name: "Can vote", marker: { color: T.blueSoft, line: { color: T.blue, width: 2 } }, hovertemplate: "Can vote: %{x:.1f}M<extra></extra>", text: [`can vote: ${fmtM(eligibleResidents)}`], textposition: "inside", insidetextanchor: "middle", textfont: { color: "#1f2d4d", size: 13 } },
    { type: "bar", orientation: "h", y: [""], x: [N.noncitizen / 1e6], name: "Not citizens", marker: { color: T.redSoft, line: { color: T.red, width: 2 } }, hovertemplate: `Not citizens: ≈%{x:.1f}M (${fmt(N.pct_noncitizen)}% of adults)<extra></extra>` },
    { type: "bar", orientation: "h", y: [""], x: [N.ineligible_felon / 1e6], name: "Barred (felony)", marker: { color: T.ink2 }, hovertemplate: "Barred by felony conviction: %{x:.1f}M<extra></extra>" },
  ], layout({ barmode: "stack", showlegend: true, legend: { orientation: "h", y: -0.45 }, margin: { l: 8, r: 8, t: 4, b: 10 }, xaxis: { title: { text: `All ${fmtM(N.vap)} adults (millions)` }, showgrid: false }, yaxis: { showticklabels: false } }), CFG);
  drawStrip($("#ov-strip"), "turnout_rate_vep");
}

function drawStrip(el, v) {
  const T = theme();
  const traces = REGIONS.map((r, i) => {
    const d = active().filter((x) => x.region === r);
    return { type: "scatter", mode: "markers", name: r, x: d.map((x) => x[v]), y: d.map((x) => i + (hash(x.abv) - 0.5) * 0.5),
      text: d.map((x) => x.state), customdata: d.map((x) => x.abv), marker: { color: T.series[i], size: 12, symbol: SYMBOLS[i], line: { color: T.paper, width: 1.5 } },
      hovertemplate: `<b>%{text}</b><br>%{x:.1f}% voted<extra>${r}</extra>` };
  });
  Plotly.react(el, traces, layout({ showlegend: false, xaxis: { title: { text: label(v) } },
    yaxis: { tickvals: [0, 1, 2, 3], ticktext: REGIONS, gridcolor: "rgba(0,0,0,0)" }, margin: { l: 84, r: 10, t: 6, b: 42 } }), CFG);
  el.removeAllListeners?.("plotly_click");
  el.on("plotly_click", (ev) => { const a = ev.points[0].customdata; showTab("explore"); setSelected([a], { focus: a }); });
}
function hash(s) { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) % 997; return h / 997; }

// ───────────────────────── explore ─────────────────────────
let exploreInit = false;
function initExploreControls() {
  const numVars = [...S.meta.outcomes, ...S.meta.predictors.filter((p) => !["is_south", "alt_num"].includes(p)), "vep"];
  const opt = (vs, cur) => vs.map((v) => `<option value="${v}" ${v === cur ? "selected" : ""}>${esc(label(v))}</option>`).join("");
  S.ex.y = S.ex.y || S.outcome; S.ex.mapVar = S.ex.mapVar || S.outcome; S.ex.histVar = S.ex.histVar || S.outcome; S.ex.rankVar = S.ex.rankVar || S.outcome;
  $("#sc-x").innerHTML = opt(numVars, S.ex.x); $("#sc-y").innerHTML = opt(numVars, S.ex.y);
  $("#map-var").innerHTML = opt(numVars, S.ex.mapVar); $("#hist-var").innerHTML = opt(numVars, S.ex.histVar); $("#rank-var").innerHTML = opt(numVars, S.ex.rankVar);
  $("#grp-var").innerHTML = Object.keys(S.meta.groups).map((k) => `<option value="${k}" ${k === S.ex.grpVar ? "selected" : ""}>${esc(label(k))}</option>`).join("");
  if (exploreInit) return; exploreInit = true;
  $("#sc-x").onchange = (e) => { S.ex.x = e.target.value; drawScatter(); };
  $("#sc-y").onchange = (e) => { S.ex.y = e.target.value; drawScatter(); };
  $("#sc-color").onchange = (e) => { S.ex.color = e.target.value; drawScatter(); };
  $("#sc-ols").onchange = drawScatter; $("#sc-lowess").onchange = drawScatter;
  $("#map-var").onchange = (e) => { S.ex.mapVar = e.target.value; drawMap(); };
  $("#hist-var").onchange = (e) => { S.ex.histVar = e.target.value; drawHist(); };
  $("#grp-var").onchange = (e) => { S.ex.grpVar = e.target.value; drawGroup(); };
  $("#rank-var").onchange = (e) => { S.ex.rankVar = e.target.value; drawRank(); };
  $("#heat-method").onchange = (e) => { S.ex.heat = e.target.value; drawHeat(); };
}
function renderExplore() {
  initExploreControls();
  hydrateMascots($("#tab-explore"));
  drawExploreCharts(true); renderProfile(); renderSelectionPanel();
}
function drawExploreCharts(full = false) { drawMap(); drawScatter(); drawHist(); drawGroup(full); drawRank(); if (full) drawHeat(); drawTable(); }
const isSel = (a) => S.selected.has(a);
const hasSel = () => S.selected.size > 0;

function bindClick(el) {
  el.removeAllListeners?.("plotly_click");
  el.on("plotly_click", (ev) => {
    const p = ev.points[0]; const a = p.customdata ?? p.location; if (!a || typeof a !== "string") return;
    toggleSelect(a, ev.event?.shiftKey || ev.event?.ctrlKey || ev.event?.metaKey);
  });
}

function drawMap() {
  const el = $("#map"), v = S.ex.mapVar, T = theme(), d = active();
  const base = { type: "choropleth", locationmode: "USA-states", locations: d.map((x) => x.abv), z: d.map((x) => x[v]), customdata: d.map((x) => x.abv),
    text: d.map((x) => `${x.state}${x.alt_numerator ? " *" : ""}`), colorscale: [[0, T.seqLo], [1, T.seqHi]],
    marker: { line: { color: T.paper, width: 1.2 } }, colorbar: { thickness: 12, len: 0.7, tickfont: { color: T.ink2, size: 11 }, outlinewidth: 0 },
    hovertemplate: `<b>%{text}</b><br>${esc(label(v))}: %{z:,.1f}<extra></extra>` };
  const s = d.filter((x) => isSel(x.abv));
  const hi = { type: "choropleth", locationmode: "USA-states", locations: s.map((x) => x.abv), z: s.map(() => 1), showscale: false,
    colorscale: [[0, hexA(T.red, 0.3)], [1, hexA(T.red, 0.3)]], marker: { line: { color: T.red, width: 3 } }, hoverinfo: "skip" };
  Plotly.react(el, [base, hi], layout({ margin: { l: 0, r: 0, t: 0, b: 0 }, geo: { scope: "usa", bgcolor: T.paper, lakecolor: T.paper, showlakes: false, subunitcolor: T.paper } }), CFG);
  bindClick(el);
}

let scSeq = 0;
async function drawScatter() {
  const el = $("#scatter"), x = S.ex.x, y = S.ex.y || S.outcome, key = S.ex.color, T = theme(), d = active();
  const seq = ++scSeq;
  const traces = groupValues(key).map((g) => {
    const pts = d.filter((r) => String(r[key]) === g);
    return { type: "scatter", mode: "markers+text", name: groupLabel(key, g), x: pts.map((r) => r[x]), y: pts.map((r) => r[y]), customdata: pts.map((r) => r.abv),
      text: pts.map((r) => (isSel(r.abv) || r.abv === S.focus ? r.abv : "")), textposition: "top center", textfont: { size: 12, color: T.ink },
      hovertext: pts.map((r) => `<b>${r.state}</b>${r.alt_numerator ? " *" : ""}<br>${label(x)}: ${fmt(r[x], 2)}<br>${label(y)}: ${fmt(r[y], 1)}`), hoverinfo: "text",
      marker: { size: pts.map((r) => (isSel(r.abv) ? 16 : 12)), color: colorFor(key, g), symbol: symbolFor(key, g),
        opacity: pts.map((r) => (!hasSel() || isSel(r.abv) ? 0.95 : 0.3)), line: { color: pts.map((r) => (isSel(r.abv) ? T.red : T.paper)), width: pts.map((r) => (isSel(r.abv) ? 3 : 1.5)) } },
      cliponaxis: false };
  });
  const L = layout({ dragmode: "lasso", xaxis: { title: { text: label(x) } }, yaxis: { title: { text: label(y) } } });
  Plotly.react(el, traces, L, CFG);
  el.removeAllListeners?.("plotly_selected"); el.removeAllListeners?.("plotly_deselect");
  el.on("plotly_selected", (ev) => { if (ev && ev.points) setSelected(ev.points.map((p) => p.customdata)); });
  el.on("plotly_deselect", () => setSelected([]));
  bindClick(el);
  $("#sc-stats").innerHTML = `<h3>What it means</h3><p class="loading">Calculating…</p>`;
  try {
    const c = await api.get("/api/correlate", { x, y, exclude: exParam() });
    if (seq !== scSeq) return;
    const extra = [];
    if ($("#sc-ols").checked) {
      extra.push({ type: "scatter", mode: "lines", x: [...c.fit.x, ...c.fit.x.slice().reverse()], y: [...c.fit.hi, ...c.fit.lo.slice().reverse()], fill: "toself", fillcolor: hexA(T.blue, 0.12), line: { width: 0 }, hoverinfo: "skip", showlegend: false });
      extra.push({ type: "scatter", mode: "lines", x: c.fit.x, y: c.fit.y, line: { color: T.blue, width: 3 }, name: "trend", hoverinfo: "skip" });
    }
    if ($("#sc-lowess").checked && c.lowess) extra.push({ type: "scatter", mode: "lines", x: c.lowess.x, y: c.lowess.y, line: { color: T.red, width: 3, dash: "dot" }, name: "wiggly trend", hoverinfo: "skip" });
    Plotly.react(el, [...extra, ...traces], L, CFG);
    $("#sc-stats").innerHTML = corrStatsHTML(c);
    $("#sc-ask").onclick = () => { showTab("ask"); askQuestion(`Does ${label(S.ex.x).toLowerCase()} still matter after adjusting for other things?`); };
  } catch (e) { $("#sc-stats").innerHTML = `<h3>What it means</h3><p class="err">${esc(e.message)}</p>`; }
}
function meter(r) {
  const a = Math.min(1, Math.abs(r)), T = theme();
  return `<div style="height:12px;border-radius:999px;background:var(--grid);position:relative;margin:6px 0 2px"><div style="position:absolute;left:0;top:0;bottom:0;width:${a * 100}%;border-radius:999px;background:${r < 0 ? T.blue : T.red}"></div></div>
    <div class="row small muted" style="justify-content:space-between"><span>no link</span><span>weak</span><span>moderate</span><span>strong</span></div>`;
}
function corrStatsHTML(c) {
  const top = Object.entries(c.cooks).sort((a, b) => b[1] - a[1]).slice(0, 3);
  return `<div class="row"><span class="mascot-slot">${mascot(Math.abs(c.r) < 0.1 ? "bloo" : "ballo", c.p < 0.05 ? "happy" : "shrug", 54)}</span><h3>What it means</h3></div>
    <p class="bigplain">${esc(c.plain)}</p>
    <div class="small"><b>How strong is the link?</b> ${meter(c.r)}</div>
    <p class="small muted">Based on ${c.n} states${S.exclude.size ? ` (hiding ${[...S.exclude].join(", ")})` : ""}.</p>
    <details><summary>Show the numbers 🤓</summary>
    <div class="statgrid">
      <div><span>${term("r", "Correlation r")}</span><b>${signed(c.r)}</b><span>${term("ci", "95% range")} ${signed(c.r_ci[0])} to ${signed(c.r_ci[1])}</span></div>
      <div><span>${term("p", "p-value")}</span><b>${fmtP(c.p)}</b><span>${c.p < 0.05 ? "probably not luck" : "could be luck"}</span></div>
      <div><span>Rank-based version (ρ)</span><b>${signed(c.rho)}</b><span>p ${fmtP(c.p_spearman)}; less swayed by extreme states</span></div>
      <div><span>Trend line slope</span><b>${signed(c.slope, 2)}</b><span>change in “up” per 1 unit “across”</span></div>
      <div><span>Bootstrap 95% range (r)</span><b>${signed(c.boot_r_ci[0])} to ${signed(c.boot_r_ci[1])}</b><span>from 2,000 resamples</span></div>
      <div><span>Drop any one state</span><b>r from ${signed(c.loo_r_min)} to ${signed(c.loo_r_max)}</b><span>biggest swing: ${c.loo_most_influential}</span></div>
      ${c.quad_p !== undefined ? `<div><span>Is it curved?</span><b>p ${fmtP(c.quad_p)}</b><span>${c.quad_p < 0.05 ? "some curve" : "no sign of a curve"}</span></div>` : ""}
      <div><span>Most influential states</span><b>${top.map(([a]) => a).join(" · ")}</b><span>Cook's distance</span></div>
    </div>
    <p class="hint">Checking lots of pairs here means some will look “significant” by luck. The “What goes with what?” grid adjusts for that.</p></details>
    <p><button class="btn sm blue" id="sc-ask">Does this still hold up? Ask Ballo →</button></p>`;
}

function drawHist() {
  const el = $("#hist"), v = S.ex.histVar, T = theme(), d = active();
  const vals = d.map((r) => r[v]);
  Plotly.react(el, [
    { type: "histogram", x: vals, nbinsx: 14, marker: { color: T.blueSoft, line: { color: T.blue, width: 2 } }, hovertemplate: "%{x}: %{y} states<extra></extra>", yaxis: "y" },
    { type: "scatter", mode: "markers", x: vals, y: d.map((r) => (hash(r.abv) - 0.5) * 0.6), yaxis: "y2", customdata: d.map((r) => r.abv), text: d.map((r) => r.state),
      marker: { size: d.map((r) => (isSel(r.abv) ? 13 : 8)), color: d.map((r) => (isSel(r.abv) ? T.red : hexA(T.ink2, hasSel() ? 0.25 : 0.55))) }, hovertemplate: "%{text}: %{x:.2f}<extra></extra>" },
  ], layout({ showlegend: false, bargap: 0.08, xaxis: { title: { text: label(v) }, anchor: "y2" }, yaxis: { title: { text: "Number of states" }, domain: [0.22, 1] },
    yaxis2: { domain: [0, 0.16], showticklabels: false, showgrid: false, zeroline: false } }), CFG);
  bindClick(el);
}

let grpSeq = 0;
async function drawGroup(withStats = true) {
  const el = $("#grp"), key = S.ex.grpVar, y = S.outcome;
  drawGroupPlot(el, key, y, active());
  if (!withStats) return;
  const seq = ++grpSeq;
  const g = await api.get("/api/group", { group: key, y, exclude: exParam() });
  if (seq !== grpSeq) return;
  $("#grp-stats").innerHTML = groupStatsHTML(g);
}
function drawGroupPlot(el, key, y, d, opts = {}) {
  const T = theme();
  const traces = groupValues(key).map((g) => {
    const pts = d.filter((r) => String(r[key]) === g), c = colorFor(key, g);
    return { type: "box", name: groupLabel(key, g), y: pts.map((r) => r[y]), customdata: pts.map((r) => r.abv), text: pts.map((r) => r.state),
      boxpoints: "all", jitter: 0.45, pointpos: 0, boxmean: true, fillcolor: hexA(c, 0.15), line: { color: c, width: 2 },
      marker: { color: c, size: pts.map((r) => (isSel(r.abv) ? 13 : 8)), symbol: symbolFor(key, g), opacity: 0.95, line: { color: pts.map((r) => (isSel(r.abv) ? T.red : T.paper)), width: pts.map((r) => (isSel(r.abv) ? 3 : 1)) } },
      hovertemplate: "%{text}: %{y:.1f}%<extra>" + esc(groupLabel(key, g)) + "</extra>" };
  });
  Plotly.react(el, traces, layout({ showlegend: false, yaxis: { title: { text: label(y) } }, margin: { l: 52, r: 10, t: 6, b: opts.mini ? 30 : 44 } }), CFG);
  bindClick(el);
}
function groupStatsHTML(g) {
  const s = [...g.groups].sort((a, b) => a.mean - b.mean);
  return `<p class="bigplain" style="font-size:14px">Lowest: <b>${esc(groupLabel(g.group, s[0].group))}</b> (${fmt(s[0].mean)}%) · highest: <b>${esc(groupLabel(g.group, s.at(-1).group))}</b> (${fmt(s.at(-1).mean)}%). ${g.anova_p < 0.05 ? "These differences are bigger than luck would explain." : "These differences could be luck."}</p>
    <details><summary>Show the numbers 🤓</summary>
    <p class="tab-nums">${g.groups.map((x) => `${esc(groupLabel(g.group, x.group))} ${fmt(x.mean)}% (n=${x.n}, ${term("ci", "range")} ${fmt(x.ci[0])}–${fmt(x.ci[1])})`).join(" · ")}</p>
    <p class="tab-nums">ANOVA ${term("p", "p")} ${fmtP(g.anova_p)} · Kruskal-Wallis p ${fmtP(g.kruskal_p)} · share of differences explained by group (η²) ${fmt(g.eta2 * 100, 0)}%</p>
    ${g.pairwise?.length ? `<p class="tab-nums">Pairs (Holm-adjusted): ${g.pairwise.map((p) => `<span class="${p.p_holm < 0.05 ? "sig" : ""}">${esc(groupLabel(g.group, p.a))} vs ${esc(groupLabel(g.group, p.b))} ${signed(p.diff, 1)} pts (p ${fmtP(p.p_holm)})</span>`).join(" · ")}</p>` : ""}</details>`;
}

function drawRank() {
  const el = $("#rank"), v = S.ex.rankVar, T = theme();
  const d = active().slice().sort((a, b) => b[v] - a[v]);
  const traces = REGIONS.map((r, i) => {
    const pts = d.filter((x) => x.region === r);
    return { type: "bar", name: r, x: pts.map((x) => x.abv), y: pts.map((x) => x[v]), customdata: pts.map((x) => x.abv), hovertext: pts.map((x) => x.state),
      marker: { color: pts.map((x) => (!hasSel() || isSel(x.abv) ? T.series[i] : hexA(T.series[i], 0.3))), line: { color: pts.map((x) => (isSel(x.abv) ? T.red : T.paper)), width: pts.map((x) => (isSel(x.abv) ? 3 : 1)) } },
      hovertemplate: `%{hovertext}: %{y:.1f}<extra>${r}</extra>` };
  });
  Plotly.react(el, traces, layout({ barmode: "overlay", bargap: 0.18, xaxis: { categoryorder: "array", categoryarray: d.map((x) => x.abv), tickangle: -60, tickfont: { size: 10 } },
    yaxis: { title: { text: label(v) } } }), CFG);
  bindClick(el);
}

async function drawHeat() {
  const el = $("#heat"), T = theme();
  const m = await api.get("/api/matrix", { method: S.ex.heat, exclude: exParam() });
  const short = m.vars.map((v) => label(v).replace(" (% of adults)", " %").replace(" (log scale)", ""));
  const ann = [];
  m.r.forEach((row, i) => row.forEach((v, j) => ann.push({ x: j, y: i, text: (m.q[i][j] < 0.05 && i !== j ? "<b>" : "") + fmt(v, 2) + (m.q[i][j] < 0.05 && i !== j ? "</b>" : ""), showarrow: false, font: { size: 10.5, color: Math.abs(v) > 0.6 ? "#ffffff" : T.ink } })));
  Plotly.react(el, [{ type: "heatmap", z: m.r, x: short.map((_, i) => i), y: short.map((_, i) => i), zmin: -1, zmax: 1, colorscale: [[0, T.divNeg], [0.5, T.divMid], [1, T.divPos]], xgap: 3, ygap: 3,
    customdata: m.r.map((row, i) => row.map((_, j) => [short[i], short[j], fmtP(m.q[i][j])])),
    hovertemplate: "%{customdata[0]}<br>& %{customdata[1]}<br>link: %{z:.2f}<br>adjusted p: %{customdata[2]}<extra></extra>", colorbar: { thickness: 12, tickfont: { color: T.ink2, size: 11 }, outlinewidth: 0 } }],
    layout({ annotations: ann, margin: { l: 170, r: 10, t: 6, b: 140 }, xaxis: { tickvals: short.map((_, i) => i), ticktext: short, tickangle: -45, showgrid: false },
      yaxis: { tickvals: short.map((_, i) => i), ticktext: short, autorange: "reversed", showgrid: false } }), CFG);
  el.removeAllListeners?.("plotly_click");
  el.on("plotly_click", (ev) => {
    const p = ev.points[0]; const a = m.vars[p.x], b = m.vars[p.y]; if (a === b) return;
    const numeric = $$("#sc-x option").map((o) => o.value);
    if (!numeric.includes(a) || !numeric.includes(b)) { toast("That's a yes/no factor. Try the Compare groups chart."); return; }
    if (S.meta.outcomes.includes(a)) { S.ex.y = a; S.ex.x = b; } else { S.ex.y = b; S.ex.x = a; }
    $("#sc-x").value = S.ex.x; $("#sc-y").value = S.ex.y; drawScatter();
    $("#scatter").scrollIntoView({ behavior: "smooth", block: "center" });
  });
}

function drawTable() {
  const cols = [["abv", "State"], ["region", "Region"], ["turnout_rate_vep", "Turnout % (eligible)"], ["turnout_rate_vap", "Turnout % (all adults)"], ["total_turnout", "Votes"], ["vep", "Eligible voters"],
    ["pct_noncitizen", "Non-citizens %"], ["prison_pct_vap", "In prison %"], ["felony_regime", "Felony voting rules"], ["status", "Result status"]];
  let rows = S.data.slice();
  if (S.ex.sortKey) rows.sort((a, b) => (a[S.ex.sortKey] > b[S.ex.sortKey] ? 1 : -1) * S.ex.sortDir);
  const cell = (r, k) => { const v = r[k]; if (typeof v === "number") return `<td class="num">${["total_turnout", "vep"].includes(k) ? fmtInt(v) : fmt(v, k.includes("prison") ? 2 : 1)}</td>`; return `<td>${esc(v)}${k === "abv" && r.alt_numerator ? " *" : ""}</td>`; };
  $("#table").innerHTML = `<table><thead><tr><th>hide</th>${cols.map(([k, l]) => `<th data-k="${k}" class="${typeof S.data[0][k] === "number" ? "num" : ""}">${l}${S.ex.sortKey === k ? (S.ex.sortDir > 0 ? " ▲" : " ▼") : ""}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr data-a="${r.abv}" class="${isSel(r.abv) ? "sel" : ""} ${r.excluded ? "ex" : ""}"><td><input type="checkbox" data-ex="${r.abv}" ${r.excluded ? "checked" : ""} aria-label="Hide ${r.abv}"></td>${cols.map(([k]) => cell(r, k)).join("")}</tr>`).join("")}</tbody></table>
    <p class="hint">* = counts votes for the top race only, so turnout is slightly undercounted.</p>`;
  $$("#table th[data-k]").forEach((th) => (th.onclick = () => { const k = th.dataset.k; S.ex.sortDir = S.ex.sortKey === k ? -S.ex.sortDir : -1; S.ex.sortKey = k; drawTable(); }));
  $$("#table tbody tr").forEach((tr) => (tr.onclick = (e) => { if (e.target.matches("input")) return; toggleSelect(tr.dataset.a, true); }));
  $$("#table input[data-ex]").forEach((cb) => (cb.onchange = () => { const s = new Set(S.exclude); cb.checked ? s.add(cb.dataset.ex) : s.delete(cb.dataset.ex); setExclude(s); }));
}

async function renderProfile() {
  const el = $("#profile");
  if (!S.focus || S.exclude.has(S.focus)) {
    el.innerHTML = `<div class="row"><span class="mascot-slot">${mascot("rosie", "happy", 60)}</span><h3>Pick a state!</h3></div><p class="muted">Click any state on the map or any dot in a chart to see its story here.</p>`;
    return;
  }
  const p = await api.get("/api/profile", { abv: S.focus, exclude: exParam() });
  const v = p.values.turnout_rate_vep, resid = v.value - p.region_expected;
  const show = ["turnout_rate_vep", "turnout_rate_vap", "pct_noncitizen", "prison_pct_vap", "log10_vep"];
  el.innerHTML = `<div class="row"><span class="mascot-slot">${mascot(resid > 0 ? "bloo" : "rosie", resid > 0 ? "happy" : "thinking", 60)}</span><div><h3>${esc(p.state)}</h3><span class="src">${esc(p.region)}</span></div></div>
    <p class="bigplain" style="font-size:14.5px">About <b>${fmt(v.value, 0)} in 100</b> eligible people voted, which ranks <b>#${v.rank}</b> of ${p.n}. That's <b>${fmt(Math.abs(resid), 1)} points ${resid > 0 ? "more" : "less"}</b> than we'd guess from ${p.region === "South" ? "being in the South" : "not being in the South"} alone.</p>
    ${p.alt_numerator ? `<p class="small">⚠️ This state only counts votes for the top race, so its real turnout was a little higher.</p>` : ""}
    <div class="profile-bars">${show.map((k) => { const x = p.values[k]; return `<div class="pbar"><span>${esc(label(k))}</span><span class="v">${fmt(x.value, k === "prison_pct_vap" ? 2 : 1)}</span><div class="track" title="Higher than ${fmt(x.pctile, 0)}% of states"><div class="fill" style="width:${x.pctile}%"></div></div></div>`; }).join("")}</div>
    <p class="hint">Bars show where the state sits from lowest (left) to highest (right) among the ${p.n} places.</p>
    <p class="row"><button class="btn sm blue" id="pf-ask">Ask about ${esc(p.state)}</button><button class="btn sm" id="pf-ex">Hide ${p.abv}</button><a class="small" href="${esc(p.source)}" target="_blank" rel="noopener">official results ↗</a></p>`;
  $("#pf-ask").onclick = () => { showTab("ask"); askQuestion(`Tell me about ${p.state}`); };
  $("#pf-ex").onclick = () => setExclude(new Set([...S.exclude, p.abv]));
}

let selSeq = 0;
async function renderSelectionPanel() {
  const el = $("#selection-panel");
  if (S.selected.size < 2) {
    el.innerHTML = `<div class="row"><span class="mascot-slot">${mascot("bloo", "thinking", 56)}</span><h3>Your picks vs. everyone else</h3></div>
      <p class="muted">Pick two or more states (draw a loop on the dot chart, shift-click, or click table rows) and Ballo will compare them with the rest on everything.</p>`;
    return;
  }
  const seq = ++selSeq;
  const r = await api.post("/api/selection", { selected: [...S.selected], y: S.outcome, exclude: [...S.exclude] });
  if (seq !== selSeq) return;
  if (!r.ok) { el.innerHTML = `<h3>Your picks vs. everyone else</h3><p class="muted">${esc(r.msg)}</p>`; return; }
  const sig = r.rows.filter((x) => x.q < 0.05);
  el.innerHTML = `<h3>Your ${r.n_sel} picks vs. the other ${r.n_rest}</h3>
    <p class="bigplain" style="font-size:14px">${sig.length ? `Your picks clearly differ on: <b>${sig.map((x) => esc(label(x.var))).join(", ")}</b>.` : "Nothing stands out clearly. Any differences could be luck."}</p>
    <table><thead><tr><th>What</th><th class="num">Your picks</th><th class="num">The rest</th><th class="num">Difference</th></tr></thead><tbody>
    ${r.rows.map((x) => `<tr><td>${esc(label(x.var))}</td><td class="num">${fmt(x.mean_sel, 2)}</td><td class="num">${fmt(x.mean_rest, 2)}</td><td class="num ${x.q < 0.05 ? "sig" : ""}">${signed(x.diff, 2)}</td></tr>`).join("")}</tbody></table>
    <p class="hint">Red = passes the “probably not luck” test (Mann-Whitney, adjusted for checking many things). Picking states after looking at them makes this exploratory, not proof.</p>`;
}

// ───────────────────────── discoveries ─────────────────────────
function renderFeed() {
  hydrateMascots($("#tab-discover"));
  $("#feed").innerHTML = S.findings.map((f) => `
    <article class="card fcard" data-f="${f.id}" tabindex="0">
      <div class="top-row"><span class="num-badge">${f.rank}</span>${verdictBadge(f)}<span class="spacer"></span><span class="mascot-slot">${mascot(["rosie", "ballo", "bloo"][f.rank % 3], f.mood, 48)}</span></div>
      <h3>${esc(f.title)}</h3>
      <p class="plain">${esc(f.plain)}</p>
      <div id="mini-${f.id}" class="plot h-220"></div>
      <p class="trust">How much to trust it: ${esc(f.confidence_plain)}</p>
      <details><summary>Show the numbers 🤓</summary>
        <p class="tab-nums"><b>${esc(f.headline_stat)}</b></p><p>${esc(f.explanation)}</p>
        <p class="muted">Label rule: ${esc(f.verdict_rule)}, ${f.verdict_rule_met ? "met ✓" : "not met"}.</p></details>
      <div><button class="btn primary sm">Dig deeper →</button></div>
    </article>`).join("");
  $$(".fcard").forEach((c) => {
    const go = (e) => { if (e.target.closest(".plot") || e.target.closest("details")) return; S.inv.id = c.dataset.f; showTab("investigate"); };
    c.onclick = go; c.onkeydown = (e) => e.key === "Enter" && go(e);
  });
  for (const f of S.findings) drawFindingChart($("#mini-" + f.id), f, true);
}

async function drawFindingChart(el, f, mini = false) {
  const T = theme(), c = f.chart, d = active();
  const Lm = (o) => layout({ ...o, margin: mini ? { l: 46, r: 8, t: 6, b: 36 } : { l: 58, r: 16, t: 10, b: 52 } });
  if (c.kind === "group") return drawGroupPlot(el, c.group, c.y, d, { mini });
  if (c.kind === "scatter") {
    const cc = await api.get("/api/correlate", { x: c.x, y: c.y, exclude: exParam() });
    const traces = REGIONS.map((r, i) => { const p = d.filter((x) => x.region === r);
      return { type: "scatter", mode: mini ? "markers" : "markers+text", name: r, x: p.map((x) => x[c.x]), y: p.map((x) => x[c.y]), text: p.map((x) => x.abv), customdata: p.map((x) => x.abv), textposition: "top center", textfont: { size: 10, color: T.ink2 },
        marker: { color: T.series[i], symbol: SYMBOLS[i], size: 10, line: { color: T.paper, width: 1.5 } }, hovertemplate: `%{text}: (%{x:.2f}, %{y:.1f})<extra>${r}</extra>`, cliponaxis: false }; });
    traces.unshift({ type: "scatter", mode: "lines", x: cc.fit.x, y: cc.fit.y, line: { color: T.blue, width: 3 }, name: "trend", hoverinfo: "skip" });
    Plotly.react(el, traces, Lm({ showlegend: !mini, xaxis: { title: { text: label(c.x) } }, yaxis: { title: { text: label(c.y) } } }), CFG); bindClick(el); return;
  }
  if (c.kind === "denominator") {
    const [a, b] = await Promise.all([api.get("/api/correlate", { x: "pct_noncitizen", y: "turnout_rate_vep", exclude: exParam() }), api.get("/api/correlate", { x: "pct_noncitizen", y: "turnout_rate_vap", exclude: exParam() })]);
    const segs = { type: "scatter", mode: "lines", x: d.flatMap((r) => [r.pct_noncitizen, r.pct_noncitizen, null]), y: d.flatMap((r) => [r.turnout_rate_vep, r.turnout_rate_vap, null]), line: { color: T.grid, width: 2 }, hoverinfo: "skip", showlegend: false };
    const pts = (k, col, nm, sym) => ({ type: "scatter", mode: "markers", name: nm, x: d.map((r) => r.pct_noncitizen), y: d.map((r) => r[k]), customdata: d.map((r) => r.abv), text: d.map((r) => r.state), marker: { color: col, size: 9, symbol: sym, line: { color: T.paper, width: 1 } }, hovertemplate: `%{text}<br>non-citizens %{x:.1f}%<br>${nm}: %{y:.1f}%<extra></extra>` });
    const fit = (cc, col, nm) => ({ type: "scatter", mode: "lines", x: cc.fit.x, y: cc.fit.y, line: { color: col, width: 3 }, name: nm, hoverinfo: "skip" });
    Plotly.react(el, [segs, pts("turnout_rate_vep", T.blue, "out of eligible (VEP)", "circle"), pts("turnout_rate_vap", T.red, "out of all adults (VAP)", "square"), fit(a, T.blue, `VEP trend (r ${fmt(a.r, 2)})`), fit(b, T.red, `VAP trend (r ${fmt(b.r, 2)})`)],
      Lm({ xaxis: { title: { text: "Non-citizens (% of adults)" } }, yaxis: { title: { text: "Turnout (%)" } }, legend: { orientation: "h", y: 1.22, font: { size: 10.5 } } }), CFG); bindClick(el); return;
  }
  if (c.kind === "partial") {
    const ry = residualize(d, c.y, c.controls), rx = residualize(d, c.x, c.controls), slope = ols1(rx, ry);
    const xs = [Math.min(...rx), Math.max(...rx)];
    const traces = REGIONS.map((r, i) => { const idx = d.map((x, k) => (x.region === r ? k : -1)).filter((k) => k >= 0);
      return { type: "scatter", mode: mini ? "markers" : "markers+text", name: r, x: idx.map((k) => rx[k]), y: idx.map((k) => ry[k]), text: idx.map((k) => d[k].abv), customdata: idx.map((k) => d[k].abv), textposition: "top center", textfont: { size: 10, color: T.ink2 },
        marker: { color: T.series[i], symbol: SYMBOLS[i], size: 10, line: { color: T.paper, width: 1.5 } }, hovertemplate: `%{text}<extra>${r}</extra>` }; });
    traces.unshift({ type: "scatter", mode: "lines", x: xs, y: xs.map((v) => slope * v), line: { color: T.blue, width: 3 }, name: "trend after adjusting", hoverinfo: "skip" });
    Plotly.react(el, traces, Lm({ showlegend: !mini, xaxis: { title: { text: "Non-citizens, after removing size & region effects" } }, yaxis: { title: { text: "Turnout, adjusted" } } }), CFG); bindClick(el); return;
  }
  if (c.kind === "residuals") {
    const r = await api.post("/api/regress", { y: c.y, terms: c.terms, exclude: [...S.exclude] });
    const rows = d.filter((x) => r.fitted[x.abv] !== undefined);
    const big = new Set(Object.entries(r.student_resid).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 6).map(([a]) => a));
    const lo = Math.min(...rows.map((x) => x[c.y])) - 2, hi = Math.max(...rows.map((x) => x[c.y])) + 2;
    const traces = REGIONS.map((reg, i) => { const p = rows.filter((x) => x.region === reg);
      return { type: "scatter", mode: "markers+text", name: reg, x: p.map((x) => r.fitted[x.abv]), y: p.map((x) => x[c.y]), text: p.map((x) => (big.has(x.abv) ? x.abv : "")), customdata: p.map((x) => x.abv), textposition: "top center", textfont: { size: 10, color: T.ink2 },
        marker: { color: T.series[i], symbol: SYMBOLS[i], size: 10, line: { color: T.paper, width: 1.5 } }, hovertext: p.map((x) => `${x.state}<br>actual ${fmt(x[c.y])}%, guessed ${fmt(r.fitted[x.abv])}%`), hoverinfo: "text", cliponaxis: false }; });
    traces.unshift({ type: "scatter", mode: "lines", x: [lo, hi], y: [lo, hi], line: { color: T.red, dash: "dash", width: 2 }, name: "perfect guess", hoverinfo: "skip" });
    Plotly.react(el, traces, Lm({ showlegend: !mini, xaxis: { title: { text: "Ballo's best guess (%)" }, range: [lo, hi] }, yaxis: { title: { text: "Actual turnout (%)" }, range: [lo, hi] } }), CFG); bindClick(el);
  }
}
function solve(A, b) {
  const n = A.length, M = A.map((r, i) => [...r, b[i]]);
  for (let i = 0; i < n; i++) {
    let p = i; for (let k = i + 1; k < n; k++) if (Math.abs(M[k][i]) > Math.abs(M[p][i])) p = k;
    [M[i], M[p]] = [M[p], M[i]];
    for (let k = i + 1; k < n; k++) { const f = M[k][i] / M[i][i]; for (let j = i; j <= n; j++) M[k][j] -= f * M[i][j]; }
  }
  const x = Array(n).fill(0);
  for (let i = n - 1; i >= 0; i--) { let s = M[i][n]; for (let j = i + 1; j < n; j++) s -= M[i][j] * x[j]; x[i] = s / M[i][i]; }
  return x;
}
function residualize(d, y, controls) {
  const X = d.map((r) => [1, ...controls.map((c) => +r[c])]), Y = d.map((r) => +r[y]);
  const k = X[0].length, XtX = Array.from({ length: k }, (_, i) => Array.from({ length: k }, (_, j) => X.reduce((s, r) => s + r[i] * r[j], 0)));
  const Xty = Array.from({ length: k }, (_, i) => X.reduce((s, r, n) => s + r[i] * Y[n], 0));
  const b = solve(XtX, Xty);
  return Y.map((v, n) => v - X[n].reduce((s, x, i) => s + x * b[i], 0));
}
const ols1 = (x, y) => x.reduce((s, v, i) => s + v * y[i], 0) / x.reduce((s, v) => s + v * v, 0);

// ───────────────────────── investigate ─────────────────────────
function renderInvList() {
  $("#inv-list").innerHTML = `<h4 style="margin-top:0">Pick a discovery</h4>` + S.findings.map((f) => `<button data-f="${f.id}" class="${f.id === S.inv.id ? "on" : ""}"><span class="small muted">#${f.rank} · ${esc(f.verdict_plain)}</span><br>${esc(f.title)}</button>`).join("");
  $$("#inv-list button").forEach((b) => (b.onclick = () => renderInvestigation(b.dataset.f)));
}
const STAT_LABELS = {
  n: "States", welch_p: "p (t-test)", mwu_p: "p (rank test)", diff: "Difference (pts)", diff_ci: "95% range", cohens_d: "Effect size (d)", eta2_region: "Explained by region", anova_p: "p (regions differ)",
  adjusted_coef: "Gap after adjusting", adjusted_ci: "…95% range", adjusted_p: "…p", diff_without_dc: "Gap without DC", spec_share: "Re-checks that agree",
  r_vap: "Link with all-adults turnout", p_vap: "…p", r_vep: "Link with eligible turnout", p_vep: "…p", diff_r_ci: "Difference in links (95% range)", gap_r: "Non-citizens vs. VEP−VAP gap", rank_rho: "Rankings agree (ρ)",
  r: "Correlation r", p: "p", q: "Adjusted p (q)", boot_r_ci: "95% range (r)", slope: "Slope", adj_slope: "Slope after adjusting for South", adj_p: "…p", south_prison_r: "South vs. prison share (r)", loo_range: "r when dropping each state",
  coef: "Adjusted effect", boot_ci: "95% range (bootstrap)", noncit_size_r: "Non-citizens vs. size (r)", loo_sig: "Drop-one fits that pass", n_alt: "* states", adj_coef: "Gap after adjusting for South",
  rho: "Rank-based ρ", r_ci: "95% range", quad_p: "Curve p", unweighted_mean: "Average of states", national: "National rate", kruskal_p: "p (groups differ)", eta2: "Explained by group", r_community: "Probation/parole share r", p_community: "…p",
  r2: "Explained (in sample)", loo_r2: "Explained (predicting new states)", south_loo_r2: "South alone (new states)",
};
function statVal(k, v) {
  if (Array.isArray(v)) return v.map((x) => fmt(x, 2)).join(" to ");
  if (v && typeof v === "object") return Object.entries(v).map(([a, b]) => typeof b === "object" ? `${a}: r=${fmt(b.r, 2)}` : `${a} ${fmt(b, 0)}`).join("; ");
  if (/(^p$|_p$|^p_)/.test(k) || k === "q") return fmtP(v);
  if (k.includes("share") || k.includes("r2") || k.includes("eta2")) return fmt(v * 100, 0) + "%";
  if (["n", "n_alt", "loo_sig"].includes(k)) return String(v);
  return fmt(v, 2);
}
const TEST_PLAIN = {
  adjust_alt: "Account for counting method", adjust_south: "Account for the South", adjust_prison: "Account for prison share", adjust_size: "Account for state size",
  adjust_all: "Account for everything", exclude_dc: "Leave out DC", rank_test: "Use ranks (ignore extremes)", permutation: "Shuffle test (5,000×)",
  loo: "Drop one state at a time", vap_outcome: "Count out of all adults", within_region: "Look inside each region", within_nonsouth: "Compare non-South regions", spec: "Count sturdy re-checks",
};
async function renderInvestigation(id) {
  S.inv.id = id; renderInvList();
  const f = S.findings.find((x) => x.id === id), el = $("#inv-main");
  el.innerHTML = `
    <div class="card"><div class="row">${verdictBadge(f)}<span class="trust">${esc(f.confidence_plain)}</span></div>
      <div class="bubble-row" style="margin:10px 0 0"><span class="mascot-slot">${mascot("ballo", f.mood, 84)}</span>
        <div class="speech"><h2 style="font-size:21px">${esc(f.title)}</h2><p style="color:var(--ink)">${esc(f.plain)}</p></div></div>
      ${S.exclude.size ? `<p class="small">Charts and tests below leave out ${[...S.exclude].join(", ")}.</p>` : ""}</div>
    <div class="card step"><h3><span class="n">1</span> What we saw <span class="kind obs">from the data</span></h3>
      <div id="inv-chart" class="plot h-400"></div>
      <details><summary>Show the numbers 🤓</summary><p>${esc(f.explanation)}</p>
        <div class="statgrid">${Object.entries(f.stats).filter(([k]) => STAT_LABELS[k]).map(([k, v]) => `<div><span>${esc(STAT_LABELS[k])}</span><b>${esc(statVal(k, v))}</b></div>`).join("")}</div></details></div>
    <div class="card step"><h3><span class="n">2</span> Why might this happen? <span class="kind spec">educated guesses</span></h3>
      <p class="small muted">These ideas come from what's known about elections. The data here can't prove them.</p>
      <ul class="clean hearts">${f.hypotheses.map((h) => `<li>${esc(h)}</li>`).join("")}</ul>
      <p class="small"><b>Why it's worth a closer look:</b> ${esc(f.why_interesting)}</p></div>
    <div class="card step"><h3><span class="n">3</span> Could something else explain it? <span class="kind interp">tap to test</span></h3>
      ${f.alternatives.length ? f.alternatives.map(([t, test], i) => `<div class="alt"><div>${esc(t)}<div id="alt-res-${i}"></div></div>${test ? `<button class="btn sm blue" data-alt="${i}" data-t="${test}">Test it!</button>` : `<span class="small muted">can't test with this data</span>`}</div>`).join("") : '<p class="muted">Nothing specific to check here.</p>'}</div>
    <div class="card step"><h3><span class="n">4</span> Try a check yourself <span class="kind obs">runs real math</span></h3>
      <p class="small muted">Each button re-runs the analysis a different way. Watch whether the answer changes.</p>
      <div class="row">${f.tests.map((t) => `<button class="btn sm" data-test="${t}">${esc(TEST_PLAIN[t] || S.meta.tests[t] || t)}</button>`).join(" ")}</div><div id="test-log"></div></div>
    <div class="card step"><h3><span class="n">5</span> Does it hold up? <span class="kind interp">many re-checks</span></h3>
      <p class="small">We re-ran this analysis <b>many reasonable ways</b>: adding other factors, switching how turnout is counted, and dropping unusual states. <b>Each dot is one re-run.</b> Filled dots pass the “probably not luck” test. If most dots sit on the same side of zero, the finding is sturdy; if they scatter across zero, it's shaky.</p>
      <div class="row controls"><label>Turnout counted out of <select id="spec-o"><option value="">either</option><option value="turnout_rate_vep">eligible (VEP)</option><option value="turnout_rate_vap">all adults (VAP)</option></select></label>
        <label>States used <select id="spec-s"><option value="">every version</option></select></label></div>
      <div id="spec" class="plot h-400"></div><div id="spec-sum" class="small"></div>
      <details><summary>Build your own version 🛠️</summary>
        <p class="small">Choose which other factors to ${term("control", "take into account")}, then press the button. Your versions stack up below so you can compare.</p>
        <div class="row controls" id="mb"></div><div id="mb-out"></div></details></div>
    <div class="card step"><h3><span class="n">6</span> What this data can't tell us</h3>
      <ul class="clean hearts">${f.limitations.map((l) => `<li>${esc(l)}</li>`).join("")}<li>A pattern across states isn't proof that one thing causes another.</li></ul></div>`;
  drawFindingChart($("#inv-chart"), f, false);
  $$("[data-test]", el).forEach((b) => (b.onclick = () => runTest(f, b.dataset.test, $("#test-log"), b)));
  $$("[data-alt]", el).forEach((b) => (b.onclick = () => runTest(f, b.dataset.t, $("#alt-res-" + b.dataset.alt), b, true)));
  renderModelBuilder(f);
  const sc = await api.get("/api/spec", { focal: f.focal, exclude: exParam() });
  if (S.inv.id !== id) return;
  $("#spec-s").innerHTML += sc.samples.map((s) => `<option>${esc(s)}</option>`).join("");
  const draw = () => drawSpec(sc, $("#spec-o").value, $("#spec-s").value);
  $("#spec-o").onchange = draw; $("#spec-s").onchange = draw; draw();
}
function drawSpec(sc, o, s) {
  const T = theme();
  const specs = sc.specs.filter((x) => (!o || x.outcome === o) && (!s || x.sample === s)).sort((a, b) => a.coef - b.coef);
  const mk = (oc, col, sym, nm) => { const p = specs.map((x, k) => ({ ...x, k })).filter((x) => x.outcome === oc);
    return { type: "scatter", mode: "markers", name: nm, x: p.map((x) => x.k), y: p.map((x) => x.coef),
      error_y: { type: "data", symmetric: false, array: p.map((x) => x.hi - x.coef), arrayminus: p.map((x) => x.coef - x.lo), color: hexA(col, 0.35), thickness: 1.2, width: 0 },
      marker: { color: p.map((x) => (x.p < 0.05 ? col : T.paper)), line: { color: col, width: 2 }, size: 8, symbol: sym },
      hovertext: p.map((x) => `effect ${fmt(x.coef, 2)} (range ${fmt(x.lo, 2)} to ${fmt(x.hi, 2)})<br>${x.p < 0.05 ? "passes" : "doesn't pass"} the luck test<br>also accounting for: ${x.controls.length ? x.controls.map(label).join(", ") : "nothing"}<br>states: ${x.sample}`), hoverinfo: "text" }; };
  Plotly.react($("#spec"), [mk("turnout_rate_vep", T.blue, "circle", "counted out of eligible"), mk("turnout_rate_vap", T.red, "square", "counted out of all adults")], layout({
    xaxis: { title: { text: `${specs.length} re-runs, sorted from smallest to largest effect` }, showticklabels: false, showgrid: false },
    yaxis: { title: { text: `Effect of ${label(sc.focal)}` }, zeroline: true, zerolinewidth: 2, zerolinecolor: T.ink2 } }), CFG);
  const agree = specs.filter((x) => Math.sign(x.coef) === Math.sign(sc.baseline.coef) && x.p < 0.05).length;
  const share = specs.length ? agree / specs.length : 0;
  $("#spec-sum").innerHTML = `<p class="bigplain" style="font-size:14px">${fmt(share * 100, 0)}% of these re-runs agree and pass the luck test. ${share >= 0.8 ? "That's sturdy! 💪" : share >= 0.4 ? "That's mixed, so be careful." : "That's shaky. 🫧"}</p>`;
}
function renderModelBuilder(f) {
  const coll = S.meta.collinear[f.focal] || [];
  const pool = S.meta.control_pool.concat(["community_inelig_pct_vap"]).filter((c) => c !== f.focal && !coll.includes(c));
  $("#mb").innerHTML = `<label>Turnout out of <select id="mb-y"><option value="turnout_rate_vep">eligible (VEP)</option><option value="turnout_rate_vap">all adults (VAP)</option></select></label>
    <span class="small"><b>${esc(label(f.focal))}</b> +</span>
    ${pool.map((c) => `<label class="chk"><input type="checkbox" value="${c}"> ${esc(label(c))}</label>`).join("")}
    <button class="btn primary sm" id="mb-run">Run it ✦</button>`;
  S.inv.history = [];
  $("#mb-run").onclick = async () => {
    const terms = [f.focal, ...$$("#mb input:checked").map((i) => i.value)], y = $("#mb-y").value;
    try {
      const r = await api.post("/api/regress", { y, terms, exclude: [...S.exclude] });
      const c = r.coefs.find((x) => x.term === f.focal);
      S.inv.history.push({ y, terms, excl: [...S.exclude], c, r2: r.r2, n: r.n });
      renderHistory(f, r);
    } catch (e) { toast(e.message); }
  };
}
function renderHistory(f, last) {
  const T = theme(), H = S.inv.history, c = last.coefs.find((x) => x.term === f.focal);
  $("#mb-out").innerHTML = `
    <div class="result"><p class="p">${esc(label(f.focal))}: effect ${signed(c.coef, 2)} (95% range ${fmt(c.ci[0], 2)} to ${fmt(c.ci[1], 2)}). ${c.p < 0.05 ? "Passes the luck test." : "Could be luck."} This version explains ${fmt(last.r2 * 100, 0)}% of the differences between states.</p>
      <details><summary>Full table</summary><table><thead><tr><th>Factor</th><th class="num">Effect</th><th class="num">95% range</th><th class="num">p</th></tr></thead><tbody>
      ${last.coefs.map((x) => `<tr><td>${esc(label(x.term))}</td><td class="num ${x.p < 0.05 ? "sig" : ""}">${fmt(x.coef, 3)}</td><td class="num">${fmt(x.ci[0], 2)} to ${fmt(x.ci[1], 2)}</td><td class="num">${fmtP(x.p)}</td></tr>`).join("")}</tbody></table>
      <p class="hint">${esc(last.formula)} · n = ${last.n} · ${esc(last.se_type)}</p></details></div>
    <h4>Your versions side by side</h4><div id="mb-forest" class="plot" style="height:${80 + 36 * H.length}px"></div>`;
  const names = H.map((h, i) => `#${i + 1} ${h.y === "turnout_rate_vap" ? "all adults" : "eligible"}${h.terms.length > 1 ? " + " + h.terms.slice(1).map((t) => label(t).split(" (")[0]).join(", ") : ""}${h.excl.length ? ` − ${h.excl.join(",")}` : ""}`);
  Plotly.react($("#mb-forest"), [{ type: "scatter", mode: "markers", y: names, x: H.map((h) => h.c.coef),
    error_x: { type: "data", symmetric: false, array: H.map((h) => h.c.ci[1] - h.c.coef), arrayminus: H.map((h) => h.c.coef - h.c.ci[0]), color: T.ink2, thickness: 2, width: 5 },
    marker: { size: 12, color: H.map((h) => (h.c.p < 0.05 ? T.red : T.paper)), line: { color: T.red, width: 2.5 } },
    hovertext: H.map((h) => `effect ${fmt(h.c.coef, 2)}, p ${fmtP(h.c.p)}`), hoverinfo: "text" }],
    layout({ margin: { l: 10, r: 16, t: 6, b: 40 }, xaxis: { zeroline: true, zerolinewidth: 2, zerolinecolor: T.ink2, title: { text: "Effect with 95% range (filled = passes the luck test)" } }, yaxis: { autorange: "reversed", automargin: true } }), CFG);
}
async function runTest(f, test, target, btn, replace = false) {
  btn.disabled = true; const old = btn.textContent; btn.textContent = "Running…";
  try {
    const r = await api.post("/api/test", { finding: f.id, test, exclude: [...S.exclude] });
    const html = `<div class="result"><div class="t">✦ ${esc(TEST_PLAIN[test] || r.label)} (${r.n} states)</div><p class="p">${esc(testPlain(test, r))}</p><details><summary>Details</summary><p>${esc(r.summary)}</p></details><div class="tplot"></div></div>`;
    if (replace) target.innerHTML = html; else target.insertAdjacentHTML("afterbegin", html);
    if (test === "loo") {
      const pl = target.querySelector(".tplot"); pl.classList.add("plot"); pl.style.height = "220px";
      const rows = r.result.rows.slice().sort((a, b) => a.coef - b.coef), T = theme();
      Plotly.react(pl, [{ type: "bar", x: rows.map((x) => x.state), y: rows.map((x) => x.coef), marker: { color: rows.map((x) => (x.p < 0.05 ? T.blueSoft : hexA(T.blueSoft, 0.4))), line: { color: T.blue, width: 1 } }, hovertemplate: "without %{x}: %{y:.2f}<extra></extra>" }],
        layout({ margin: { l: 50, r: 8, t: 6, b: 50 }, xaxis: { tickangle: -60, tickfont: { size: 9 }, categoryorder: "array", categoryarray: rows.map((x) => x.state) }, yaxis: { title: { text: "Effect without that state" } } }), CFG);
    }
  } catch (e) { target.insertAdjacentHTML("afterbegin", `<div class="result err">${esc(e.message)}</div>`); }
  btn.disabled = false; btn.textContent = old;
}
// Everyday-language reading of a test result (every number comes from the server's result)
function testPlain(test, r) {
  const b = r.baseline, res = r.result || {};
  const still = (p) => (p < 0.05 ? "still passes the luck test" : "no longer passes the luck test");
  if (test.startsWith("adjust_") || test === "exclude_dc" || test === "vap_outcome") {
    const ratio = b.coef !== 0 ? Math.abs(res.coef / b.coef) : 1;
    return `The effect goes from ${fmt(b.coef, 2)} to ${fmt(res.coef, 2)} (${ratio < 0.5 ? "much smaller" : ratio < 0.85 ? "somewhat smaller" : ratio > 1.15 ? "bigger" : "about the same"}) and ${still(res.p)}.`;
  }
  if (test === "permutation") return `We shuffled turnout randomly between states 5,000 times. A link this strong showed up by chance ${fmt(res.p * 100, 1)}% of the time, ${res.p < 0.05 ? "so it's probably not luck." : "so it could easily be luck."}`;
  if (test === "loo") return `Leaving out one state at a time, the effect stays between ${fmt(res.min, 2)} and ${fmt(res.max, 2)}, and passes the luck test in ${res.n_sig} of ${res.rows.length} tries.`;
  if (test === "rank_test") return res.rho !== undefined ? `Using rankings instead of exact values, the link is ${fmt(res.rho, 2)} and ${still(res.p)}.` : `Using rankings, the groups ${res.p < 0.05 ? "still clearly differ" : "don't clearly differ"} (typical values ${fmt(res.median_a, 1)}% vs ${fmt(res.median_b, 1)}%).`;
  if (test === "within_region") return "Inside each region the link is: " + res.rows.map((x) => `${x.region} ${fmt(x.r, 2)}${x.p < 0.05 ? " ✓" : ""}`).join(", ") + ". Small groups make these uncertain.";
  if (test === "within_nonsouth") return `Outside the South: ${res.groups.map((g) => `${g.group} ${fmt(g.mean, 1)}%`).join(", ")}. ${res.anova_p < 0.05 ? "They differ." : "They're about the same, so the real split is South vs. everyone else."}`;
  return r.summary;
}

// ───────────────────────── ask ─────────────────────────
const SUGGESTED = [ // must match build_static.py
  "What is the most surprising thing in this data?",
  "Which things go along with higher or lower turnout?",
  "What should I look into next?",
];
let askInit = false;
async function renderAsk() {
  hydrateMascots($("#tab-ask"));
  if (askInit) return;
  askInit = true;
  $("#ask-chips").innerHTML = SUGGESTED.map((q) => `<button type="button">${esc(q)}</button>`).join("");
  $$("#ask-chips button").forEach((b) => (b.onclick = () => askQuestion(b.textContent)));
  $("#ask-form").onsubmit = (e) => { e.preventDefault(); const q = $("#ask-input").value.trim(); if (q) askQuestion(q); };
  const ai = await api.get("/api/ai_status");
  $("#ai-toggle").disabled = !ai.available;
  $("#ai-toggle-wrap").style.display = ai.available ? "" : "none";
  $("#ai-status").textContent = ai.available ? `Optional AI explainer (${ai.model}) only sees the computed results, never the raw data.` : "";
}
async function askQuestion(q) {
  $("#ask-input").value = q;
  const id = "qa" + Date.now();
  $("#ask-log").insertAdjacentHTML("afterbegin", `<div class="card qa" id="${id}"><div class="q">“${esc(q)}”</div><div class="answer-row"><span class="mascot-slot bounce">${mascot("ballo", "thinking", 60)}</span><p class="loading">Running the numbers…</p></div></div>`);
  const box = $("#" + id);
  try {
    const r = await api.post("/api/ask", { question: q, exclude: [...S.exclude], outcome: S.outcome, use_ai: $("#ai-toggle").checked });
    box.innerHTML = `<div class="q">“${esc(q)}”</div>
      <div class="answer-row"><span class="mascot-slot">${mascot("ballo", "happy", 60)}</span><div class="speech">${esc(r.plain || r.answer)}</div></div>
      <div class="qa-viz" style="margin-top:12px"></div>
      <details><summary>Show the numbers 🤓</summary><p>${esc(r.answer)}</p><p class="ran"><b>What Ballo actually calculated:</b> ${r.analyses_run.map(esc).join("; ")}${r.excluded.length ? ` (leaving out ${r.excluded.join(", ")})` : ""}</p></details>
      ${r.ai ? (r.ai.ok ? `<div class="ai-box"><div class="t">AI explainer (${esc(r.ai.model)}): based only on the results above, it did no math itself</div>${esc(r.ai.text)}</div>` : `<div class="ai-box"><div class="t">AI explainer unavailable</div>${esc(r.ai.error)}</div>`) : ""}`;
    drawAskViz(r, box.querySelector(".qa-viz"));
  } catch (e) { box.innerHTML = `<div class="q">“${esc(q)}”</div><p class="err">${esc(e.message)}</p>`; }
}
function drawAskViz(r, el) {
  const T = theme();
  const plot = (h) => { const d = document.createElement("div"); d.className = "plot"; d.style.height = h + "px"; el.appendChild(d); return d; };
  if (r.intent === "strongest") {
    const rows = r.table.slice().reverse(), p = plot(70 + 34 * rows.length);
    Plotly.react(p, [{ type: "bar", orientation: "h", y: rows.map((x) => label(x.x)), x: rows.map((x) => x.r),
      marker: { color: rows.map((x) => (x.r < 0 ? T.blueSoft : T.redSoft)), line: { color: rows.map((x) => (x.q < 0.05 ? T.ink : x.r < 0 ? T.blue : T.red)), width: rows.map((x) => (x.q < 0.05 ? 3 : 1.5)) } },
      error_x: { type: "data", symmetric: false, array: rows.map((x) => x.boot_r_ci[1] - x.r), arrayminus: rows.map((x) => x.r - x.boot_r_ci[0]), color: T.ink2, thickness: 1.5, width: 4 },
      hovertext: rows.map((x) => `link ${fmt(x.r, 2)} (range ${fmt(x.boot_r_ci[0], 2)} to ${fmt(x.boot_r_ci[1], 2)})<br>${x.q < 0.05 ? "passes" : "doesn't pass"} the luck test`), hoverinfo: "text" }],
      layout({ margin: { l: 10, r: 16, t: 6, b: 46 }, xaxis: { range: [-1, 1], zeroline: true, zerolinewidth: 2, zerolinecolor: T.ink2, title: { text: "← goes with LOWER turnout · link · goes with HIGHER turnout →" } }, yaxis: { automargin: true } }), CFG);
    el.insertAdjacentHTML("beforeend", `<p class="hint">Bars with a dark outline pass the “probably not luck” test. Whiskers show the 95% range.</p>`);
  } else if (r.intent === "nonlinear" || r.intent === "adjusted") {
    el.innerHTML = r.intent === "nonlinear"
      ? `<table><thead><tr><th>Factor</th><th class="num">Straight-line link</th><th class="num">Curve? (adjusted p)</th></tr></thead><tbody>${r.table.map((x) => `<tr><td>${esc(label(x.var))}</td><td class="num">${fmt(x.r, 2)}</td><td class="num">${fmtP(x.quad_q)}</td></tr>`).join("")}</tbody></table>`
      : `<table><thead><tr><th>Factor</th><th class="num">On its own</th><th class="num">After accounting for others</th><th class="num">Luck test</th></tr></thead><tbody>${r.table.map((x) => `<tr><td>${esc(label(x.var))}</td><td class="num">${fmt(x.bivariate, 2)}</td><td class="num">${fmt(x.adjusted, 2)}</td><td class="num ${x.p_adj < 0.05 ? "sig" : ""}">${x.p_adj < 0.05 ? "passes" : "could be luck"}</td></tr>`).join("")}</tbody></table>`;
  } else if (r.intent === "influence") {
    const p = plot(240);
    Plotly.react(p, [{ type: "bar", x: r.cooks.map((c) => nameOf(c[0])), y: r.cooks.map((c) => c[1]), marker: { color: T.redSoft, line: { color: T.red, width: 2 } }, hovertemplate: "%{x}: influence %{y:.3f}<extra></extra>" }],
      layout({ margin: { l: 50, r: 10, t: 6, b: 40 }, yaxis: { title: { text: "How much it sways results" } } }), CFG);
  } else if (r.intent === "pair") {
    drawFindingChart(plot(320), { chart: { kind: "scatter", x: r.corr.x, y: r.corr.y } }, false);
  } else if (r.intent === "groups") {
    drawGroupPlot(plot(300), "region", r.outcome, active());
  } else if (r.intent === "state") {
    const pr = r.profile;
    el.innerHTML = `<div class="profile-bars" style="max-width:520px">${["turnout_rate_vep", "turnout_rate_vap", "pct_noncitizen", "prison_pct_vap", "log10_vep"].map((k) => { const v = pr.values[k]; return `<div class="pbar"><span>${esc(label(k))}</span><span class="v">${fmt(v.value, 1)}</span><div class="track"><div class="fill" style="width:${v.pctile}%"></div></div></div>`; }).join("")}</div>
      <p><button class="btn sm blue" id="go${pr.abv}">See ${esc(pr.state)} on the map →</button></p>`;
    $("#go" + pr.abv).onclick = () => { showTab("explore"); setSelected([pr.abv], { focus: pr.abv }); };
  } else if (r.intent === "surprising") {
    el.innerHTML = `<ul class="clean hearts">${r.items.map((it) => { const f = S.findings.find((x) => x.id === it.finding); return `<li><a href="#" data-goinv="${it.finding}">${esc(it.title)}</a> <span class="small muted">(${esc(f?.verdict_plain || it.verdict)})</span></li>`; }).join("")}</ul>`;
    $$("[data-goinv]", el).forEach((a) => (a.onclick = (e) => { e.preventDefault(); S.inv.id = a.dataset.goinv; showTab("investigate"); }));
  } else if (r.intent === "next") {
    el.innerHTML = `<ol class="clean">${r.items.map((x) => `<li>${esc(x)}</li>`).join("")}</ol>`;
  }
}

// ───────────────────────── boot ─────────────────────────
async function boot() {
  $("#brand-mascots").innerHTML = mascot("bloo", "happy", 42) + mascot("ballo", "happy", 54) + mascot("rosie", "happy", 42);
  hydrateMascots();
  const [meta, overview, findings, data] = await Promise.all([api.get("/api/meta"), api.get("/api/overview"), api.get("/api/findings"), api.get("/api/data")]);
  Object.assign(S, { meta, overview, findings, data });
  S.inv.id = findings[0].id;
  $$(".tabs button").forEach((b) => (b.onclick = () => showTab(b.dataset.tab)));
  renderGlobalBar();
  renderOverview();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => showTab(S.tab));
}
boot().catch((e) => {
  const msg = typeof Plotly === "undefined" ? "The charting library (loaded from cdn.jsdelivr.net) couldn't load. Check your internet connection." : `Couldn't load the data: ${esc(e.message)}`;
  $("#tab-overview").innerHTML = `<div class="card err">${msg}</div>`;
  console.error(e);
});
