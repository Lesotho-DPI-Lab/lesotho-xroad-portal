"""REST API: /api/v1"""
import json
import os
import uuid
from functools import wraps
from html import escape

from flask import Blueprint, current_app, g, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash

from .db import audit, get_db, now, row, rows
from .stages import (OPERATOR_ROLES, ROLES, STAGE_BY_KEY, STAGE_ORDER, STAGES, public_model,
                     ra001_score, ra003_score)

bp = Blueprint("api", __name__, url_prefix="/api/v1")

ALLOWED_EXT = {"pdf", "docx", "doc", "xlsx", "xls", "odt", "ods", "png", "jpg", "jpeg", "txt", "csv",
               "json", "yaml", "yml"}
EDITABLE = {"not_started", "draft", "returned"}
ACTION_WORD = {"mda_ps": "endorsed", "tc": "recommended", "sc": "approved"}
REQUIRED_NOMINATIONS = ["Data Owner", "Chief Data Officer", "Data Management Focal Point", "Security Officer",
                        "Security Server Administrator", "Alternate Administrator"]


class ApiError(Exception):
    def __init__(self, status, message, details=None):
        super().__init__(message)
        self.status, self.message, self.details = status, message, details


@bp.errorhandler(ApiError)
def _api_error(e):
    body = {"error": e.message}
    if e.details:
        body["details"] = e.details
    return jsonify(body), e.status


@bp.before_request
def _load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = row(get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
    # Simple CSRF defence for cookie sessions: state-changing calls must carry a custom header,
    # which a cross-site form cannot set.
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("X-Requested-With") != "portal":
        raise ApiError(403, "Missing X-Requested-With header")


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not g.user:
            raise ApiError(401, "Authentication required")
        return fn(*a, **kw)
    return wrapper


def is_operator(user):
    return user["role"] in OPERATOR_ROLES


def body():
    return request.get_json(silent=True) or {}


# ----------------------------------------------------------------- helpers
def get_member(mid):
    m = row(get_db().execute("SELECT * FROM members WHERE id=?", (mid,)).fetchone())
    if not m:
        raise ApiError(404, "Member not found")
    if not is_operator(g.user) and g.user["member_id"] != m["id"]:
        raise ApiError(403, "You may only view your own ministry")
    return m


def get_stage(key):
    s = STAGE_BY_KEY.get(key)
    if not s:
        raise ApiError(404, "Unknown stage")
    return s


def get_record(member_id, key):
    db = get_db()
    r = db.execute("SELECT * FROM stage_records WHERE member_id=? AND stage_key=?", (member_id, key)).fetchone()
    if not r:
        db.execute("INSERT INTO stage_records (member_id, stage_key, updated_at) VALUES (?,?,?)",
                   (member_id, key, now()))
        db.commit()
        r = db.execute("SELECT * FROM stage_records WHERE member_id=? AND stage_key=?", (member_id, key)).fetchone()
    return row(r)


def records_for(member_id):
    rs = rows(get_db().execute("SELECT * FROM stage_records WHERE member_id=?", (member_id,)).fetchall())
    by = {r["stage_key"]: r for r in rs}
    return [by.get(k) or get_record(member_id, k) for k in STAGE_ORDER]


def is_unlocked(member_id, key):
    i = STAGE_ORDER.index(key)
    if i == 0:
        return True
    prev = get_record(member_id, STAGE_ORDER[i - 1])
    return prev["status"] == "approved"


def effective_status(rec, unlocked):
    if rec["status"] == "not_started" and not unlocked:
        return "locked"
    return rec["status"]


def can_edit(user, rec, stage, unlocked):
    return (unlocked and user["member_id"] == rec["member_id"] and user["role"] in stage["submitters"]
            and rec["status"] in EDITABLE)


def awaiting_role(rec, stage):
    if rec["status"] != "in_review":
        return None
    return stage["chain"][rec["level"]] if rec["level"] < len(stage["chain"]) else None


def can_decide(user, rec, stage):
    role = awaiting_role(rec, stage)
    if not role or user["role"] != role:
        return False
    if ROLES[role]["scope"] == "member":
        return user["member_id"] == rec["member_id"]
    return True


def computed(stage, data):
    out = {}
    if stage["key"] == "readiness":
        out["ra001"] = ra001_score(data.get("ra001"))
    if stage["key"] == "usecase":
        out["ra003"] = ra003_score(data.get("ra003"))
    return out


def documents_for(record_id):
    return rows(get_db().execute(
        "SELECT d.*, u.full_name AS uploaded_by_name FROM documents d LEFT JOIN users u ON u.id=d.uploaded_by "
        "WHERE record_id=? ORDER BY uploaded_at", (record_id,)).fetchall())


def validate(stage, rec):
    data, chk = rec["data"] or {}, rec["checklist"] or {}
    issues = []
    for f in stage["fields"]:
        v = data.get(f["name"])
        if f["type"] == "nominations":
            noms = [n for n in (v or []) if (n.get("name") or "").strip()]
            have = {n.get("role") for n in noms}
            missing = [r for r in REQUIRED_NOMINATIONS if r not in have]
            if missing:
                issues.append("Nominations missing: " + ", ".join(missing))
            admins = {n["name"].strip().lower() for n in noms if n.get("role") == "Security Server Administrator"}
            alts = {n["name"].strip().lower() for n in noms if n.get("role") == "Alternate Administrator"}
            if admins & alts:
                issues.append("The alternate administrator must be a different person from the administrator")
            if "Training Nominee" not in have:
                issues.append("Nominate at least one member of staff for training")
        elif f["type"] == "services":
            if not [s for s in (v or []) if (s.get("code") or "").strip() and (s.get("name") or "").strip()]:
                issues.append("Add at least one service with a code and a name")
        elif f["type"] == "ra001":
            sc = ra001_score(v)
            if sc["evidence_level"] < 2:
                issues.append("RA-001 must be at evidence level 2 (facilitated) or above")
            if sc["open_gates"]:
                issues.append("Open RA-001 gates must be closed: " + ", ".join(sc["open_gates"]))
        elif f["type"] == "ra003":
            sc = ra003_score(v)
            if sc["failed_screen"]:
                issues.append("Safeguards screen not passed: " + ", ".join(sc["failed_screen"]))
            elif not sc["floors_ok"]:
                issues.append("Below the 3.0 floor on safeguards or deliverability; the use case is not ranked")
        elif f.get("required"):
            if v is None or (isinstance(v, (str, list)) and not v) or (isinstance(v, str) and not v.strip()):
                issues.append(f"{f['label']} is required")
    for cid, label in stage["checklist"]:
        if not chk.get(cid):
            issues.append(f"Confirm: {label}")
    have_docs = {d["doc_type"] for d in documents_for(rec["id"])}
    for d in stage["documents"]:
        if d["required"] and d["type"] not in have_docs:
            issues.append(f"Upload: {d['label']}")
    return issues


def member_summary(m):
    recs = records_for(m["id"])
    approved = sum(1 for r in recs if r["status"] == "approved")
    current = next((r for r in recs if r["status"] != "approved"), None)
    by = {r["stage_key"]: r for r in recs}
    if by["golive"]["status"] == "approved":
        overall = "Live on X-Road"
    elif by["clearance"]["status"] == "approved":
        overall = "Technical onboarding"
    elif approved == 0 and all(r["status"] == "not_started" for r in recs):
        overall = "Not started"
    else:
        overall = "Pre-technical readiness"
    stages = []
    prev_ok = True
    for s, r in zip(STAGES, recs):
        st = effective_status(r, prev_ok)
        stages.append({"key": s["key"], "status": st, "awaiting": awaiting_role(r, s)})
        prev_ok = r["status"] == "approved"
    cur = None
    if current:
        s = STAGE_BY_KEY[current["stage_key"]]
        cur = {"key": s["key"], "no": s["no"], "title": s["title"], "status": current["status"],
               "awaiting": awaiting_role(current, s)}
    return {**m, "approved": approved, "total": len(STAGES), "overall": overall, "current": cur,
            "stages": stages}


def user_public(u):
    return {k: u[k] for k in ("id", "username", "full_name", "title", "email", "role", "member_id")} | {
        "role_label": ROLES[u["role"]]["label"], "is_operator": is_operator(u)}


def tasks_for(user):
    db = get_db()
    out = []
    if is_operator(user):
        members = rows(db.execute("SELECT * FROM members WHERE is_operator=0").fetchall())
    else:
        members = rows(db.execute("SELECT * FROM members WHERE id=?", (user["member_id"],)).fetchall())
    for m in members:
        prev_ok = True
        for s, r in zip(STAGES, records_for(m["id"])):
            if can_decide(user, r, s):
                out.append({"kind": "review", "member_id": m["id"], "member": m["short"], "stage": s["key"],
                            "stage_no": s["no"], "title": s["title"], "since": r["submitted_at"],
                            "action": "Review and decide"})
            elif can_edit(user, r, s, prev_ok):
                label = {"returned": "Revise and resubmit", "draft": "Complete and submit"}.get(
                    r["status"], "Start")
                out.append({"kind": "prepare", "member_id": m["id"], "member": m["short"], "stage": s["key"],
                            "stage_no": s["no"], "title": s["title"], "since": r["updated_at"],
                            "action": label, "status": r["status"]})
            prev_ok = r["status"] == "approved"
    return out


def sync_services(member_id, data, status):
    db = get_db()
    for s in data.get("services") or []:
        code, name = (s.get("code") or "").strip(), (s.get("name") or "").strip()
        if not code or not name:
            continue
        db.execute(
            "INSERT INTO services (member_id, subsystem, code, name, description, version, status) "
            "VALUES (?,?,?,?,?,?,?) ON CONFLICT(member_id, subsystem, code) DO UPDATE SET "
            "name=excluded.name, description=excluded.description, version=excluded.version, status=excluded.status",
            (member_id, (s.get("subsystem") or "").strip() or "DEFAULT", code, name,
             (s.get("description") or "").strip(), (s.get("version") or "v1").strip(), status))


# ----------------------------------------------------------------- auth
@bp.post("/auth/login")
def login():
    b = body()
    u = row(get_db().execute("SELECT * FROM users WHERE username=?",
                             ((b.get("username") or "").strip().lower(),)).fetchone())
    if not u or not check_password_hash(u["password_hash"], b.get("password") or ""):
        raise ApiError(401, "Invalid username or password")
    session.clear()
    session["uid"] = u["id"]
    session.permanent = True
    db = get_db()
    audit(db, u["id"], u["member_id"], "login", u["username"])
    db.commit()
    return jsonify({"user": user_public(u)})


@bp.post("/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@bp.get("/auth/me")
@login_required
def me():
    m = None
    if g.user["member_id"]:
        m = row(get_db().execute("SELECT * FROM members WHERE id=?", (g.user["member_id"],)).fetchone())
    return jsonify({"user": user_public(g.user), "member": m})


@bp.get("/auth/demo-accounts")
def demo_accounts():
    """Demonstration only: lists the synthetic accounts so workshop participants can sign in."""
    us = rows(get_db().execute(
        "SELECT u.username, u.full_name, u.role, m.short AS member FROM users u "
        "LEFT JOIN members m ON m.id=u.member_id ORDER BY u.member_id IS NOT NULL, m.short, u.id").fetchall())
    for u in us:
        u["role_label"] = ROLES[u["role"]]["label"]
    return jsonify({"password": current_app.config["DEMO_PASSWORD"], "accounts": us})


# ----------------------------------------------------------------- model
@bp.get("/health")
def health():
    get_db().execute("SELECT 1").fetchone()
    return jsonify({"status": "ok", "time": now()})


@bp.get("/model")
def model():
    return jsonify(public_model())


# ----------------------------------------------------------------- members
@bp.get("/members")
@login_required
def list_members():
    db = get_db()
    if is_operator(g.user):
        ms = rows(db.execute("SELECT * FROM members WHERE is_operator=0 ORDER BY name").fetchall())
    else:
        ms = rows(db.execute("SELECT * FROM members WHERE id=?", (g.user["member_id"],)).fetchall())
    return jsonify({"members": [member_summary(m) for m in ms]})


@bp.get("/members/<int:mid>")
@login_required
def get_member_ep(mid):
    m = get_member(mid)
    return jsonify({"member": member_summary(m)})


@bp.get("/members/<int:mid>/stages/<key>")
@login_required
def get_stage_ep(mid, key):
    m, s = get_member(mid), get_stage(key)
    rec = get_record(mid, key)
    unlocked = is_unlocked(mid, key)
    decisions = rows(get_db().execute(
        "SELECT d.*, u.full_name FROM decisions d JOIN users u ON u.id=d.user_id WHERE record_id=? "
        "ORDER BY d.id", (rec["id"],)).fetchall())
    for d in decisions:
        d["role_label"] = ROLES[d["role"]]["label"]
    aw = awaiting_role(rec, s)
    return jsonify({
        "member": {"id": m["id"], "name": m["name"], "short": m["short"]},
        "stage": s["key"],
        "record": {**rec, "status": effective_status(rec, unlocked)},
        "unlocked": unlocked,
        "can_edit": can_edit(g.user, rec, s, unlocked),
        "can_decide": can_decide(g.user, rec, s),
        "awaiting": aw, "awaiting_label": ROLES[aw]["label"] if aw else None,
        "documents": documents_for(rec["id"]),
        "decisions": decisions,
        "computed": computed(s, rec["data"]),
        "issues": validate(s, rec) if unlocked else [],
    })


@bp.put("/members/<int:mid>/stages/<key>")
@login_required
def save_stage(mid, key):
    get_member(mid)
    s, rec = get_stage(key), get_record(mid, key)
    if not can_edit(g.user, rec, s, is_unlocked(mid, key)):
        raise ApiError(403, "This stage cannot be edited by you in its current state")
    b = body()
    allowed = {f["name"] for f in s["fields"]}
    data = {k: v for k, v in (b.get("data") or {}).items() if k in allowed}
    chk_ids = {c for c, _ in s["checklist"]}
    chk = {k: bool(v) for k, v in (b.get("checklist") or {}).items() if k in chk_ids}
    status = "returned" if rec["status"] == "returned" else "draft"
    db = get_db()
    db.execute("UPDATE stage_records SET data=?, checklist=?, status=?, updated_at=? WHERE id=?",
               (json.dumps(data), json.dumps(chk), status, now(), rec["id"]))
    audit(db, g.user["id"], mid, "stage.save", f"{s['title']} saved as draft")
    db.commit()
    return get_stage_ep(mid, key)


@bp.post("/members/<int:mid>/stages/<key>/submit")
@login_required
def submit_stage(mid, key):
    get_member(mid)
    s, rec = get_stage(key), get_record(mid, key)
    if not can_edit(g.user, rec, s, is_unlocked(mid, key)):
        raise ApiError(403, "This stage cannot be submitted by you in its current state")
    issues = validate(s, rec)
    if issues:
        raise ApiError(422, "The gate is not yet met", issues)
    db = get_db()
    db.execute("UPDATE stage_records SET status='in_review', level=0, submitted_at=?, submitted_by=?, "
               "updated_at=? WHERE id=?", (now(), g.user["id"], now(), rec["id"]))
    db.execute("INSERT INTO decisions (record_id, user_id, role, action, comment, created_at) VALUES (?,?,?,?,?,?)",
               (rec["id"], g.user["id"], g.user["role"], "submitted", body().get("comment", ""), now()))
    audit(db, g.user["id"], mid, "stage.submit",
          f"{s['title']} submitted; awaiting {ROLES[s['chain'][0]]['label']}")
    db.commit()
    return get_stage_ep(mid, key)


@bp.post("/members/<int:mid>/stages/<key>/decision")
@login_required
def decide(mid, key):
    m = get_member(mid)
    s, rec = get_stage(key), get_record(mid, key)
    if not can_decide(g.user, rec, s):
        raise ApiError(403, "This submission is not awaiting your decision")
    b = body()
    action, comment = b.get("action"), (b.get("comment") or "").strip()
    db = get_db()
    if action == "return":
        if not comment:
            raise ApiError(422, "A reason is required when returning a submission")
        db.execute("UPDATE stage_records SET status='returned', level=0, updated_at=? WHERE id=?",
                   (now(), rec["id"]))
        word, detail = "returned", f"{s['title']} returned by {ROLES[g.user['role']]['label']}"
    elif action == "approve":
        word = ACTION_WORD.get(g.user["role"], "approved")
        if rec["level"] + 1 < len(s["chain"]):
            nxt = s["chain"][rec["level"] + 1]
            db.execute("UPDATE stage_records SET level=level+1, updated_at=? WHERE id=?", (now(), rec["id"]))
            detail = f"{s['title']} {word}; awaiting {ROLES[nxt]['label']}"
        else:
            word = "approved" if g.user["role"] != "tc" else word
            db.execute("UPDATE stage_records SET status='approved', approved_at=?, updated_at=? WHERE id=?",
                       (now(), now(), rec["id"]))
            detail = f"{s['title']} approved - gate passed"
            if key == "semantic":
                sync_services(mid, rec["data"], "Agreed")
            if key == "golive":
                db.execute("UPDATE services SET status='Live' WHERE member_id=?", (mid,))
                detail = f"{m['short']} is live on X-Road"
            if key == "clearance":
                detail = f"{m['short']} cleared for technical onboarding"
    else:
        raise ApiError(422, "action must be 'approve' or 'return'")
    db.execute("INSERT INTO decisions (record_id, user_id, role, action, comment, created_at) VALUES (?,?,?,?,?,?)",
               (rec["id"], g.user["id"], g.user["role"], word, comment, now()))
    audit(db, g.user["id"], mid, f"stage.{action}", detail)
    db.commit()
    return get_stage_ep(mid, key)


# ----------------------------------------------------------------- documents
@bp.post("/members/<int:mid>/stages/<key>/documents")
@login_required
def upload(mid, key):
    get_member(mid)
    s, rec = get_stage(key), get_record(mid, key)
    if not can_edit(g.user, rec, s, is_unlocked(mid, key)):
        raise ApiError(403, "Evidence can only be uploaded while the stage is being prepared")
    f = request.files.get("file")
    doc_type = request.form.get("doc_type", "")
    if doc_type not in {d["type"] for d in s["documents"]}:
        raise ApiError(422, "Unknown document type for this stage")
    if not f or not f.filename:
        raise ApiError(422, "Choose a file to upload")
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_EXT:
        raise ApiError(422, "File type not allowed", sorted(ALLOWED_EXT))
    try:
        level = max(1, min(3, int(request.form.get("evidence_level", 1))))
    except ValueError:
        level = 1
    stored = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(current_app.config["UPLOAD_DIR"], stored)
    f.save(path)
    size = os.path.getsize(path)
    safe_name = os.path.basename(f.filename)[:200]
    db = get_db()
    db.execute("INSERT INTO documents (record_id, doc_type, filename, stored_name, size, evidence_level, "
               "uploaded_by, uploaded_at) VALUES (?,?,?,?,?,?,?,?)",
               (rec["id"], doc_type, safe_name, stored, size, level, g.user["id"], now()))
    if rec["status"] == "not_started":
        db.execute("UPDATE stage_records SET status='draft', updated_at=? WHERE id=?", (now(), rec["id"]))
    audit(db, g.user["id"], mid, "document.upload", f"{safe_name} ({s['title']})")
    db.commit()
    return get_stage_ep(mid, key)


def _doc(doc_id):
    d = row(get_db().execute(
        "SELECT d.*, r.member_id, r.stage_key, r.status FROM documents d JOIN stage_records r ON r.id=d.record_id "
        "WHERE d.id=?", (doc_id,)).fetchone())
    if not d:
        raise ApiError(404, "Document not found")
    get_member(d["member_id"])
    return d


@bp.get("/documents/<int:doc_id>")
@login_required
def download(doc_id):
    d = _doc(doc_id)
    return send_from_directory(current_app.config["UPLOAD_DIR"], d["stored_name"], as_attachment=True,
                               download_name=d["filename"])


@bp.delete("/documents/<int:doc_id>")
@login_required
def delete_doc(doc_id):
    d = _doc(doc_id)
    s = STAGE_BY_KEY[d["stage_key"]]
    rec = get_record(d["member_id"], d["stage_key"])
    if not can_edit(g.user, rec, s, is_unlocked(d["member_id"], d["stage_key"])):
        raise ApiError(403, "Evidence can only be removed while the stage is being prepared")
    db = get_db()
    db.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    audit(db, g.user["id"], d["member_id"], "document.delete", d["filename"])
    db.commit()
    try:
        os.remove(os.path.join(current_app.config["UPLOAD_DIR"], d["stored_name"]))
    except OSError:
        pass
    return get_stage_ep(d["member_id"], d["stage_key"])


# ----------------------------------------------------------------- registers
@bp.get("/tasks")
@login_required
def tasks():
    return jsonify({"tasks": tasks_for(g.user)})


@bp.get("/services")
@login_required
def services():
    q = ("SELECT s.*, m.short AS member, m.code AS member_code, m.member_class FROM services s "
         "JOIN members m ON m.id=s.member_id ORDER BY m.short, s.code")
    return jsonify({"services": rows(get_db().execute(q).fetchall())})


@bp.get("/nominations")
@login_required
def nominations():
    db = get_db()
    q = ("SELECT r.*, m.short AS member, m.id AS mid FROM stage_records r JOIN members m ON m.id=r.member_id "
         "WHERE r.stage_key='organisational'")
    params = ()
    if not is_operator(g.user):
        q += " AND m.id=?"
        params = (g.user["member_id"],)
    out = []
    for r in rows(db.execute(q, params).fetchall()):
        for n in (r["data"] or {}).get("nominations") or []:
            if (n.get("name") or "").strip():
                out.append({**n, "member": r["member"], "member_id": r["mid"], "status": r["status"]})
    return jsonify({"nominations": out})


@bp.get("/audit")
@login_required
def audit_log():
    db = get_db()
    q = ("SELECT a.*, u.full_name, u.role, m.short AS member FROM audit a LEFT JOIN users u ON u.id=a.user_id "
         "LEFT JOIN members m ON m.id=a.member_id")
    params = []
    if not is_operator(g.user):
        q += " WHERE a.member_id=?"
        params.append(g.user["member_id"])
    elif request.args.get("member_id"):
        q += " WHERE a.member_id=?"
        params.append(int(request.args["member_id"]))
    q += " ORDER BY a.id DESC LIMIT 300"
    return jsonify({"events": rows(db.execute(q, params).fetchall())})


@bp.get("/dashboard")
@login_required
def dashboard():
    ms = list_members().get_json()["members"]
    pending_reviews = sum(1 for m in ms for s in m["stages"] if s["status"] == "in_review")
    return jsonify({
        "members": ms,
        "kpis": {
            "members": len(ms),
            "cleared": sum(1 for m in ms if m["overall"] in ("Technical onboarding", "Live on X-Road")),
            "live": sum(1 for m in ms if m["overall"] == "Live on X-Road"),
            "in_review": pending_reviews,
            "services": get_db().execute("SELECT COUNT(*) FROM services").fetchone()[0],
        },
        "tasks": tasks_for(g.user),
    })


@bp.post("/admin/reset")
@login_required
def reset():
    if g.user["role"] != "admin":
        raise ApiError(403, "Only the portal administrator can reset demonstration data")
    from .seed import seed
    seed(current_app, reset=True)
    session.clear()
    return jsonify({"ok": True})


# ----------------------------------------------------------------- agreement template
@bp.get("/members/<int:mid>/agreement")
@login_required
def agreement(mid):
    m = get_member(mid)
    d = get_record(mid, "legal")["data"] or {}
    sem = get_record(mid, "semantic")["data"] or {}

    def v(k, default="____________________"):
        x = d.get(k)
        if isinstance(x, list):
            x = "; ".join(x)
        return escape(str(x)) if x else default

    svc_rows = "".join(
        f"<tr><td>{escape(s.get('subsystem') or '')}</td><td>{escape(s.get('code') or '')}</td>"
        f"<td>{escape(s.get('name') or '')}</td><td>{escape(s.get('description') or '')}</td></tr>"
        for s in (sem.get("services") or [])) or "<tr><td colspan=4><em>To be completed at the semantic stage</em></td></tr>"
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Standard X-Road Member Agreement - {escape(m['short'])}</title>
<style>body{{font:14px/1.55 Georgia,serif;max-width:800px;margin:40px auto;color:#1a1a1a;padding:0 24px}}
h1{{font:600 20px system-ui;margin:0}}h2{{font:600 15px system-ui;margin:28px 0 6px;color:#0b2a5b}}
.hd{{display:flex;gap:16px;align-items:center;border-bottom:2px solid #0b2a5b;padding-bottom:14px;margin-bottom:8px}}
.hd img{{height:72px}}.sub{{font:13px system-ui;color:#555}}table{{border-collapse:collapse;width:100%;font:13px system-ui}}
td,th{{border:1px solid #ccc;padding:6px 8px;text-align:left;vertical-align:top}}th{{background:#f2f4f8;width:34%}}
.wm{{font:600 12px system-ui;color:#a33;border:1px solid #a33;display:inline-block;padding:2px 8px;margin-top:6px}}
.sig{{display:grid;grid-template-columns:1fr 1fr;gap:40px;margin-top:40px}}.sig div{{border-top:1px solid #333;padding-top:6px;font:13px system-ui}}
@media print{{.np{{display:none}}}}</style></head><body>
<p class="np"><button onclick="print()">Print / save as PDF</button></p>
<div class="hd"><img src="/static/img/coat-of-arms.svg" alt="Coat of arms"><div>
<div class="sub">Kingdom of Lesotho · Ministry of Information, Communications, Science, Technology and Innovation</div>
<h1>Standard X-Road Member Agreement and Service Schedule</h1>
<div class="sub">National Data Exchange (X-Road) · Template AG-001 · Joint Committee resolution R12</div>
<div class="wm">DEMONSTRATION · SYNTHETIC DATA ONLY</div></div></div>
<h2>1. Parties</h2><p>This agreement is made between the <b>Ministry of Information, Communications, Science, Technology
and Innovation (MICSTI)</b>, as X-Road Operator, and the <b>{escape(m['name'])}</b> (member code
<b>{escape(m['member_class'])}/{escape(m['code'])}</b>), as Member.</p>
<h2>2. Purpose and lawful basis</h2><table>
<tr><th>Lawful basis</th><td>{v('lawful_basis')}</td></tr><tr><th>Instrument(s)</th><td>{v('instrument')}</td></tr>
<tr><th>Purpose</th><td>{v('purpose')}</td></tr></table>
<h2>3. Service schedule</h2><table><tr><th>Attributes</th><td>{v('attributes')}</td></tr>
<tr><th>Retention</th><td>{v('retention')}</td></tr><tr><th>Audit</th><td>{v('audit')}</td></tr>
<tr><th>DPIA status</th><td>{v('dpia_status')}</td></tr><tr><th>Interim oversight</th><td>{v('oversight')}</td></tr></table>
<p></p><table><tr><th style="width:auto">Subsystem</th><th style="width:auto">Service code</th><th style="width:auto">Service</th><th style="width:auto">Description</th></tr>{svc_rows}</table>
<h2>4. Standing safeguard conditions</h2><ol><li>No live child data before the DPIA is accepted; synthetic data only until then.</li>
<li>The identifier and the minimum attributes only; no bulk or search services.</li><li>Consent at the point of service, from a parent or guardian where the person is a child.</li>
<li>Progress counted, never listed.</li><li>Every decline carries a reason code and a route to remedy.</li></ol>
<h2>5. Obligations of the Member</h2><p>The Member shall operate its security server in its own network segment, hold its
signing keys in a hardware security module or token, maintain TLS between its information systems and its security
server, keep message logs, name a security officer and an administrator with a distinct alternate, and comply with the
X-Road Security Framework (CF-001), the Data Protection Act 2011 and related law.</p>
<h2>6. Obligations of the Operator</h2><p>MICSTI shall operate the Central Server and trust services, publish the global
configuration, hold no Member payload data, and provide monitoring, incident coordination and onboarding support at no
licence or per-transaction fee.</p>
<div class="sig"><div>For the Member: {v('signatory_name')}<br>{v('signatory_title')}<br>Date: __________</div>
<div>For MICSTI (X-Road Operator)<br>Principal Secretary<br>Date: __________</div></div></body></html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


# ----------------------------------------------------------------- OpenAPI
ENDPOINT_DOCS = {
    "/api/v1/health": "Service health check",
    "/api/v1/model": "Process model: roles, stages, gates, RA-001/RA-003 definitions",
    "/api/v1/auth/login": "Sign in (username, password); sets a session cookie",
    "/api/v1/auth/logout": "Sign out",
    "/api/v1/auth/me": "Current user and ministry",
    "/api/v1/auth/demo-accounts": "Synthetic demonstration accounts",
    "/api/v1/dashboard": "KPIs, member status and my tasks",
    "/api/v1/members": "Members and their onboarding progress",
    "/api/v1/members/{mid}": "One member's onboarding status",
    "/api/v1/members/{mid}/stages/{key}": "Stage record (GET), save draft (PUT)",
    "/api/v1/members/{mid}/stages/{key}/submit": "Submit a stage against its gate",
    "/api/v1/members/{mid}/stages/{key}/decision": "Endorse/approve or return (action, comment)",
    "/api/v1/members/{mid}/stages/{key}/documents": "Upload evidence (multipart: file, doc_type, evidence_level)",
    "/api/v1/members/{mid}/agreement": "Rendered standard agreement and service schedule",
    "/api/v1/documents/{doc_id}": "Download (GET) or remove (DELETE) evidence",
    "/api/v1/tasks": "Items awaiting the current user",
    "/api/v1/services": "Service catalogue",
    "/api/v1/nominations": "Nominations register",
    "/api/v1/audit": "Audit trail",
    "/api/v1/admin/reset": "Reset demonstration data (administrator)",
    "/api/v1/openapi.json": "This document",
}


@bp.get("/openapi.json")
def openapi():
    paths = {}
    for rule in current_app.url_map.iter_rules():
        if not rule.rule.startswith("/api/v1"):
            continue
        p = rule.rule.replace("<int:", "{").replace("<", "{").replace(">", "}")
        for meth in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            paths.setdefault(p, {})[meth.lower()] = {
                "summary": ENDPOINT_DOCS.get(p, ""),
                "responses": {"200": {"description": "OK"}},
            }
    return jsonify({
        "openapi": "3.0.3",
        "info": {"title": "Lesotho X-Road Member Onboarding Portal API", "version": "1.0.0",
                 "description": "Demonstration API. All data is synthetic. Mutating requests require the header "
                                "X-Requested-With: portal and a session cookie from /auth/login."},
        "paths": dict(sorted(paths.items())),
    })
