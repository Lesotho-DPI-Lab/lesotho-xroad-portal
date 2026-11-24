import json
import sqlite3
from datetime import datetime, timezone

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    short TEXT NOT NULL,
    member_class TEXT NOT NULL DEFAULT 'GOV',
    systems TEXT NOT NULL DEFAULT '',
    wave TEXT NOT NULL DEFAULT 'Pilot',
    is_operator INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL,
    member_id INTEGER REFERENCES members(id)
);
CREATE TABLE IF NOT EXISTS stage_records (
    id INTEGER PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES members(id),
    stage_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'not_started',
    level INTEGER NOT NULL DEFAULT 0,
    data TEXT NOT NULL DEFAULT '{}',
    checklist TEXT NOT NULL DEFAULT '{}',
    submitted_at TEXT,
    submitted_by INTEGER REFERENCES users(id),
    approved_at TEXT,
    updated_at TEXT,
    UNIQUE(member_id, stage_key)
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY,
    record_id INTEGER NOT NULL REFERENCES stage_records(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    role TEXT NOT NULL,
    action TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    record_id INTEGER NOT NULL REFERENCES stage_records(id),
    doc_type TEXT NOT NULL,
    filename TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    size INTEGER NOT NULL,
    evidence_level INTEGER NOT NULL DEFAULT 1,
    uploaded_by INTEGER REFERENCES users(id),
    uploaded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES members(id),
    subsystem TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    version TEXT NOT NULL DEFAULT 'v1',
    status TEXT NOT NULL DEFAULT 'Proposed',
    UNIQUE(member_id, subsystem, code)
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    user_id INTEGER,
    member_id INTEGER,
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
"""


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_schema(db):
    db.execute("PRAGMA journal_mode = WAL")
    db.executescript(SCHEMA)
    db.commit()


def row(r):
    if r is None:
        return None
    d = dict(r)
    for k in ("data", "checklist"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except ValueError:
                d[k] = {}
    return d


def rows(rs):
    return [row(r) for r in rs]


def audit(db, user_id, member_id, action, detail=""):
    db.execute("INSERT INTO audit (ts, user_id, member_id, action, detail) VALUES (?,?,?,?,?)",
               (now(), user_id, member_id, action, detail))
