/* Lesotho X-Road Member Onboarding Portal - single-page client for /api/v1 */
(function () {
  "use strict";

  const S = { user: null, member: null, model: null };
  const LOGO = "/static/img/coat-of-arms.svg";
  const STATUS = {
    locked: "Locked", not_started: "Not started", draft: "In preparation", in_review: "In review",
    returned: "Returned", approved: "Approved"
  };
  const $ = (sel, el) => (el || document).querySelector(sel);
  const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));

  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }
  function fmtDate(ts) {
    if (!ts) return "";
    const d = new Date(ts);
    if (isNaN(d)) return esc(ts);
    return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) + " " +
      d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  }
  function chip(status, label) {
    return `<span class="chip ${esc(status)}">${esc(label || STATUS[status] || status)}</span>`;
  }
  function roleLabel(r) { return (S.model && S.model.roles[r] && S.model.roles[r].label) || r; }
  function stageDef(k) { return S.model.stages.find(s => s.key === k); }

  function toast(msg, bad) {
    const t = document.createElement("div");
    t.className = "toast" + (bad ? " bad" : "");
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), bad ? 6000 : 3000);
  }

  class ApiError extends Error {
    constructor(status, body) { super(body.error || "Request failed"); this.status = status; this.body = body; }
  }
  async function api(method, path, data, isForm) {
    const opts = { method, headers: { "X-Requested-With": "portal" }, credentials: "same-origin" };
    if (data !== undefined) {
      if (isForm) opts.body = data;
      else { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(data); }
    }
    const r = await fetch("/api/v1" + path, opts);
    let body = {};
    try { body = await r.json(); } catch (e) { /* non-JSON */ }
    if (r.status === 401 && path !== "/auth/login" && path !== "/auth/me") { S.user = null; renderLogin(); throw new ApiError(401, body); }
    if (!r.ok) throw new ApiError(r.status, body);
    return body;
  }

  // ======================================================================= login
  async function renderLogin(msg) {
    document.title = "Sign in · X-Road Member Onboarding Portal";
    const app = $("#app");
    app.innerHTML = `
    <div class="login">
      <section class="login-side">
        <div class="brand-w"><img src="${LOGO}" alt="Coat of arms of Lesotho">
          <div><b>MICSTI</b>Ministry of Information, Communications,<br>Science, Technology and Innovation</div></div>
        <h1>X-Road Member Onboarding Portal</h1>
        <p class="lede">One guided path for line ministries to join Lesotho's National Data Exchange. The legal,
          organisational and semantic layers are settled online first; technical onboarding follows CF-001's
          secure onboarding procedure.</p>
        <ol>
          <li><b>1 · Agree</b>Standard agreement and service schedule</li>
          <li><b>2 · Register</b>Nominations, semantics, RA-003, RA-001</li>
          <li><b>3 · Install</b>Security server in the ministry's own segment</li>
          <li><b>4 · Certify</b>Keys in HSM or token; custody recorded</li>
          <li><b>5 · Connect</b>Access rights and synthetic-data tests</li>
          <li><b>6 · Go live</b>DPIA accepted; Committee recommendation</li>
        </ol>
        <div class="foot">National Data Exchange (X-Road) Pilot · MICSTI with UNICEF and the National University of
          Lesotho · Whole-of-Government Interoperability Framework</div>
      </section>
      <section class="login-main">
        <div class="login-card">
          <h2 style="font-size:20px">Sign in</h2>
          <p class="muted">Use your portal account. This is a demonstration environment with synthetic data only.</p>
          <form id="loginForm" autocomplete="on">
            <div class="field"><label for="u">Username</label><input id="u" type="text" autocomplete="username" required></div>
            <div class="field"><label for="p">Password</label><input id="p" type="password" autocomplete="current-password" required></div>
            <div class="err" id="loginErr">${esc(msg || "")}</div>
            <button class="btn primary" style="width:100%;justify-content:center;padding:10px">Sign in</button>
          </form>
        </div>
        <div class="demo-list" id="demoList"><div class="empty">Loading demonstration accounts...</div></div>
      </section>
    </div>`;
    $("#loginForm").addEventListener("submit", async e => {
      e.preventDefault();
      try {
        await api("POST", "/auth/login", { username: $("#u").value, password: $("#p").value });
        location.hash = "#/";
        await boot();
      } catch (err) { $("#loginErr").textContent = err.message; }
    });
    try {
      const d = await api("GET", "/auth/demo-accounts");
      $("#demoList").innerHTML = `<table class="t"><thead><tr><th colspan="3">Demonstration accounts · password
        <span class="mono">${esc(d.password)}</span> · click to fill</th></tr></thead><tbody>${
        d.accounts.map(a => `<tr class="click" data-u="${esc(a.username)}" data-p="${esc(d.password)}">
          <td class="mono">${esc(a.username)}</td><td>${esc(a.role_label)}</td>
          <td class="muted">${esc(a.member === "MICSTI" ? "MICSTI / Committees" : a.member)}</td></tr>`).join("")}
        </tbody></table>`;
      $$("#demoList tr.click").forEach(tr => tr.addEventListener("click", () => {
        $("#u").value = tr.dataset.u; $("#p").value = tr.dataset.p; $("#p").focus();
      }));
    } catch (e) { $("#demoList").remove(); }
  }

  // ======================================================================= shell
  function renderShell() {
    const u = S.user, op = u.is_operator;
    const nav = [
      ["#/", "Dashboard", "dash"],
      ["#/tasks", "My tasks", "tasks"],
      op ? ["#/members", "Member status", "members"] : ["#/members/" + u.member_id, "Onboarding path", "members"],
      null,
      ["#/catalogue", "Service catalogue", "catalogue"],
      ["#/nominations", "Nominations register", "nominations"],
      ["#/guidance", "Templates & guidance", "guidance"],
      ["#/audit", "Audit trail", "audit"],
      ["#/api", "REST API", "api"],
    ];
    $("#app").innerHTML = `
    <header class="topbar"><div class="topbar-inner">
      <a class="brand" href="#/"><img src="${LOGO}" alt="Coat of arms of Lesotho">
        <div class="org"><b>MICSTI</b>Ministry of Information, Communications, Science, Technology and Innovation</div></a>
      <div class="brand-divider"></div>
      <div class="app-title">X-Road Member Onboarding Portal<span>National Data Exchange · Kingdom of Lesotho</span></div>
      <div class="spacer"></div>
      <div class="userbox"><b>${esc(u.full_name)}</b>${esc(u.role_label)}${S.member && !op ? " · " + esc(S.member.short) : ""}</div>
      <button class="btn sm" id="logout">Sign out</button>
    </div><div class="flag"></div></header>
    <div class="demo-banner">Demonstration environment · ICT Cadre Management Workshop, 24 November 2026 ·
      synthetic data only, no personal data from any ministry system</div>
    <div class="layout">
      <nav class="sidebar"><div class="nav">
        <div class="nav-label">${op ? "Operator & governance" : "My ministry"}</div>
        ${nav.map(n => n ? `<a href="${n[0]}" data-nav="${n[2]}">${n[1]}${n[2] === "tasks" ?
          '<span class="count" id="taskCount" hidden></span>' : ""}</a>` : '<div class="nav-label">Registers</div>').join("")}
      </div></nav>
      <main class="main" id="main"></main>
    </div>`;
    $("#main").addEventListener("click", e => {
      const rm = e.target.closest("[data-rm]");
      if (rm) rm.closest("tr").remove();
    });
    $("#logout").addEventListener("click", async () => {
      await api("POST", "/auth/logout").catch(() => {});
      S.user = null; location.hash = ""; renderLogin();
    });
  }

  function setNav(key) {
    $$(".nav a").forEach(a => a.classList.toggle("active", a.dataset.nav === key));
  }
  async function refreshTaskCount() {
    try {
      const d = await api("GET", "/tasks");
      const el = $("#taskCount");
      if (el) { el.textContent = d.tasks.length; el.hidden = !d.tasks.length; }
    } catch (e) { /* ignore */ }
  }

  // ======================================================================= shared fragments
  function progressBar(stages) {
    return `<div class="bar" title="Stages 1-6: pre-technical · 7-10: technical">${stages.map((s, i) =>
      (i === 6 ? '<i class="sep"></i>' : "") + `<i class="${esc(s.status)}" title="${esc(stageDef(s.key).no + ". " +
        stageDef(s.key).title + " - " + (STATUS[s.status] || s.status))}"></i>`).join("")}</div>`;
  }
  function currentCell(m) {
    if (!m.current) return chip("approved", "Complete");
    const aw = m.current.awaiting ? `<div class="small muted">Awaiting ${esc(roleLabel(m.current.awaiting))}</div>` : "";
    return `<div>${m.current.no}. ${esc(m.current.title)} ${chip(m.current.status)}</div>${aw}`;
  }
  function taskList(tasks, emptyMsg) {
    if (!tasks.length) return `<div class="empty">${esc(emptyMsg || "Nothing is waiting for you.")}</div>`;
    return tasks.map(t => `<a class="task" href="#/members/${t.member_id}/${t.stage}">
      <div class="tn ${t.kind}">${t.stage_no}</div>
      <div class="tx"><div><b>${esc(t.title)}</b> · ${esc(t.member)}</div>
        <div class="small muted">${t.kind === "review" ? "Submitted " : "Updated "}${fmtDate(t.since)}</div></div>
      <span class="btn sm ${t.kind === "review" ? "primary" : ""}">${esc(t.action)}</span></a>`).join("");
  }
  function pathView(m) {
    const card = s => {
      const d = stageDef(s.key);
      const aw = s.awaiting ? `<div class="small muted">Awaiting ${esc(roleLabel(s.awaiting))}</div>` : "";
      return `<a class="step ${esc(s.status)}" href="#/members/${m.id}/${s.key}">
        <div class="no">Stage ${d.no} · ${esc(d.layer)}</div><div class="tt">${esc(d.title)}</div>
        <div class="small muted">${esc(d.subtitle)}</div><div class="st">${chip(s.status)}${aw}</div></a>`;
    };
    return `
      <div class="phase"><div class="phase-head"><h2>Phase A · Pre-technical readiness</h2>
        <span class="muted small">Legal, organisational and semantic layers, use case and MIS readiness, then clearance</span></div>
        <div class="path">${m.stages.slice(0, 6).map(card).join("")}</div></div>
      <div class="phase"><div class="phase-head"><h2>Phase B · Technical onboarding on X-Road</h2>
        <span class="muted small">Install, Certify, Connect and Go live (CF-001 secure onboarding)</span></div>
        <div class="path b">${m.stages.slice(6).map(card).join("")}</div></div>`;
  }

  // ======================================================================= pages
  async function pageDashboard() {
    setNav("dash");
    const d = await api("GET", "/dashboard");
    const main = $("#main");
    if (S.user.is_operator) {
      const k = d.kpis;
      main.innerHTML = `
        <div class="page-head"><div><h1>Onboarding overview</h1>
          <div class="muted">Status of every ministry on the guided path to X-Road go-live</div></div>
          ${S.user.role === "admin" ? '<button class="btn danger" id="reset">Reset demonstration data</button>' : ""}</div>
        <div class="kpis">
          <div class="kpi"><div class="v">${k.members}</div><div class="l">Ministries onboarding</div></div>
          <div class="kpi"><div class="v">${k.in_review}</div><div class="l">Submissions in review</div></div>
          <div class="kpi"><div class="v">${k.cleared}</div><div class="l">Cleared for technical onboarding</div></div>
          <div class="kpi"><div class="v">${k.live}</div><div class="l">Live on X-Road</div></div>
          <div class="kpi"><div class="v">${k.services}</div><div class="l">Services in catalogue</div></div>
        </div>
        <div class="grid g-main">
          <div class="card tight"><div class="card-head"><h2>Member status</h2>
            <span class="small muted">Click a ministry for its onboarding path</span></div>
            ${memberTable(d.members)}</div>
          <div class="card tight"><div class="card-head"><h2>Awaiting your action</h2></div>
            ${taskList(d.tasks, "No submissions are awaiting your decision.")}</div>
        </div>`;
      wireMemberTable();
      const rb = $("#reset");
      if (rb) rb.addEventListener("click", async () => {
        if (!confirm("Reset all demonstration data to the initial synthetic state? You will be signed out.")) return;
        await api("POST", "/admin/reset"); S.user = null; location.hash = ""; renderLogin("Demonstration data reset.");
      });
    } else {
      const m = d.members[0];
      main.innerHTML = `
        <div class="page-head"><div><h1>${esc(m.name)}</h1>
          <div class="muted">Member code <span class="mono">${esc(m.member_class)}/${esc(m.code)}</span> ·
            ${esc(m.systems)} · ${esc(m.wave)}</div></div>
          <div>${chip(m.overall === "Live on X-Road" ? "approved" : m.overall === "Not started" ? "locked" : "in_review", m.overall)}</div></div>
        <div class="grid g-main">
          <div>
            <div class="card"><div style="display:flex;justify-content:space-between;margin-bottom:8px">
              <b>${m.approved} of ${m.total} stages approved</b>
              <span class="muted small">Each gate must pass before the next stage begins</span></div>
              ${progressBar(m.stages)}</div>
            ${pathView(m)}
          </div>
          <div class="card tight"><div class="card-head"><h2>Your tasks</h2></div>
            ${taskList(d.tasks, "Nothing is waiting for you. Submissions are with the reviewers.")}</div>
        </div>`;
    }
  }

  function memberTable(ms) {
    return `<table class="t"><thead><tr><th>Ministry</th><th style="width:210px">Progress</th><th>Current stage</th>
      </tr></thead><tbody>${ms.map(m => `<tr class="click" data-href="#/members/${m.id}">
      <td><b>${esc(m.short)}</b><div class="small muted">${esc(m.systems)} · ${esc(m.wave)}</div></td>
      <td>${progressBar(m.stages)}<div class="small muted" style="margin-top:4px">${m.approved}/${m.total} · ${esc(m.overall)}</div></td>
      <td>${currentCell(m)}</td></tr>`).join("")}</tbody></table>`;
  }
  function wireMemberTable() {
    $$("tr.click[data-href]").forEach(tr => tr.addEventListener("click", () => { location.hash = tr.dataset.href; }));
  }

  async function pageMembers() {
    setNav("members");
    const d = await api("GET", "/members");
    $("#main").innerHTML = `<div class="page-head"><div><h1>Member status</h1>
      <div class="muted">Status view per member across all ten gated stages</div></div></div>
      <div class="card tight">${memberTable(d.members)}</div>
      <div class="small muted">Legend: ${["approved", "in_review", "draft", "returned"].map(s => chip(s)).join(" ")}
        ${chip("locked", "Not started / locked")}</div>`;
    wireMemberTable();
  }

  async function pageMember(id) {
    setNav("members");
    const { member: m } = await api("GET", "/members/" + id);
    $("#main").innerHTML = `
      <div class="crumbs">${S.user.is_operator ? '<a href="#/members">Member status</a> / ' : ""}${esc(m.short)}</div>
      <div class="page-head"><div><h1>${esc(m.name)}</h1>
        <div class="muted">Member code <span class="mono">${esc(m.member_class)}/${esc(m.code)}</span> · ${esc(m.systems)}
          · ${esc(m.wave)}</div></div>
        <div class="actions"><a class="btn" href="/api/v1/members/${m.id}/agreement" target="_blank" rel="noopener">
          View agreement & service schedule</a>${S.user.is_operator ? `<a class="btn" href="#/audit?member=${m.id}">Audit trail</a>` : ""}</div></div>
      <div class="card"><div style="display:flex;justify-content:space-between;margin-bottom:8px">
        <b>${m.approved} of ${m.total} stages approved · ${esc(m.overall)}</b></div>${progressBar(m.stages)}</div>
      ${pathView(m)}`;
  }

  // ----------------------------------------------------------------------- stage workspace
  async function pageStage(mid, key) {
    setNav("members");
    const d = await api("GET", `/members/${mid}/stages/${key}`);
    renderStage(d);
  }

  function renderStage(d) {
    const s = stageDef(d.stage), rec = d.record, edit = d.can_edit;
    const data = rec.data || {}, chk = rec.checklist || {};
    const last = d.decisions.filter(x => x.action === "returned").pop();
    const noticeReturned = rec.status === "returned" && last ? `<div class="notice returned"><b>Returned for revision by
      ${esc(last.full_name)} (${esc(last.role_label)})</b><div>${esc(last.comment)}</div></div>` : "";
    const noticeLocked = rec.status === "locked" ? `<div class="notice info">This stage unlocks when stage
      ${s.no - 1} (${esc(stageDef(S.model.stages[s.no - 2].key).title)}) is approved.</div>` : "";
    const noticeReview = rec.status === "in_review" && !d.can_decide ? `<div class="notice info">Submitted
      ${fmtDate(rec.submitted_at)} · awaiting <b>${esc(d.awaiting_label)}</b>.</div>` : "";

    $("#main").innerHTML = `
      <div class="crumbs">${S.user.is_operator ? '<a href="#/members">Member status</a> / ' : ""}<a href="#/members/${d.member.id}">${esc(d.member.short)}</a> / Stage ${s.no}</div>
      <div class="page-head"><div>
        <div class="actions" style="margin-bottom:6px"><span class="chip layer">${esc(s.layer)} layer</span>
          <span class="chip layer">Portal step: ${esc(s.step)}</span><span class="chip layer">Phase ${s.phase}</span></div>
        <h1>${s.no}. ${esc(s.title)}</h1><div class="muted">${esc(s.subtitle)} · ${esc(d.member.name)}</div></div>
        <div>${chip(rec.status)}</div></div>
      ${noticeReturned}${noticeLocked}${noticeReview}
      <div class="grid g-main">
        <div>
          <div class="card"><div class="gate"><b>${esc(s.question)}</b><div><b>Gate:</b> ${esc(s.gate)}</div></div></div>
          ${rec.status === "locked" ? "" : `
          <form id="stageForm">
            <div class="card"><h2>Submission</h2><div class="form">${s.fields.map(f => renderField(f, data[f.name], edit, d)).join("")}</div></div>
            <div class="card"><h2>Gate checklist</h2><div class="checks">${s.checklist.map(c => `<label>
              <input type="checkbox" name="chk_${c.id}" ${chk[c.id] ? "checked" : ""} ${edit ? "" : "disabled"}>
              <span>${esc(c.label)}</span></label>`).join("")}</div></div>
          </form>
          ${docsCard(s, d, edit)}
          ${edit ? `<div class="card">${issuesBox(d.issues)}
            <div class="actions" style="margin-top:14px"><button class="btn" id="saveBtn">Save draft</button>
            <button class="btn primary" id="submitBtn">Submit to ${esc(roleLabel(s.chain[0]))}</button></div></div>` : ""}
          ${d.can_decide ? decisionCard(s, d) : ""}`}
        </div>
        <aside>
          <div class="card"><h2>Approval chain</h2>${chainView(s, d)}</div>
          <div class="card"><h2>History</h2>${historyView(d.decisions)}</div>
          ${s.key === "legal" ? `<div class="card"><h3>Agreement template</h3><p class="small muted">The standard
            X-Road member agreement and service schedule, pre-filled from this submission.</p>
            <a class="btn sm" target="_blank" rel="noopener" href="/api/v1/members/${d.member.id}/agreement">Open agreement</a></div>` : ""}
        </aside>
      </div>`;
    wireStage(s, d);
  }

  function issuesBox(issues) {
    if (!issues.length) return `<div class="issues ok"><b>Gate met.</b> All required information, confirmations and evidence are in place.</div>`;
    return `<div class="issues"><b>Before you can submit (${issues.length})</b><ul>${issues.map(i => `<li>${esc(i)}</li>`).join("")}</ul></div>`;
  }

  function chainView(s, d) {
    const rec = d.record;
    const sub = d.decisions.filter(x => x.action === "submitted").pop();
    const lastSubIdx = sub ? d.decisions.lastIndexOf(sub) : -1;
    const after = lastSubIdx >= 0 ? d.decisions.slice(lastSubIdx + 1) : [];
    const items = [`<div class="c ${sub ? "done" : (rec.status === "locked" ? "" : "now")}"><div class="dot">${sub ? "✓" : "1"}</div>
      <div><div class="who">Prepared by ${esc(s.submitters.map(roleLabel).join(" / "))}</div>
      <div class="when">${sub ? esc(sub.full_name) + " · " + fmtDate(sub.created_at) : "Not yet submitted"}</div></div></div>`];
    s.chain.forEach((role, i) => {
      const dec = after.find(x => x.role === role);
      let cls = "", mark = String(i + 2), when = "Pending";
      if (dec && dec.action === "returned") { cls = "back"; mark = "!"; when = "Returned · " + esc(dec.full_name) + " · " + fmtDate(dec.created_at); }
      else if (dec) { cls = "done"; mark = "✓"; when = esc(dec.action[0].toUpperCase() + dec.action.slice(1)) + " · " + esc(dec.full_name) + " · " + fmtDate(dec.created_at); }
      else if (rec.status === "in_review" && rec.level === i) { cls = "now"; when = "Awaiting decision"; }
      items.push(`<div class="c ${cls}"><div class="dot">${mark}</div><div><div class="who">${esc(roleLabel(role))}</div>
        <div class="when">${when}</div></div></div>`);
    });
    return `<div class="chain">${items.join("")}</div>`;
  }

  function historyView(decs) {
    if (!decs.length) return `<div class="muted small">No activity yet.</div>`;
    return `<ul class="timeline">${decs.slice().reverse().map(x => `<li class="${esc(x.action)}">
      <div><b>${esc(x.action[0].toUpperCase() + x.action.slice(1))}</b> · ${esc(x.full_name)}</div>
      <div class="small muted">${esc(x.role_label)} · ${fmtDate(x.created_at)}</div>
      ${x.comment ? `<div class="cm">${esc(x.comment)}</div>` : ""}</li>`).join("")}</ul>`;
  }

  function decisionCard(s, d) {
    const role = S.user.role;
    const verb = { mda_ps: "Endorse", tc: "Recommend", sc: "Approve" }[role] || "Approve";
    const lastStep = d.record.level === s.chain.length - 1;
    const hint = lastStep ? "This is the final decision for the gate. Approval unlocks the next stage."
      : "On endorsement, the submission moves to " + roleLabel(s.chain[d.record.level + 1]) + ".";
    return `<div class="card" style="border-color:#bcd0f2"><h2>Your decision · ${esc(roleLabel(role))}</h2>
      <p class="small muted">${esc(hint)} Review the submission, checklist and evidence above.</p>
      ${issuesBox(d.issues)}
      <div class="field" style="margin-top:12px"><label for="decComment">Comment <span class="muted small">(required when returning)</span></label>
        <textarea id="decComment" placeholder="Reasoning, conditions or required changes"></textarea></div>
      <div class="actions" style="margin-top:12px"><button class="btn ok" id="approveBtn">${verb}${lastStep ? " - gate passed" : ""}</button>
        <button class="btn danger" id="returnBtn">Return for revision</button></div></div>`;
  }

  function docsCard(s, d, edit) {
    const byType = {};
    d.documents.forEach(x => (byType[x.doc_type] = byType[x.doc_type] || []).push(x));
    const rows = s.documents.map(t => {
      const docs = byType[t.type] || [];
      const status = docs.length ? chip("approved", "Uploaded") : (t.required ? chip("returned", "Required") : chip("locked", "Optional"));
      return `<div style="margin-bottom:6px"><div style="display:flex;justify-content:space-between;gap:8px;padding-top:8px">
        <b>${esc(t.label)}</b>${status}</div>
        <div class="docs">${docs.map(x => `<div class="doc"><div class="ic">${esc((x.filename.split(".").pop() || "").toUpperCase().slice(0, 4))}</div>
          <div class="meta"><div><a href="/api/v1/documents/${x.id}">${esc(x.filename)}</a></div>
          <div class="small muted">Evidence level ${x.evidence_level} · ${(x.size / 1024).toFixed(1)} KB · ${esc(x.uploaded_by_name || "")} · ${fmtDate(x.uploaded_at)}</div></div>
          ${edit ? `<button class="btn sm danger" data-del="${x.id}">Remove</button>` : ""}</div>`).join("")}</div></div>`;
    }).join("");
    const up = edit ? `<form class="upload" id="uploadForm">
      <select name="doc_type" required>${s.documents.map(t => `<option value="${esc(t.type)}">${esc(t.label)}</option>`).join("")}</select>
      <select name="evidence_level"><option value="1">Level 1 · self-reported</option><option value="2" selected>Level 2 · facilitated</option>
        <option value="3">Level 3 · verified</option></select>
      <input class="full" type="file" name="file" required>
      <div class="full small muted">PDF, Office, image, text, CSV, JSON or YAML; up to 10 MB. Synthetic documents only.</div>
      <div class="full"><button class="btn">Upload evidence</button></div></form>` : "";
    return `<div class="card"><h2>Evidence</h2>${rows}${up}</div>`;
  }

  // ----------------------------------------------------------------------- field renderers
  function renderField(f, v, edit, d) {
    const dis = edit ? "" : "disabled";
    const req = f.required ? ' <span class="req">*</span>' : "";
    const help = f.help ? `<div class="help">${esc(f.help)}</div>` : "";
    const id = "f_" + f.name;
    let input, wide = ["textarea", "multiselect", "nominations", "services", "ra001", "ra003"].includes(f.type);
    switch (f.type) {
      case "textarea":
        input = `<textarea id="${id}" name="${f.name}" ${dis}>${esc(v)}</textarea>`; break;
      case "select":
        input = `<select id="${id}" name="${f.name}" ${dis}><option value="">Select...</option>${f.options.map(o =>
          `<option ${o === v ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`; break;
      case "multiselect":
        input = `<div class="multi" data-multi="${f.name}">${f.options.map(o => `<label><input type="checkbox" value="${esc(o)}"
          ${(v || []).includes(o) ? "checked" : ""} ${dis}><span>${esc(o)}</span></label>`).join("")}</div>`; break;
      case "number": case "date":
        input = `<input id="${id}" type="${f.type}" name="${f.name}" value="${esc(v)}" ${dis}>`; break;
      case "nominations": input = nominationsTable(v || [], edit); break;
      case "services": input = servicesTable(v || [], edit); break;
      case "ra001": input = ra001Form(v || {}, edit); break;
      case "ra003": input = ra003Form(v || {}, edit); break;
      default:
        input = `<input id="${id}" type="text" name="${f.name}" value="${esc(v)}" ${dis}>`;
    }
    return `<div class="field ${wide ? "wide" : ""}"><label for="${id}">${esc(f.label)}${req}</label>${input}${help}</div>`;
  }

  function nomRow(n, edit) {
    const dis = edit ? "" : "disabled";
    return `<tr><td><select data-k="role" ${dis}>${S.model.nomination_roles.map(r => `<option ${r === n.role ? "selected" : ""}>${esc(r)}</option>`).join("")}</select></td>
      <td><input type="text" data-k="name" value="${esc(n.name)}" ${dis}></td>
      <td><input type="text" data-k="designation" value="${esc(n.designation)}" ${dis}></td>
      <td><input type="text" data-k="email" value="${esc(n.email)}" placeholder="name@ministry" ${dis}></td>
      ${edit ? '<td><button type="button" class="btn sm danger" data-rm>✕</button></td>' : ""}</tr>`;
  }
  function nominationsTable(list, edit) {
    const rows = list.length ? list : (edit ? S.model.nomination_roles.slice(0, 6).map(r => ({ role: r })) : []);
    return `<table class="subtable" data-table="nominations"><thead><tr><th style="width:26%">Role</th><th>Name</th>
      <th>Designation</th><th>Email</th>${edit ? "<th></th>" : ""}</tr></thead><tbody>${rows.map(n => nomRow(n, edit)).join("")}</tbody></table>
      ${edit ? '<button type="button" class="btn sm" data-add="nominations" style="margin-top:6px">+ Add nomination</button>' : ""}`;
  }
  function svcRow(x, edit) {
    const dis = edit ? "" : "disabled";
    return `<tr><td><input type="text" data-k="subsystem" value="${esc(x.subsystem)}" placeholder="e.g. NISSA" ${dis}></td>
      <td><input type="text" data-k="code" value="${esc(x.code)}" placeholder="serviceCode" ${dis}></td>
      <td><input type="text" data-k="name" value="${esc(x.name)}" ${dis}></td>
      <td><input type="text" data-k="description" value="${esc(x.description)}" ${dis}></td>
      <td style="width:70px"><input type="text" data-k="version" value="${esc(x.version || "v1")}" ${dis}></td>
      ${edit ? '<td><button type="button" class="btn sm danger" data-rm>✕</button></td>' : ""}</tr>`;
  }
  function servicesTable(list, edit) {
    const rows = list.length ? list : (edit ? [{}] : []);
    return `<table class="subtable" data-table="services"><thead><tr><th>Subsystem</th><th>Service code</th><th>Name</th>
      <th>Description</th><th>Version</th>${edit ? "<th></th>" : ""}</tr></thead><tbody>${rows.map(x => svcRow(x, edit)).join("")}</tbody></table>
      ${edit ? '<button type="button" class="btn sm" data-add="services" style="margin-top:6px">+ Add service</button>' : ""}`;
  }

  function scoreSelect(name, val, max, step, edit) {
    const opts = [];
    for (let x = 0; x <= max + 1e-9; x += step) opts.push(Math.round(x * 10) / 10);
    return `<select data-score="${name}" ${edit ? "" : "disabled"}><option value="">-</option>${opts.map(o =>
      `<option value="${o}" ${val !== undefined && val !== "" && Number(val) === o ? "selected" : ""}>${o}</option>`).join("")}</select>`;
  }
  function yn(name, val, edit) {
    return `<select data-yn="${name}" ${edit ? "" : "disabled"}><option value="">-</option>
      <option ${val === "Yes" ? "selected" : ""}>Yes</option><option ${val === "No" ? "selected" : ""}>No</option></select>`;
  }
  function ra001Form(a, edit) {
    const m = S.model.ra001, sc = a.scores || {}, gt = a.gates || {};
    return `<div data-assess="ra001">
      <div class="field" style="max-width:340px;margin-bottom:10px"><label>Evidence level</label>
        <select data-level ${edit ? "" : "disabled"}>${[1, 2, 3].map(l => `<option value="${l}" ${Number(a.evidence_level) === l ? "selected" : ""}>
        Level ${l} · ${["self-reported (provisional)", "facilitated (decision-grade)", "verified (go-live)"][l - 1]}</option>`).join("")}</select></div>
      <div class="grid g2"><div><h3>Dimensions (score 0-4)</h3><table class="assess">${m.dimensions.map(x =>
        `<tr><td>${esc(x.label)}</td><td class="w">${x.weight}%</td><td>${scoreSelect(x.key, sc[x.key], 4, 1, edit)}</td></tr>`).join("")}</table></div>
      <div><h3>Gates (an open gate caps the result)</h3><table class="assess">${m.gates.map(x =>
        `<tr><td><span class="mono">${x.id}</span> ${esc(x.label)}</td><td>${yn(x.id, gt[x.id], edit)}</td></tr>`).join("")}</table></div></div>
      <div class="score" data-result></div></div>`;
  }
  function ra003Form(a, edit) {
    const m = S.model.ra003, sc = a.scores || {}, scr = a.screen || {};
    return `<div data-assess="ra003">
      <h3>Safeguards screen (comes first)</h3><table class="assess">${m.screen.map(x =>
        `<tr><td><span class="mono">${x.id}</span> ${esc(x.label)}</td><td>${yn(x.id, scr[x.id], edit)}</td></tr>`).join("")}</table>
      <h3 style="margin-top:14px">Criteria (score 0-5)</h3><table class="assess">${m.criteria.map(x =>
        `<tr><td>${esc(x.label)}</td><td class="w">${x.weight}%</td><td>${scoreSelect(x.key, sc[x.key], 5, 0.5, edit)}</td></tr>`).join("")}</table>
      <div class="score" data-result></div></div>`;
  }

  // client-side mirror of server scoring for live feedback (server remains authoritative)
  function calcRa001(a) {
    let total = 0;
    S.model.ra001.dimensions.forEach(x => { total += x.weight * (Number((a.scores || {})[x.key]) || 0) / 4; });
    const open = S.model.ra001.gates.filter(g => (a.gates || {})[g.id] !== "Yes").map(g => g.id);
    let band = total >= 75 ? "Ready" : total >= 60 ? "Ready with limited adjustment" : total >= 40 ? "Needs remediation" : "Not ready";
    if (open.length && (band === "Ready" || band === "Ready with limited adjustment")) band = "Needs remediation";
    return { index: Math.round(total * 10) / 10, band, open, level: Number(a.evidence_level) || 0 };
  }
  function calcRa003(a) {
    const v = {}; S.model.ra003.criteria.forEach(x => { v[x.key] = Number((a.scores || {})[x.key]) || 0; });
    const total = S.model.ra003.criteria.reduce((t, x) => t + v[x.key] * x.weight, 0) / 100;
    const failed = S.model.ra003.screen.filter(q => (a.screen || {})[q.id] !== "Yes").map(q => q.id);
    const floors = v.safeguards >= 3 && v.deliverable >= 3;
    return { score: Math.round(total * 100) / 100, failed, floors,
      outcome: failed.length ? "Fails safeguards screen" : !floors ? "Below floor - not ranked" : "Eligible" };
  }
  function readAssess(el) {
    const out = { scores: {} };
    $$("[data-score]", el).forEach(s => { if (s.value !== "") out.scores[s.dataset.score] = Number(s.value); });
    const yns = {}; $$("[data-yn]", el).forEach(s => { if (s.value) yns[s.dataset.yn] = s.value; });
    if (el.dataset.assess === "ra001") { out.gates = yns; out.evidence_level = Number($("[data-level]", el).value); }
    else out.screen = yns;
    return out;
  }
  function updateAssess(el) {
    const a = readAssess(el), res = $("[data-result]", el);
    if (el.dataset.assess === "ra001") {
      const r = calcRa001(a);
      const cls = r.band === "Ready" ? "approved" : r.band.startsWith("Ready") ? "in_review" : "returned";
      res.innerHTML = `<div class="big">${r.index}%</div><div>${chip(cls, r.band)}<div class="small muted">Readiness index ·
        evidence level ${r.level}${r.open.length ? " · open gates: " + r.open.join(", ") : " · all gates closed"}</div></div>`;
    } else {
      const r = calcRa003(a);
      const cls = r.outcome === "Eligible" ? "approved" : "returned";
      res.innerHTML = `<div class="big">${r.score.toFixed(2)}<span class="small muted"> / 5</span></div><div>${chip(cls, r.outcome)}
        <div class="small muted">Floors: 3.0 on safeguards and on deliverability · tie-break: value to the child</div></div>`;
    }
  }

  function collect(s) {
    const form = $("#stageForm"), data = {}, checklist = {};
    s.fields.forEach(f => {
      if (f.type === "nominations" || f.type === "services") {
        data[f.name] = $$(`[data-table="${f.name}"] tbody tr`, form).map(tr => {
          const o = {}; $$("[data-k]", tr).forEach(i => { o[i.dataset.k] = i.value.trim(); }); return o;
        }).filter(o => Object.entries(o).some(([k, v]) => v && k !== "role" && k !== "version"));
      } else if (f.type === "ra001" || f.type === "ra003") {
        data[f.name] = readAssess($(`[data-assess="${f.type}"]`, form));
      } else if (f.type === "multiselect") {
        data[f.name] = $$(`[data-multi="${f.name}"] input:checked`, form).map(i => i.value);
      } else {
        const el = form.elements[f.name];
        if (el) data[f.name] = f.type === "number" ? (el.value === "" ? "" : Number(el.value)) : el.value;
      }
    });
    s.checklist.forEach(c => { checklist[c.id] = form.elements["chk_" + c.id].checked; });
    return { data, checklist };
  }

  function wireStage(s, d) {
    const mid = d.member.id, base = `/members/${mid}/stages/${s.key}`;
    $$("[data-assess]").forEach(el => { updateAssess(el); el.addEventListener("change", () => updateAssess(el)); });
    $$("[data-add]").forEach(b => b.addEventListener("click", () => {
      const tb = $(`[data-table="${b.dataset.add}"] tbody`);
      tb.insertAdjacentHTML("beforeend", b.dataset.add === "nominations" ? nomRow({ role: "Training Nominee" }, true) : svcRow({}, true));
    }));
    const save = async () => renderStage(await api("PUT", base, collect(s)));
    const sb = $("#saveBtn");
    if (sb) sb.addEventListener("click", async () => {
      try { await save(); toast("Draft saved"); } catch (e) { toast(e.message, true); }
    });
    const sub = $("#submitBtn");
    if (sub) sub.addEventListener("click", async () => {
      try {
        await api("PUT", base, collect(s));
        const r = await api("POST", base + "/submit", {});
        renderStage(r); refreshTaskCount(); toast("Submitted to " + roleLabel(s.chain[0]));
      } catch (e) {
        if (e.status === 422 && e.body.details) { await pageStage(mid, s.key); toast("The gate is not yet met - see the list of items", true); }
        else toast(e.message, true);
      }
    });
    const uf = $("#uploadForm");
    if (uf) uf.addEventListener("submit", async e => {
      e.preventDefault();
      try {
        await api("PUT", base, collect(s));
        renderStage(await api("POST", base + "/documents", new FormData(uf), true)); toast("Evidence uploaded");
      } catch (err) { toast(err.message, true); }
    });
    $$("[data-del]").forEach(b => b.addEventListener("click", async () => {
      if (!confirm("Remove this document?")) return;
      try { await api("PUT", base, collect(s)); renderStage(await api("DELETE", "/documents/" + b.dataset.del)); }
      catch (e) { toast(e.message, true); }
    }));
    const decideFn = action => async () => {
      const comment = $("#decComment").value.trim();
      if (action === "return" && !comment) { toast("Give a reason when returning a submission", true); $("#decComment").focus(); return; }
      try {
        const r = await api("POST", base + "/decision", { action, comment });
        renderStage(r); refreshTaskCount();
        toast(action === "return" ? "Returned to the ministry" : "Decision recorded");
      } catch (e) { toast(e.message, true); }
    };
    const ab = $("#approveBtn"), rb = $("#returnBtn");
    if (ab) ab.addEventListener("click", decideFn("approve"));
    if (rb) rb.addEventListener("click", decideFn("return"));
  }

  // ----------------------------------------------------------------------- other pages
  async function pageTasks() {
    setNav("tasks");
    const d = await api("GET", "/tasks");
    $("#main").innerHTML = `<div class="page-head"><div><h1>My tasks</h1><div class="muted">Submissions to prepare and
      decisions awaiting you as ${esc(S.user.role_label)}</div></div></div>
      <div class="card tight">${taskList(d.tasks)}</div>`;
  }

  async function pageCatalogue() {
    setNav("catalogue");
    const d = await api("GET", "/services");
    const st = { Proposed: "draft", Agreed: "in_review", Live: "approved" };
    $("#main").innerHTML = `<div class="page-head"><div><h1>Service catalogue</h1><div class="muted">Who publishes what on
      the National Data Exchange. Services are proposed by providers, agreed at the semantic stage and go live with the member.</div></div>
      <input type="text" id="q" placeholder="Filter services" style="max-width:240px"></div>
      <div class="card tight"><table class="t"><thead><tr><th>Provider</th><th>X-Road service identifier</th><th>Service</th>
        <th>Status</th></tr></thead><tbody id="svcBody">${d.services.map(x => `<tr data-q="${esc((x.member + x.code + x.name + x.description).toLowerCase())}">
        <td><b>${esc(x.member)}</b></td>
        <td class="mono">LSO/${esc(x.member_class)}/${esc(x.member_code)}/${esc(x.subsystem)}/${esc(x.code)}/${esc(x.version)}</td>
        <td><b>${esc(x.name)}</b><div class="small muted">${esc(x.description)}</div></td>
        <td>${chip(st[x.status] || "draft", x.status)}</td></tr>`).join("") || '<tr><td colspan="4" class="empty">No services yet.</td></tr>'}</tbody></table></div>
      <p class="small muted">The exchange carries the envelope; it never opens the payload. Identifier and minimum attributes only; no bulk or search services.</p>`;
    $("#q").addEventListener("input", e => {
      const q = e.target.value.toLowerCase();
      $$("#svcBody tr").forEach(tr => { tr.hidden = q && !(tr.dataset.q || "").includes(q); });
    });
  }

  async function pageNominations() {
    setNav("nominations");
    const d = await api("GET", "/nominations");
    $("#main").innerHTML = `<div class="page-head"><div><h1>Nominations register</h1><div class="muted">Data owners,
      focal points, security officers, administrators and alternates, committee and training nominees</div></div></div>
      <div class="card tight"><table class="t"><thead><tr><th>Ministry</th><th>Role</th><th>Name</th><th>Designation</th><th>Status</th></tr></thead>
      <tbody>${d.nominations.map(n => `<tr><td>${esc(n.member)}</td><td>${esc(n.role)}</td><td><b>${esc(n.name)}</b></td>
        <td>${esc(n.designation)}</td><td>${chip(n.status === "approved" ? "approved" : n.status, n.status === "approved" ? "Verified" : null)}</td></tr>`).join("") ||
        '<tr><td colspan="5" class="empty">No nominations recorded yet.</td></tr>'}</tbody></table></div>
      <p class="small muted">Training target for the pilot: at least 30 administrators trained by 28 February 2027 (M5). Names are synthetic.</p>`;
  }

  async function pageAudit(q) {
    setNav("audit");
    const mid = new URLSearchParams(q || "").get("member");
    const d = await api("GET", "/audit" + (mid ? "?member_id=" + encodeURIComponent(mid) : ""));
    $("#main").innerHTML = `<div class="page-head"><div><h1>Audit trail</h1><div class="muted">Every sign-in, save, submission,
      decision and upload is recorded${mid ? " · filtered to one member · <a href='#/audit'>show all</a>" : ""}</div></div></div>
      <div class="card tight"><table class="t"><thead><tr><th style="width:170px">Time (UTC)</th><th>User</th><th>Ministry</th>
      <th>Event</th></tr></thead><tbody>${d.events.map(e => `<tr><td class="small">${fmtDate(e.ts)}</td>
        <td>${esc(e.full_name || "")}<div class="small muted">${esc(roleLabel(e.role))}</div></td><td>${esc(e.member || "")}</td>
        <td><span class="mono small">${esc(e.action)}</span><div>${esc(e.detail)}</div></td></tr>`).join("")}</tbody></table></div>`;
  }

  async function pageGuidance() {
    setNav("guidance");
    const m = S.model;
    const myMember = S.user.is_operator ? null : S.user.member_id;
    $("#main").innerHTML = `<div class="page-head"><div><h1>Templates & guidance</h1><div class="muted">The four
      interoperability layers, the governing instruments and the assessment models that every ministry is tested against</div></div></div>
      <div class="card"><h2>Four layers in place before any server is configured</h2>
        <div class="layers">
          ${[["Legal", "May we share this, and on what basis?", ["Lawful basis named for each service", "Standard X-Road agreement with a service schedule; no blanket MoU", "Signatory named", "DPIA accepted; interim oversight agreed"]],
             ["Organisational", "Who is accountable, and who runs it?", ["Data owner and Chief Data Officer accountable", "Committee nominees incl. data management focal point", "Security officer; administrator and distinct alternate", "Staff nominated for training"]],
             ["Semantic", "Do we mean the same thing?", ["OpenAPI service contract agreed with the provider", "Minimum attribute list, set by purpose", "Common identifier: national ID or ABR", "Reason codes and consent reference"]],
             ["Technical", "Can we connect safely?", ["RA-001 at evidence level 2 or above", "Security server in the ministry's own segment", "Hardened; keys in HSM or token; TLS", "Access rights match the agreement; synthetic-data tests"]]]
            .map(([t, q, items]) => `<div class="layer-card"><h3>${t}</h3><div class="q">${q}</div><ul>${items.map(i => `<li>${i}</li>`).join("")}</ul></div>`).join("")}
        </div>
        <p class="small muted" style="margin-top:12px">Joint Committee resolution R12 (5 November 2026): the legal, organisational
          and semantic layers are completed first; technical steps follow CF-001's secure onboarding procedure.</p></div>
      <div class="grid g2">
        <div class="card"><h2>Online templates</h2><table class="t"><tbody>
          <tr><td><b>Standard X-Road member agreement and service schedule</b><div class="small muted">Pre-filled from the legal and semantic stages</div></td>
            <td>${myMember ? `<a class="btn sm" target="_blank" rel="noopener" href="/api/v1/members/${myMember}/agreement">Open</a>` : '<span class="small muted">Open from a member page</span>'}</td></tr>
          <tr><td><b>Nominations register</b><div class="small muted">Stage 2 form, signed by the Principal Secretary</div></td><td><a class="btn sm" href="#/nominations">View</a></td></tr>
          <tr><td><b>RA-001 readiness assessment</b><div class="small muted">34 criteria condensed to six weighted dimensions and six gates</div></td><td>Stage 5</td></tr>
          <tr><td><b>RA-003 use-case assessment</b><div class="small muted">Six-question safeguards screen then five weighted criteria</div></td><td>Stage 4</td></tr>
        </tbody></table></div>
        <div class="card"><h2>Instruments the pilot works within</h2><ul>${m.instruments.map(i => `<li>${esc(i)}</li>`).join("")}
          <li>UN Universal DPI Safeguards Framework (18 principles)</li><li>X-Road Security Framework CF-001 (NIST CSF 2.0, ISO/IEC 27001:2022)</li></ul></div>
      </div>
      <div class="grid g2">
        <div class="card"><h2>Five standing safeguard conditions</h2><ol>
          <li>No live child data before the DPIA is accepted; synthetic data only until then</li>
          <li>The identifier and the minimum attributes only; no bulk or search services</li>
          <li>Consent at the point of service, from a parent or guardian where the person is a child</li>
          <li>Progress counted, never listed</li><li>Every decline carries a reason code and a route to remedy</li></ol></div>
        <div class="card"><h2>Evidence levels</h2><table class="t"><tbody>
          <tr><td><b>1 · Self-reported</b></td><td>Questionnaire; provisional only</td></tr>
          <tr><td><b>2 · Facilitated</b></td><td>Agreed in session; decision-grade</td></tr>
          <tr><td><b>3 · Verified</b></td><td>Document seen or function shown; required for go-live</td></tr></tbody></table>
          <h3 style="margin-top:14px">RA-001 bands</h3><p class="small">Ready ≥ 75% · Ready with limited adjustment 60-75% ·
          Needs remediation 40-60% · Not ready &lt; 40%. An open gate caps the result at Needs remediation.</p></div>
      </div>
      <div class="card"><h2>Roles in the governance hierarchy</h2><table class="t"><thead><tr><th>Role</th><th>Responsibility</th></tr></thead>
        <tbody>${Object.entries(m.roles).map(([k, r]) => `<tr><td><b>${esc(r.label)}</b><div class="small muted">${r.scope === "member" ? "Line ministry" : r.scope === "governance" ? "Joint Committee" : "MICSTI (Operator)"}</div></td><td>${esc(r.desc)}</td></tr>`).join("")}</tbody></table></div>`;
  }

  async function pageApi() {
    setNav("api");
    const d = await api("GET", "/openapi.json");
    $("#main").innerHTML = `<div class="page-head"><div><h1>REST API</h1><div class="muted">${esc(d.info.description)}</div></div>
      <a class="btn" href="/api/v1/openapi.json" target="_blank" rel="noopener">openapi.json</a></div>
      <div class="card tight"><table class="t"><thead><tr><th style="width:90px">Method</th><th>Path</th><th>Purpose</th></tr></thead><tbody>
      ${Object.entries(d.paths).flatMap(([p, ops]) => Object.entries(ops).map(([meth, o]) =>
        `<tr><td><span class="chip ${meth === "get" ? "approved" : meth === "delete" ? "returned" : "in_review"}">${meth.toUpperCase()}</span></td>
        <td class="mono">${esc(p)}</td><td>${esc(o.summary)}</td></tr>`)).join("")}</tbody></table></div>`;
  }

  // ======================================================================= router
  async function route() {
    if (!S.user) return;
    const h = location.hash.replace(/^#/, "") || "/";
    const [path, query] = h.split("?");
    const parts = path.split("/").filter(Boolean);
    window.scrollTo(0, 0);
    try {
      if (!parts.length) await pageDashboard();
      else if (parts[0] === "tasks") await pageTasks();
      else if (parts[0] === "members" && parts.length === 1) S.user.is_operator ? await pageMembers() : (location.hash = "#/members/" + S.user.member_id);
      else if (parts[0] === "members" && parts.length === 2) await pageMember(parts[1]);
      else if (parts[0] === "members" && parts.length === 3) await pageStage(parts[1], parts[2]);
      else if (parts[0] === "catalogue") await pageCatalogue();
      else if (parts[0] === "nominations") await pageNominations();
      else if (parts[0] === "guidance") await pageGuidance();
      else if (parts[0] === "audit") await pageAudit(query);
      else if (parts[0] === "api") await pageApi();
      else $("#main").innerHTML = `<div class="empty">Page not found. <a href="#/">Go to the dashboard</a></div>`;
      document.title = ($("h1") ? $("h1").textContent + " · " : "") + "X-Road Member Onboarding Portal";
    } catch (e) {
      if (e.status === 401) return;
      $("#main").innerHTML = `<div class="notice returned"><b>${esc(e.message)}</b></div>`;
    }
    refreshTaskCount();
  }

  async function boot() {
    try {
      S.model = S.model || await api("GET", "/model");
      const me = await api("GET", "/auth/me");
      S.user = me.user; S.member = me.member;
    } catch (e) {
      if (e.status !== 401) console.error(e);
      return renderLogin();
    }
    renderShell();
    await route();
  }

  window.addEventListener("hashchange", route);
  boot();
})();
