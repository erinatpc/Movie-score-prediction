/* Movie Score — cliente web. Consume la API REST del servicio de IA (ver /docs del backend). */
"use strict";

const DEFAULT_API = "http://localhost:8000";
const ACCEPT = { mae: 0.65, improvement: 0.10, r2: 0.30 };   // criterios de aceptación definidos en la fase 1
const state = { api: DEFAULT_API, historyOffset: 0, historyLimit: 15, pollTimer: null, loaded: {} };

try { state.api = localStorage.getItem("apiBase") || DEFAULT_API; } catch (_) { /* almacenamiento no disponible */ }

const $ = (id) => document.getElementById(id);

/* ---------- utilidades ---------- */
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v; else if (k === "text") node.textContent = v; else node.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c != null) node.append(c.nodeType ? c : document.createTextNode(String(c)));
  return node;
}
const fmt = (n, d = 3) => (n == null ? "–" : Number(n).toLocaleString("es", { minimumFractionDigits: d, maximumFractionDigits: d }));
const pct = (n) => (n == null ? "–" : (n * 100).toLocaleString("es", { maximumFractionDigits: 1 }) + " %");
const money = (n) => (n == null ? "–" : "$" + Number(n).toLocaleString("en-US", { maximumFractionDigits: 0 }));
function when(s) {
  if (!s) return "–";
  const iso = /[zZ]|[+-]\d\d:?\d\d$/.test(s) ? s : s.replace(" ", "T") + "Z";   // SQLite guarda UTC sin zona
  const d = new Date(iso);
  return isNaN(d) ? s : d.toLocaleString("es", { dateStyle: "short", timeStyle: "short" });
}
function errorText(data, status) {
  const d = data && data.detail;
  if (Array.isArray(d)) return d.map((e) => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`).join(" · ");
  return typeof d === "string" ? d : `Error ${status}`;
}

async function api(path, options = {}) {
  let res;
  try { res = await fetch(state.api.replace(/\/$/, "") + path, options); }
  catch (_) { throw new Error(`No se pudo conectar con el servicio en ${state.api}. ¿Está en marcha y permitido por CORS?`); }
  let data = null;
  try { data = await res.json(); } catch (_) { /* respuesta sin cuerpo */ }
  if (!res.ok) throw new Error(errorText(data, res.status));
  return data;
}
const showError = (id, msg) => { const n = $(id); n.textContent = msg; n.hidden = !msg; };

/* ---------- estado del servicio ---------- */
async function refreshStatus() {
  try {
    const h = await api("/health");
    $("statusDot").className = "dot ok";
    $("statusText").textContent = h.active_model ? `Servicio activo · modelo ${h.active_model} · ${h.movies_in_database.toLocaleString("es")} películas` : "Servicio sin modelo activo";
    $("banner").hidden = true;
    return true;
  } catch (e) {
    $("statusDot").className = "dot err";
    $("statusText").textContent = "Sin conexión";
    $("banner").textContent = e.message; $("banner").hidden = false;
    return false;
  }
}

/* ---------- pestañas ---------- */
function showTab(name) {
  document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  document.querySelectorAll(".panel").forEach((p) => (p.hidden = p.id !== "tab-" + name));
  if (name === "history") loadHistory();
  if (name === "metrics") loadMetrics();
  if (name === "train") { loadDataset(); loadRuns(); }
}

/* ---------- predicción ---------- */
function fillSelect(select, values, placeholder) {
  select.replaceChildren(el("option", { value: "", text: placeholder }), ...values.map((v) => el("option", { value: v, text: v })));
}
async function loadOptions() {
  try {
    const o = await api("/options");
    fillSelect($("genre"), o.genres, "Elegir…");
    fillSelect($("rating"), o.ratings, "Sin especificar");
    fillSelect($("country"), o.countries, "Sin especificar");
    fillSelect($("month"), o.months, "Sin especificar");
    const y = document.querySelector('[name="year"]');
    if (!y.value) y.value = new Date().getFullYear();
  } catch (_) { /* el banner de estado ya informa */ }
}

function formPayload(form) {
  const out = {};
  for (const [k, v] of new FormData(form).entries()) {
    const t = String(v).trim();
    if (t === "") continue;
    out[k] = ["year", "runtime", "budget"].includes(k) ? Number(t) : t;
  }
  return out;
}

async function onPredict(ev) {
  ev.preventDefault();
  showError("predictError", "");
  const form = ev.target;
  if (!form.checkValidity()) { form.reportValidity(); return; }
  const btn = $("predictBtn"); btn.disabled = true; btn.textContent = "Calculando…";
  try {
    const r = await api("/predict", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(formPayload(form)) });
    $("resultEmpty").hidden = true; $("resultBody").hidden = false;
    $("scoreValue").textContent = fmt(r.predicted_score, 1);
    $("meterFill").style.width = Math.max(0, Math.min(100, r.predicted_score * 10)) + "%";
    $("resModel").textContent = r.model_version;
    $("resDirector").textContent = r.known_director == null ? "No indicado" : r.known_director ? `Sí (${r.director_previous_films} películas previas)` : "Sin historial";
    $("resBudget").textContent = r.budget_imputed ? "Estimado por el modelo" : "Informado";
    $("resWarnings").replaceChildren(...r.warnings.map((w) => el("li", { text: w })));
    state.loaded.history = false;
  } catch (e) { showError("predictError", e.message); }
  finally { btn.disabled = false; btn.textContent = "Predecir score"; }
}

function fillExample() {
  const f = $("predictForm");
  const set = (n, v) => { const i = f.elements[n]; if (!i) return; if (i.tagName === "SELECT" && ![...i.options].some((o) => o.value === v)) return; i.value = v; };
  set("name", "Mi película de ejemplo"); set("genre", "Drama"); set("year", "2021");
  set("director", "Christopher Nolan"); set("writer", "Christopher Nolan"); set("star", "Leonardo DiCaprio");
  set("company", "Warner Bros."); set("rating", "PG-13"); set("country", "United States"); set("release_month", "July");
  set("runtime", "150"); set("budget", "100000000");
}

/* ---------- historial ---------- */
async function loadHistory() {
  try {
    const p = await api(`/predictions?limit=${state.historyLimit}&offset=${state.historyOffset}`);
    const body = $("historyTable").tBodies[0];
    body.replaceChildren(...p.items.map((it) => el("tr", {},
      el("td", { text: when(it.created_at) }), el("td", { text: it.input.name || "–" }), el("td", { text: it.input.director || "–" }),
      el("td", { text: it.input.genre || "–" }), el("td", { text: it.input.year ?? "–" }), el("td", { text: money(it.input.budget) }),
      el("td", { class: "num" }, el("strong", { text: fmt(it.predicted_score, 1) })), el("td", {}, el("span", { class: "pill", text: it.model_version })))));
    $("historyEmpty").hidden = p.total > 0;
    $("historyTable").hidden = p.total === 0;
    const from = p.total ? state.historyOffset + 1 : 0, to = Math.min(state.historyOffset + state.historyLimit, p.total);
    $("historyInfo").textContent = `${from}–${to} de ${p.total}`;
    $("prevPage").disabled = state.historyOffset === 0;
    $("nextPage").disabled = to >= p.total;
  } catch (e) { $("historyInfo").textContent = e.message; }
}

/* ---------- métricas ---------- */
function kpi(label, value, vs) { return el("div", { class: "kpi" }, el("div", { class: "label", text: label }), el("div", { class: "value", text: value }), el("div", { class: "vs", text: vs })); }
function check(ok, text) { return el("li", {}, el("span", { class: "pill " + (ok ? "good" : "bad"), text: ok ? "Cumple" : "No cumple" }), " ", text); }

async function loadMetrics() {
  try {
    const m = await api("/metrics");
    const a = m.active, ev = a.evaluation, bl = a.baseline;
    $("activeVersion").textContent = a.version;
    $("metricsContext").textContent = `${a.algorithm}. Entrenado con películas de ${a.train_years[0]}–${a.train_years[1]} (${a.n_train?.toLocaleString("es")}) y evaluado en ${a.eval_years[0]}–${a.eval_years[1]} (${a.n_eval?.toLocaleString("es")}).`;
    $("kpis").replaceChildren(
      kpi("MAE (error medio)", fmt(ev.mae), `Baseline (media): ${fmt(bl.mae)}`),
      kpi("RMSE", fmt(ev.rmse), `Baseline: ${fmt(bl.rmse)}`),
      kpi("R²", fmt(ev.r2), a.cv ? `En validación cruzada: ${fmt(a.cv.r2)}` : "Varianza explicada"),
      kpi("Mejora vs baseline", pct(a.improvement_vs_baseline), "Reducción del MAE"),
      a.parent_version ? kpi(`${a.parent_version} en el mismo conjunto`, fmt(a.parent_evaluation_mae), "MAE del modelo anterior") : null);
    $("metricsNote").replaceChildren(el("strong", { text: "Criterios de aceptación definidos en la fase 1" }), el("ul", {},
      check(ev.mae <= ACCEPT.mae, `MAE ≤ ${ACCEPT.mae}`),
      check(a.improvement_vs_baseline >= ACCEPT.improvement, `Mejora ≥ ${ACCEPT.improvement * 100} % sobre el baseline`),
      check(ev.r2 >= ACCEPT.r2, `R² ≥ ${ACCEPT.r2}`)),
      a.parent_version ? el("p", { class: "muted small", text: `Este modelo se evaluó en ${a.eval_years[0]}–${a.eval_years[1]}, un conjunto distinto (y más difícil: el baseline también empeora, MAE ${fmt(bl.mae)}) que el test ciego de v1. Por eso se compara con el modelo anterior y con el baseline sobre ese mismo conjunto, no con las cifras de v1.` }) : null);
    const body = $("versionsTable").tBodies[0];
    body.replaceChildren(...m.history.map((v) => el("tr", {},
      el("td", {}, el("strong", { text: v.version })),
      el("td", {}, el("span", { class: "pill " + (v.is_active ? "good" : "gray"), text: v.is_active ? "Activo" : "Archivado" })),
      el("td", { text: `${v.train_years[0]}–${v.train_years[1]}` }), el("td", { text: `${v.eval_years[0]}–${v.eval_years[1]}` }),
      el("td", { class: "num", text: fmt(v.evaluation.mae) }), el("td", { class: "num", text: fmt(v.evaluation.rmse) }),
      el("td", { class: "num", text: fmt(v.evaluation.r2) }), el("td", { class: "num", text: fmt(v.baseline.mae) }),
      el("td", { class: "num", text: v.parent_evaluation_mae == null ? "–" : fmt(v.parent_evaluation_mae) }),
      el("td", { class: "num", text: pct(v.improvement_vs_baseline) }))));
  } catch (e) { $("metricsContext").textContent = e.message; }
}

/* ---------- datos y reentrenamiento ---------- */
async function loadDataset() {
  try {
    const d = await api("/dataset");
    const by = Object.entries(d.by_source).map(([k, v]) => `${k === "seed" ? "iniciales" : "subidas"}: ${v.toLocaleString("es")}`).join(" · ");
    $("datasetInfo").replaceChildren(el("span", { class: "pill", text: `${d.total_rows.toLocaleString("es")} películas` }),
      el("span", { class: "pill gray", text: `${d.year_min}–${d.year_max}` }), el("span", { class: "pill gray", text: by }));
  } catch (e) { $("datasetInfo").textContent = e.message; }
}

function onFileChosen() {
  const f = $("file").files[0];
  $("fileLabel").textContent = f ? `${f.name} (${(f.size / 1024).toFixed(0)} KB)` : "Elegir archivo CSV…";
  $("drop").classList.toggle("has", !!f);
  $("uploadBtn").disabled = !f;
}

async function onUpload(ev) {
  ev.preventDefault();
  showError("uploadError", ""); $("uploadReport").hidden = true;
  const f = $("file").files[0]; if (!f) return;
  const fd = new FormData(); fd.append("file", f);
  const btn = $("uploadBtn"); btn.disabled = true; btn.textContent = "Subiendo…";
  try {
    const r = await api("/training-file", { method: "POST", body: fd });
    const rep = $("uploadReport");
    rep.replaceChildren(el("strong", { text: `«${r.filename}» procesado` }), el("ul", {},
      el("li", { text: `Filas recibidas: ${r.rows_received.toLocaleString("es")}` }),
      el("li", { text: `Nuevas insertadas: ${r.rows_inserted.toLocaleString("es")}` }),
      el("li", { text: `Ya existían (omitidas): ${r.rows_duplicated.toLocaleString("es")}` }),
      el("li", { text: `Rechazadas: ${r.rows_rejected.toLocaleString("es")}${Object.keys(r.rejection_reasons).length ? " — " + Object.entries(r.rejection_reasons).map(([k, v]) => `${k}: ${v}`).join(", ") : ""}` }),
      r.ignored_columns.length ? el("li", { text: `Columnas ignoradas: ${r.ignored_columns.join(", ")}` }) : null,
      el("li", { text: `Total de películas en la base: ${r.total_rows_in_dataset.toLocaleString("es")}` })));
    rep.hidden = false;
    loadDataset(); refreshStatus();
  } catch (e) { showError("uploadError", e.message); }
  finally { btn.textContent = "Subir archivo"; btn.disabled = !$("file").files[0]; }
}

const STATUS = { pending: ["Pendiente", "gray"], running: ["Entrenando…", "warn"], succeeded: ["Completado", "good"], failed: ["Falló", "bad"] };
function statusPill(s) { const [t, c] = STATUS[s] || [s, "gray"]; return el("span", { class: "pill " + c, text: t }); }

function renderRun(run) {
  const box = $("runBox"); box.hidden = false;
  const busy = run.status === "pending" || run.status === "running";
  box.replaceChildren(
    el("div", {}, busy ? el("span", { class: "spinner" }) : null, el("strong", { text: `Reentrenamiento #${run.id} · ` }), statusPill(run.status)),
    run.message ? el("p", { class: "muted", text: run.message }) : (busy ? el("p", { class: "muted", text: "Entrenando el candidato y comparándolo con el modelo activo. Puede tardar un par de minutos." }) : null),
    run.status === "succeeded" ? el("div", {}, el("span", { class: "pill " + (run.promoted ? "good" : "gray"), text: run.promoted ? `Nuevo modelo activo: ${run.resulting_version}` : "Se conserva el modelo anterior" })) : null);
}

async function pollRun(id) {
  clearTimeout(state.pollTimer);
  try {
    const run = await api(`/retrain/${id}`);
    renderRun(run);
    if (run.status === "pending" || run.status === "running") { state.pollTimer = setTimeout(() => pollRun(id), 2000); return; }
    $("retrainBtn").disabled = false; $("retrainBtn").textContent = "Reentrenar modelo";
    loadRuns(); refreshStatus(); loadDataset();
  } catch (e) { showError("retrainError", e.message); $("retrainBtn").disabled = false; $("retrainBtn").textContent = "Reentrenar modelo"; }
}

async function onRetrain() {
  showError("retrainError", "");
  const btn = $("retrainBtn"); btn.disabled = true; btn.textContent = "Reentrenando…";
  try {
    const run = await api("/retrain", { method: "POST" });
    renderRun(run); pollRun(run.id);
  } catch (e) { showError("retrainError", e.message); btn.disabled = false; btn.textContent = "Reentrenar modelo"; }
}

async function loadRuns() {
  try {
    const runs = await api("/retrain");
    $("runsEmpty").hidden = runs.length > 0; $("runsTable").hidden = runs.length === 0;
    $("runsTable").tBodies[0].replaceChildren(...runs.map((r) => el("tr", {},
      el("td", { text: r.id }), el("td", { text: when(r.started_at) }), el("td", {}, statusPill(r.status)),
      el("td", { class: "num", text: r.total_rows?.toLocaleString("es") ?? "–" }), el("td", { text: r.resulting_version || "–" }),
      el("td", { text: r.promoted == null ? "–" : r.promoted ? "Sí" : "No" }), el("td", { class: "wrap-cell", text: r.message || "" }))));
    const active = runs.find((r) => r.status === "pending" || r.status === "running");
    if (active && !state.pollTimer) { $("retrainBtn").disabled = true; renderRun(active); pollRun(active.id); }
  } catch (_) { /* silencioso: el banner informa */ }
}

/* ---------- configuración de la API ---------- */
function setupSettings() {
  const dlg = $("settings");
  $("settingsBtn").addEventListener("click", () => { $("apiUrl").value = state.api; dlg.showModal(); });
  dlg.addEventListener("close", async () => {
    if (dlg.returnValue === "ok" && $("apiUrl").value) {
      state.api = $("apiUrl").value.trim();
      try { localStorage.setItem("apiBase", state.api); } catch (_) { /* ignorar */ }
      if (await refreshStatus()) { loadOptions(); }
    }
  });
}

/* ---------- inicio ---------- */
document.addEventListener("DOMContentLoaded", async () => {
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
  $("predictForm").addEventListener("submit", onPredict);
  $("exampleBtn").addEventListener("click", fillExample);
  $("refreshHistory").addEventListener("click", loadHistory);
  $("prevPage").addEventListener("click", () => { state.historyOffset = Math.max(0, state.historyOffset - state.historyLimit); loadHistory(); });
  $("nextPage").addEventListener("click", () => { state.historyOffset += state.historyLimit; loadHistory(); });
  $("refreshMetrics").addEventListener("click", loadMetrics);
  $("file").addEventListener("change", onFileChosen);
  $("uploadForm").addEventListener("submit", onUpload);
  $("retrainBtn").addEventListener("click", onRetrain);
  setupSettings();
  if (await refreshStatus()) loadOptions();
});
