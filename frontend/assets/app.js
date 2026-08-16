/* Argus dashboard - agentic blockchain investigation UI */
"use strict";

const $ = (sel) => document.querySelector(sel);

const state = {
  investigationId: null,
  timer: null,
  pollMs: 900,
  maxPolls: 400,
};

const severityMeta = {
  informational: "info",
  low: "warn",
  medium: "medium",
  high: "danger",
};

/* ------------------------------------------------------------------ */
/* health check                                                        */
/* ------------------------------------------------------------------ */
async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    const body = await res.json();
    const connected = body.rpc && body.rpc.connected;
    $("#rpc-dot").className = "status-dot " + (connected ? "ok" : "bad");
    $("#rpc-label").textContent = connected
      ? `RPC online · ${body.rpc.chain} · ${body.rpc.indexer}`
      : `RPC offline · ${(body.rpc && body.rpc.error) || "unconfigured"}`;
  } catch (err) {
    $("#rpc-dot").className = "status-dot bad";
    $("#rpc-label").textContent = "API unreachable";
  }
}

/* ------------------------------------------------------------------ */
/* investigation lifecycle                                             */
/* ------------------------------------------------------------------ */
function shortHash(h) {
  if (!h) return "";
  return h.length > 20 ? h.slice(0, 10) + "\u2026" + h.slice(-8) : h;
}

function parseAddress(queryText) {
  const m = String(queryText || "").match(/\b0x[a-fA-F0-9]{40}\b/);
  return m ? m[0] : "";
}

async function startInvestigation() {
  const query = $("#query").value.trim();
  const address = $("#address").value.trim() || parseAddress(query);

  if (!query) return showError("Enter an investigation request.");
  if (!address) return showError("Provide an address, or embed 0x\u2026 in the query.");

  clearError();
  $("#run").disabled = true;
  resetExecutionView();

  try {
    const res = await fetch("/api/investigate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, address }),
    });
    const body = await res.json();
    if (!res.ok) return showError(body.detail || "Failed to start investigation");

    state.investigationId = body.investigation_id;
    $("#execution").hidden = false;
    $("#empty-state").hidden = true;
    $("#subject").textContent = address;
    setStatus("running", "queued");
    beginPolling();
  } catch (err) {
    showError("Could not reach the API.");
  } finally {
    $("#run").disabled = false;
  }
}

function beginPolling() {
  clearTimeout(state.timer);
  const tick = async () => {
    try {
      const res = await fetch(`/api/investigation/${state.investigationId}`);
      if (res.status === 404) {
        setStatus("failed", "not found");
        return;
      }
      const record = await res.json();
      render(record);
      if (record.status === "completed" || record.status === "failed") {
        setStatus(record.status, record.status);
        return;
      }
    } catch (err) {
      /* transient - keep polling */
    }
    state.timer = setTimeout(tick, state.pollMs);
  };
  tick();
}

/* ------------------------------------------------------------------ */
/* rendering                                                           */
/* ------------------------------------------------------------------ */
function resetExecutionView() {
  $("#timeline").innerHTML = "";
  $("#findings").innerHTML = "";
  $("#no-findings").hidden = true;
  $("#tx-table tbody").innerHTML = "";
  $("#evidence-list").innerHTML = "";
  $("#report-body").innerHTML = "";
  $("#exec-title").textContent = "Investigation";
}

function setStatus(status, label) {
  const pill = $("#status-pill");
  pill.className = "status-pill " + status;
  pill.textContent = label || status;
}

function renderTimeline(events) {
  const list = $("#timeline");
  list.innerHTML = "";
  for (const ev of (events || [])) {
    const li = document.createElement("li");
    li.className = "kind-" + (ev.kind || "info");
    const time = new Date(ev.timestamp).toLocaleTimeString();
    li.innerHTML =
      `<span class="t-time">${time}</span>` +
      `<span class="t-actor">${esc(ev.actor)}</span> ${esc(ev.message)}`;
    list.appendChild(li);
  }
  const last = list.lastElementChild;
  if (last) last.scrollIntoView({ block: "nearest" });
}

function renderFindings(findings) {
  const wrap = $("#findings");
  wrap.innerHTML = "";
  if (!findings || findings.length === 0) {
    $("#no-findings").hidden = false;
    return;
  }
  $("#no-findings").hidden = true;
  for (const f of findings) {
    const el = document.createElement("div");
    const sev = severityMeta[f.severity] || "info";
    el.className = `finding sev-${f.severity}`;
    el.innerHTML =
      `<div class="f-head">` +
      `<span class="sev-badge">${esc(f.severity)}</span>` +
      `<span class="f-title">${esc(f.title)}</span>` +
      `<span class="f-id">${esc(f.id)}</span>` +
      `</div>` +
      `<div class="f-desc">${esc(f.description)}</div>` +
      (f.evidence_ids && f.evidence_ids.length
        ? `<div class="f-ev">${f.evidence_ids.map((id) => esc(id)).join(" \u00b7 ")}</div>`
        : "");
    wrap.appendChild(el);
  }
}

function renderTransactions(record) {
  const body = $("#tx-table tbody");
  body.innerHTML = "";
  const subject = record.address.toLowerCase();
  const txs = (record.evidence || []).filter((e) => e.type === "transaction");

  for (const e of txs) {
    const meta = e.metadata || {};
    const direction = meta.to && meta.to.toLowerCase() === subject ? "in" : "out";
    const counterparty = direction === "in" ? meta.from : meta.to || "contract creation";
    const status = meta.status === 0 ? "reverted" : meta.status === 1 ? "ok" : "pending";
    const value = e.value_eth !== null && e.value_eth !== undefined
      ? e.value_eth.toFixed(4)
      : "\u2014";

    const row = document.createElement("tr");
    row.innerHTML =
      `<td class="hash" title="${esc(e.transaction_hash || "")}">${esc(shortHash(e.transaction_hash))}</td>` +
      `<td><span class="tag ${direction}">${direction}</span></td>` +
      `<td class="hash" title="${esc(counterparty)}">${esc(shortHash(counterparty))}</td>` +
      `<td>${esc(value)}</td>` +
      `<td>${esc(e.block_number ?? "\u2014")}</td>` +
      `<td><span class="tag ${status === "reverted" ? "reverted" : "eth"}">${status}</span></td>` +
      `<td><span class="tag eth">${esc(e.id)}</span></td>`;
    body.appendChild(row);
  }
}

function renderEvidence(evidence) {
  const list = $("#evidence-list");
  list.innerHTML = "";
  for (const e of (evidence || [])) {
    const li = document.createElement("li");
    li.innerHTML =
      `<span class="e-id">${esc(e.id)}</span>` +
      `<span class="e-desc">${esc(e.description)}</span>` +
      `<span class="e-src">${esc(e.source)}</span>`;
    list.appendChild(li);
  }
}

function renderReport(report) {
  const wrap = $("#report-body");
  if (!report) {
    wrap.innerHTML = `<p class="empty">Report pending&hellip;</p>`;
    return;
  }
  $("#exec-title").textContent = `Investigation report \u00b7 ${shortHash(report.subject)}`;
  let html = `<h3 class="section-head">Executive summary</h3><div class="exec">${esc(report.executive_summary).replace(/\n/g, "<br/>")}</div>`;

  for (const sec of report.sections || []) {
    if (sec.title === "Evidence" && !(sec.bullets || []).length) continue;
    html += `<h3 class="section-head">${esc(sec.title)}</h3>`;
    if (sec.narrative) html += `<p>${esc(sec.narrative)}</p>`;
    if (sec.bullets && sec.bullets.length) {
      html += "<ul>";
      for (const b of sec.bullets) html += `<li>${renderBullet(b)}</li>`;
      html += "</ul>";
    }
  }
  if (report.limitations && report.limitations.length) {
    html += `<h3 class="section-head">Limitations</h3><ul>`;
    for (const l of report.limitations) html += `<li>${esc(l)}</li>`;
    html += `</ul>`;
  }
  wrap.innerHTML = html;
}

function renderBullet(bullet) {
  // highlight EVID refs inside bullet text
  return esc(bullet).replace(/EVID-\d{4}/g, (m) => `<code>${m}</code>`);
}

function render(record) {
  renderTimeline(record.events);
  renderFindings(record.findings);
  renderTransactions(record);
  renderEvidence(record.evidence);
  renderReport(record.report);
  setStatus(record.status, record.status);
}

/* ------------------------------------------------------------------ */
/* helpers                                                             */
/* ------------------------------------------------------------------ */
function esc(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "" : String(value);
  return div.innerHTML;
}

function showError(msg) {
  const el = $("#api-error");
  el.textContent = msg;
  el.hidden = false;
}
function clearError() {
  $("#api-error").hidden = true;
  $("#api-error").textContent = "";
}

/* ------------------------------------------------------------------ */
/* bootstrap                                                            */
/* ------------------------------------------------------------------ */
document.addEventListener("DOMContentLoaded", () => {
  checkHealth();
  $("#run").addEventListener("click", startInvestigation);
  $("#query").addEventListener("input", () => {
    if (!$("#address").value.trim()) {
      $("#address").value = parseAddress($("#query").value);
    }
  });
  const stored = localStorage.getItem("argus:address");
  if (stored) $("#address").value = stored;
  $("#address").addEventListener("input", () => {
    localStorage.setItem("argus:address", $("#address").value.trim());
  });
  setInterval(checkHealth, 15000);
});
