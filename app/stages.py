"""Onboarding process model.

Ten gated stages in two phases, derived from PR-013 (ICT Cadre Workshop, Day 2):
  * slide 16 - the four layers of the Whole-of-Government Interoperability
    Framework (legal, organisational, semantic, technical), resolved by the
    Joint Committee (R12, 5 Nov 2026) to be settled before technical work;
  * slide 17 - the six-step guided path (Agree, Register, Install, Certify,
    Connect, Go live) that follows CF-001's secure onboarding procedure;
  * slide 18 - RA-001 (readiness) and RA-003 (use case) assessment models
    and the three evidence levels.

Each stage has a gate. A stage unlocks only when the previous one is approved,
and every submission travels up an approval chain (the governance hierarchy).
"""

ROLES = {
    # Member (line ministry) roles
    "mda_focal": {"label": "Data Management Focal Point", "scope": "member",
                  "desc": "Prepares and submits the non-technical onboarding packages for the ministry."},
    "mda_admin": {"label": "Security Server Administrator", "scope": "member",
                  "desc": "Prepares and submits technical onboarding evidence (install, certify, connect)."},
    "mda_ps": {"label": "Principal Secretary / Data Owner", "scope": "member",
               "desc": "Accountable officer. Endorses every submission before it leaves the ministry."},
    # Operator and governance roles
    "micsti_legal": {"label": "Legal & Data Protection Officer", "scope": "operator",
                     "desc": "Reviews lawful basis, agreements, service schedules and DPIA status."},
    "micsti_coord": {"label": "Onboarding Coordinator (Pilot PMO)", "scope": "operator",
                     "desc": "Verifies nominations, coordinates use-case assessment and onboarding waves."},
    "micsti_semantic": {"label": "Interoperability & Semantic Architect", "scope": "operator",
                        "desc": "Reviews service contracts, identifiers, attributes, reason codes and consent references."},
    "micsti_security": {"label": "Cybersecurity Lead", "scope": "operator",
                        "desc": "Assesses RA-001 readiness and verifies CF-001 controls on technical steps."},
    "micsti_operator": {"label": "X-Road Operator (Central Server Admin)", "scope": "operator",
                        "desc": "Registers members, certificates and subsystems on the national X-Road instance."},
    "tc": {"label": "Technical Committee", "scope": "governance",
           "desc": "Recommends use cases, clearance for technical onboarding and go-live."},
    "sc": {"label": "Steering Committee", "scope": "governance",
           "desc": "Final approval of clearance for technical onboarding and of go-live."},
    "admin": {"label": "Portal Administrator", "scope": "operator",
              "desc": "Read-only oversight of all members; resets demonstration data."},
}

OPERATOR_ROLES = {k for k, v in ROLES.items() if v["scope"] != "member"}

YES_NO = ["Yes", "No"]

NOMINATION_ROLES = [
    "Data Owner",
    "Chief Data Officer",
    "Data Management Focal Point",
    "Security Officer",
    "Security Server Administrator",
    "Alternate Administrator",
    "Technical Committee Nominee",
    "Training Nominee",
]

RA001_DIMENSIONS = [
    ("integration", "Integration", 25),
    ("data", "Data", 20),
    ("technology", "Technology", 15),
    ("security", "Security", 15),
    ("legal", "Legal and governance", 15),
    ("capacity", "Capacity", 10),
]

RA001_GATES = [
    ("D1", "Child-level (individual) records held in the system"),
    ("A1", "Complete audit trail of record access and changes"),
    ("C2", "Named system administrators (and alternate)"),
    ("L1", "Lawful basis for each exchange identified"),
    ("L7", "Consent recorded in the system (consent reference)"),
    ("L8", "Decline / refusal reasons recorded"),
]

RA003_SCREEN = [
    ("S1", "No live child data before the DPIA is accepted (synthetic data until then)"),
    ("S2", "Identifier and minimum attributes only; no bulk or search services"),
    ("S3", "Consent at the point of service (parent or guardian for a child)"),
    ("S4", "Progress counted, never listed (totals by sex and age band only)"),
    ("S5", "Every decline carries a reason code and a route to remedy"),
    ("S6", "A lawful basis exists for the exchange"),
]

RA003_CRITERIA = [
    ("value", "Value to the child and caregiver", 30),
    ("safeguards", "Safeguards position", 25),
    ("technical", "Technical readiness", 15),
    ("deliverable", "Deliverable by February 2027", 15),
    ("identity", "Dependency on identity service (5 = low risk)", 15),
]

LEGAL_INSTRUMENTS = [
    "Data Protection Act 2011",
    "National Identity Cards Act 2011 (MoU route)",
    "Registration of Births and Deaths Act 1973 (under review)",
    "Cybersecurity Bill 2026",
    "Electronic Transactions and Communications Bill 2026",
    "Data Management Policy / Government Data Management Framework",
    "Whole-of-Government Interoperability Framework",
]

STAGES = [
    # ------------------------------------------------------------ Phase A
    {
        "key": "legal", "no": 1, "phase": "A", "layer": "Legal", "step": "Agree",
        "title": "Legal readiness",
        "subtitle": "Standard X-Road agreement and service schedule",
        "question": "May we share this, and on what basis?",
        "gate": "Lawful basis, purpose, attributes, retention and audit stated; signatory named; DPIA initiated.",
        "submitters": ["mda_focal"],
        "chain": ["mda_ps", "micsti_legal"],
        "fields": [
            {"name": "lawful_basis", "label": "Lawful basis", "type": "select", "required": True,
             "options": ["Statutory function (named Act)", "Legal obligation", "Public interest task", "Consent"]},
            {"name": "instrument", "label": "Legal instrument(s) relied on", "type": "multiselect",
             "required": True, "options": LEGAL_INSTRUMENTS},
            {"name": "purpose", "label": "Purpose of the exchange", "type": "textarea", "required": True,
             "help": "One purpose per service. Purpose limits the attributes that may be requested."},
            {"name": "attributes", "label": "Attributes requested / provided", "type": "textarea", "required": True,
             "help": "Identifier and minimum attributes only. No bulk or search services."},
            {"name": "retention", "label": "Retention period", "type": "text", "required": True},
            {"name": "audit", "label": "Audit arrangements", "type": "textarea", "required": True},
            {"name": "signatory_name", "label": "Agreement signatory (name)", "type": "text", "required": True},
            {"name": "signatory_title", "label": "Signatory designation", "type": "text", "required": True},
            {"name": "dpia_status", "label": "DPIA status", "type": "select", "required": True,
             "options": ["Not started", "In preparation", "Submitted", "Accepted"]},
            {"name": "oversight", "label": "Interim data protection oversight", "type": "text"},
        ],
        "checklist": [
            ("c1", "Lawful basis named for each service"),
            ("c2", "Standard X-Road agreement with a service schedule used (no blanket MoU)"),
            ("c3", "Signatory named in the ministry"),
            ("c4", "DPIA initiated and interim oversight agreed"),
            ("c5", "The five standing safeguard conditions are accepted"),
        ],
        "documents": [
            {"type": "agreement", "label": "Signed standard X-Road member agreement", "required": True},
            {"type": "schedule", "label": "Service schedule", "required": True},
            {"type": "dpia", "label": "DPIA or DPIA plan", "required": False},
            {"type": "legal_opinion", "label": "Legal opinion / Attorney General advice", "required": False},
        ],
    },
    {
        "key": "organisational", "no": 2, "phase": "A", "layer": "Organisational", "step": "Register",
        "title": "Organisational readiness",
        "subtitle": "Accountability and nominations register",
        "question": "Who is accountable, and who runs it?",
        "gate": "Data owner, CDO, focal point, security officer, administrator and a distinct alternate nominated.",
        "submitters": ["mda_focal"],
        "chain": ["mda_ps", "micsti_coord"],
        "fields": [
            {"name": "nominations", "label": "Nominations", "type": "nominations", "required": True},
        ],
        "checklist": [
            ("c1", "Data owner and Chief Data Officer accountable"),
            ("c2", "Committee nominees, including a data management focal point"),
            ("c3", "Security officer named"),
            ("c4", "Administrator and a distinct alternate named"),
            ("c5", "Staff nominated for X-Road administrator training"),
        ],
        "documents": [
            {"type": "nomination_letter", "label": "Nomination letter signed by the Principal Secretary", "required": True},
            {"type": "org_chart", "label": "ICT / data governance organogram", "required": False},
        ],
    },
    {
        "key": "semantic", "no": 3, "phase": "A", "layer": "Semantic", "step": "Register",
        "title": "Semantic readiness",
        "subtitle": "Service contract, identifier and data definitions",
        "question": "Do we mean the same thing?",
        "gate": "OpenAPI service contract agreed; minimum attributes, common identifier, reason codes and consent reference set.",
        "submitters": ["mda_focal"],
        "chain": ["mda_ps", "micsti_semantic"],
        "fields": [
            {"name": "exchange_role", "label": "Role in the exchange", "type": "select", "required": True,
             "options": ["Provider", "Consumer", "Provider and consumer"]},
            {"name": "identifier", "label": "Common identifier", "type": "select", "required": True,
             "options": ["National ID number", "ABR identifier", "National ID and ABR"]},
            {"name": "services", "label": "Services (published to the catalogue on approval)", "type": "services",
             "required": True},
            {"name": "min_attributes", "label": "Minimum attribute list (by purpose)", "type": "textarea", "required": True},
            {"name": "reason_codes", "label": "Exchange reason codes adopted", "type": "textarea", "required": True},
            {"name": "consent_reference", "label": "Consent reference pattern", "type": "textarea", "required": True},
        ],
        "checklist": [
            ("c1", "Service contract (OpenAPI) agreed with the provider"),
            ("c2", "Minimum attribute list set by purpose"),
            ("c3", "Common identifier adopted (national ID or ABR)"),
            ("c4", "Exchange reason codes adopted"),
            ("c5", "Consent reference carried on every request"),
        ],
        "documents": [
            {"type": "openapi", "label": "OpenAPI service contract", "required": True},
            {"type": "data_dictionary", "label": "Data dictionary / attribute definitions", "required": False},
        ],
    },
    {
        "key": "usecase", "no": 4, "phase": "A", "layer": "Use case", "step": "Register",
        "title": "Use-case assessment",
        "subtitle": "RA-003 safeguards screen and scored criteria",
        "question": "Is the use case safe, valuable and deliverable?",
        "gate": "All six safeguard screen questions answered Yes; floors of 3.0 on safeguards and deliverability.",
        "submitters": ["mda_focal"],
        "chain": ["mda_ps", "micsti_coord", "tc"],
        "fields": [
            {"name": "uc_title", "label": "Use case title", "type": "text", "required": True},
            {"name": "consuming_system", "label": "Consuming system", "type": "text", "required": True},
            {"name": "providing_system", "label": "Providing system", "type": "text", "required": True},
            {"name": "children_est", "label": "Children reached (estimate, Maseru by Feb 2027)", "type": "number"},
            {"name": "uc_description", "label": "Description", "type": "textarea", "required": True},
            {"name": "ra003", "label": "RA-003 assessment", "type": "ra003", "required": True},
        ],
        "checklist": [
            ("c1", "Use case written up with the vendor"),
            ("c2", "Safeguards screen completed before scoring"),
            ("c3", "Scores agreed in a facilitated session (evidence level 2)"),
        ],
        "documents": [
            {"type": "uc_description", "label": "Use-case description", "required": True},
        ],
    },
    {
        "key": "readiness", "no": 5, "phase": "A", "layer": "MIS readiness", "step": "Register",
        "title": "MIS readiness assessment",
        "subtitle": "RA-001 readiness of the ministry and its system",
        "question": "Is the ministry, and its system, ready to join?",
        "gate": "RA-001 at evidence level 2 or above, with all six readiness gates closed.",
        "submitters": ["mda_focal", "mda_admin"],
        "chain": ["mda_ps", "micsti_security"],
        "fields": [
            {"name": "system_name", "label": "Information system", "type": "text", "required": True},
            {"name": "vendor", "label": "Vendor / support provider", "type": "text"},
            {"name": "vendor_support_until", "label": "Vendor support confirmed until", "type": "date"},
            {"name": "hosting", "label": "Hosting", "type": "select",
             "options": ["National data centre", "Ministry server room", "Vendor hosted", "Cloud"]},
            {"name": "ra001", "label": "RA-001 assessment", "type": "ra001", "required": True},
        ],
        "checklist": [
            ("c1", "Assessment completed against written anchors (0-4)"),
            ("c2", "Gate evidence attached for each closed gate"),
            ("c3", "Vendor support confirmed to February 2027 or beyond"),
        ],
        "documents": [
            {"type": "ra001_workbook", "label": "RA-001 assessment workbook", "required": True},
            {"type": "architecture", "label": "System architecture / interface description", "required": False},
        ],
    },
    {
        "key": "clearance", "no": 6, "phase": "A", "layer": "Governance", "step": "Register",
        "title": "Clearance for technical onboarding",
        "subtitle": "Technical Committee recommendation and Steering Committee approval",
        "question": "Are the legal, organisational and semantic layers settled?",
        "gate": "Stages 1-5 approved; Technical Committee recommends; Steering Committee approves.",
        "submitters": ["mda_focal"],
        "chain": ["mda_ps", "tc", "sc"],
        "fields": [
            {"name": "statement", "label": "Readiness statement", "type": "textarea", "required": True},
            {"name": "wave", "label": "Requested onboarding wave", "type": "select", "required": True,
             "options": ["Pilot (founding members)", "Wave 2 (2027/28)", "Wave 3"]},
            {"name": "budget", "label": "Security server and administrator time budgeted", "type": "select",
             "required": True, "options": YES_NO},
        ],
        "checklist": [
            ("c1", "Validated gaps closed"),
            ("c2", "Vendor support confirmed"),
            ("c3", "Administrators and alternates available for training"),
        ],
        "documents": [
            {"type": "cover_letter", "label": "Principal Secretary cover letter", "required": True},
        ],
    },
    # ------------------------------------------------------------ Phase B
    {
        "key": "install", "no": 7, "phase": "B", "layer": "Technical", "step": "Install",
        "title": "Install security server",
        "subtitle": "Security server placed in the ministry's own segment",
        "question": "Is the security server in place and hardened?",
        "gate": "Hardening, firewall rules and time synchronisation confirmed (CF-001 NW, HP, LM).",
        "submitters": ["mda_admin"],
        "chain": ["micsti_operator", "micsti_security"],
        "fields": [
            {"name": "ss_hostname", "label": "Security server hostname", "type": "text", "required": True},
            {"name": "ss_ip", "label": "Internal IP address", "type": "text", "required": True},
            {"name": "segment", "label": "Network segment / VLAN", "type": "text", "required": True},
            {"name": "xroad_version", "label": "X-Road version", "type": "select", "required": True,
             "options": ["7.8.0", "7.7.x", "7.6.x"]},
            {"name": "os", "label": "Operating system", "type": "select", "required": True,
             "options": ["Ubuntu Server 24.04 LTS", "Ubuntu Server 22.04 LTS", "RHEL 9"]},
            {"name": "firewall", "label": "Firewall rules", "type": "textarea", "required": True},
            {"name": "ntp", "label": "Time source (NTP)", "type": "text", "required": True},
        ],
        "checklist": [
            ("c1", "Security server in the ministry's own network segment"),
            ("c2", "Hardened to the CF-001 baseline; patched"),
            ("c3", "Admin UI (4000) and exchange ports never internet-facing"),
            ("c4", "Time synchronised to the national time source"),
        ],
        "documents": [
            {"type": "hardening", "label": "Hardening checklist (CF-001 HP)", "required": True},
            {"type": "network", "label": "Network / firewall diagram", "required": False},
        ],
    },
    {
        "key": "certify", "no": 8, "phase": "B", "layer": "Technical", "step": "Certify",
        "title": "Certify",
        "subtitle": "Certificate requests and key custody",
        "question": "Are keys generated safely and custody recorded?",
        "gate": "Keys generated in an HSM or token; custody recorded; auth and sign certificates issued.",
        "submitters": ["mda_admin"],
        "chain": ["micsti_operator"],
        "fields": [
            {"name": "member_class", "label": "X-Road member class", "type": "select", "required": True,
             "options": ["GOV", "COM", "NGO"]},
            {"name": "member_code", "label": "Member code", "type": "text", "required": True},
            {"name": "subsystems", "label": "Subsystem code(s)", "type": "text", "required": True},
            {"name": "key_storage", "label": "Key storage", "type": "select", "required": True,
             "options": ["Hardware security module (HSM)", "Hardware token"]},
            {"name": "custodian", "label": "Key custodian", "type": "text", "required": True},
            {"name": "custodian_alt", "label": "Alternate custodian", "type": "text", "required": True},
        ],
        "checklist": [
            ("c1", "Signing and authentication keys generated in the HSM / token"),
            ("c2", "CSRs submitted to the national CA"),
            ("c3", "Key custody and alternate recorded"),
            ("c4", "Authentication certificate registered on the Central Server"),
        ],
        "documents": [
            {"type": "custody", "label": "Key custody record", "required": True},
            {"type": "csr", "label": "Certificate signing requests", "required": False},
        ],
    },
    {
        "key": "connect", "no": 9, "phase": "B", "layer": "Technical", "step": "Connect",
        "title": "Connect and test",
        "subtitle": "Access rights and synthetic-data tests",
        "question": "Does the exchange work safely, as agreed?",
        "gate": "TLS, consent reference, reason codes and audit logs working on synthetic data.",
        "submitters": ["mda_admin"],
        "chain": ["micsti_operator", "micsti_security"],
        "fields": [
            {"name": "access_rights", "label": "Access rights granted", "type": "textarea", "required": True,
             "help": "Must match the service schedule exactly."},
            {"name": "tests", "label": "Test cases executed", "type": "textarea", "required": True},
            {"name": "result", "label": "Overall result", "type": "select", "required": True,
             "options": ["All passed", "Passed with observations", "Failed"]},
        ],
        "checklist": [
            ("c1", "TLS between information system and security server"),
            ("c2", "Consent reference carried on every request"),
            ("c3", "Reason codes returned on every decline"),
            ("c4", "Audit logs present at both ends"),
            ("c5", "Synthetic data only"),
        ],
        "documents": [
            {"type": "test_report", "label": "Synthetic-data test report", "required": True},
        ],
    },
    {
        "key": "golive", "no": 10, "phase": "B", "layer": "Governance", "step": "Go live",
        "title": "Go live",
        "subtitle": "DPIA accepted; Technical Committee recommendation recorded",
        "question": "Are we ready for live data?",
        "gate": "DPIA accepted; security contact and monitoring confirmed; TC recommends; SC approves.",
        "submitters": ["mda_focal"],
        "chain": ["mda_ps", "tc", "sc"],
        "fields": [
            {"name": "dpia_date", "label": "DPIA accepted on", "type": "date", "required": True},
            {"name": "security_contact", "label": "Security incident contact", "type": "text", "required": True},
            {"name": "golive_date", "label": "Proposed go-live date", "type": "date", "required": True},
        ],
        "checklist": [
            ("c1", "DPIA accepted"),
            ("c2", "Security contact confirmed"),
            ("c3", "Operational monitoring confirmed"),
            ("c4", "Evidence at level 3 (verified) for go-live"),
        ],
        "documents": [
            {"type": "dpia_acceptance", "label": "DPIA acceptance letter", "required": True},
            {"type": "golive_checklist", "label": "Go-live readiness checklist", "required": False},
        ],
    },
]

STAGE_BY_KEY = {s["key"]: s for s in STAGES}
STAGE_ORDER = [s["key"] for s in STAGES]


def ra001_score(a):
    """Return readiness index (%), band and open gates for an RA-001 answer set."""
    a = a or {}
    scores = a.get("scores", {}) or {}
    total = 0.0
    for key, _label, weight in RA001_DIMENSIONS:
        try:
            v = max(0.0, min(4.0, float(scores.get(key, 0) or 0)))
        except (TypeError, ValueError):
            v = 0.0
        total += weight * v / 4.0
    gates = a.get("gates", {}) or {}
    open_gates = [g for g, _ in RA001_GATES if gates.get(g) != "Yes"]
    if total >= 75:
        band = "Ready"
    elif total >= 60:
        band = "Ready with limited adjustment"
    elif total >= 40:
        band = "Needs remediation"
    else:
        band = "Not ready"
    if open_gates and band in ("Ready", "Ready with limited adjustment"):
        band = "Needs remediation"
    try:
        level = int(a.get("evidence_level") or 0)
    except (TypeError, ValueError):
        level = 0
    return {"index": round(total, 1), "band": band, "open_gates": open_gates, "evidence_level": level}


def ra003_score(a):
    """Return the weighted score (out of 5), screen result and floor checks."""
    a = a or {}
    screen = a.get("screen", {}) or {}
    failed_screen = [q for q, _ in RA003_SCREEN if screen.get(q) != "Yes"]
    scores = a.get("scores", {}) or {}
    vals = {}
    for key, _label, _w in RA003_CRITERIA:
        try:
            vals[key] = max(0.0, min(5.0, float(scores.get(key, 0) or 0)))
        except (TypeError, ValueError):
            vals[key] = 0.0
    total = sum(vals[k] * w for k, _l, w in RA003_CRITERIA) / 100.0
    floors_ok = vals["safeguards"] >= 3.0 and vals["deliverable"] >= 3.0
    if failed_screen:
        outcome = "Fails safeguards screen"
    elif not floors_ok:
        outcome = "Below floor - not ranked"
    else:
        outcome = "Eligible"
    return {"score": round(total, 2), "failed_screen": failed_screen, "floors_ok": floors_ok, "outcome": outcome}


def public_model():
    """Serialisable description of the process for the UI and API consumers."""
    return {
        "roles": ROLES,
        "stages": [
            {**s, "checklist": [{"id": i, "label": l} for i, l in s["checklist"]]} for s in STAGES
        ],
        "nomination_roles": NOMINATION_ROLES,
        "ra001": {"dimensions": [{"key": k, "label": l, "weight": w} for k, l, w in RA001_DIMENSIONS],
                  "gates": [{"id": g, "label": l} for g, l in RA001_GATES]},
        "ra003": {"screen": [{"id": q, "label": l} for q, l in RA003_SCREEN],
                  "criteria": [{"key": k, "label": l, "weight": w} for k, l, w in RA003_CRITERIA]},
        "instruments": LEGAL_INSTRUMENTS,
    }
