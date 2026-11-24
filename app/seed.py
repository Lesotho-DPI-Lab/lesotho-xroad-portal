"""Synthetic demonstration data. No real persons or records.

Members are placed at different points of the onboarding path so the workshop can
see every state: not started, awaiting endorsement, returned, in review, cleared,
and in technical onboarding.
"""
import json
import os
import sqlite3
import uuid

from werkzeug.security import generate_password_hash

from .db import init_schema
from .pdf import make_pdf
from .stages import ROLES, STAGE_BY_KEY, STAGE_ORDER

MEMBERS = [
    # code, name, short, systems, wave, is_operator
    ("MICSTI", "Ministry of Information, Communications, Science, Technology and Innovation", "MICSTI",
     "Central Server, trust services, management services", "Operator", 1),
    ("MGYSD", "Ministry of Gender, Youth and Social Development", "Social Development", "NISSA", "Pilot", 0),
    ("MOH", "Ministry of Health", "Health", "HMIS (DHIS2), eRegister, Bophelo ka Mosebeletsi", "Pilot", 0),
    ("MHAP", "Ministry of Home Affairs and Police", "Home Affairs", "Identity System, Civil registration", "Pilot", 0),
    ("MOET", "Ministry of Education and Training", "Education", "LEMIS", "Pilot", 0),
    ("MLGC", "Ministry of Local Government and Chieftainship", "Local Government", "Chieftainship register (planned)",
     "Wave 2", 0),
]

OPERATOR_USERS = [
    # username, name, title, role
    ("micsti.legal", "Mpho Lerotholi", "Legal & Data Protection Officer, MICSTI", "micsti_legal"),
    ("micsti.coord", "Thabo Mokhele", "Onboarding Coordinator, X-Road Pilot PMO", "micsti_coord"),
    ("micsti.semantic", "Lineo Ramakatane", "Interoperability & Semantic Architect", "micsti_semantic"),
    ("micsti.security", "Tumelo Sekhesa", "Cybersecurity Lead, X-Road Pilot", "micsti_security"),
    ("micsti.operator", "Rethabile Nthejane", "X-Road Central Server Administrator, MICSTI", "micsti_operator"),
    ("tc.chair", "Dr Nthabiseng Moloi", "Chair, Joint Technical Committee", "tc"),
    ("sc.chair", "Motlatsi Letsie", "Chair, Joint Steering Committee", "sc"),
    ("portal.admin", "Portal Administrator", "MICSTI Department of ICT", "admin"),
]

MEMBER_USERS = {
    # prefix: (focal, admin, ps)
    "MGYSD": ("social", "Nthati Khoeli", "Bokang Seeiso", "Sello Mphutlane"),
    "MOH": ("health", "Palesa Mokoena", "Teboho Ntsane", "Dr Mamello Phafane"),
    "MHAP": ("homeaffairs", "Refiloe Makara", "Tsepo Lebona", "Masechaba Ramoholi"),
    "MOET": ("education", "Lerato Molapo", "Katleho Tau", "Puleng Matela"),
    "MLGC": ("localgov", "Limpho Mohapi", "Neo Thamae", "Lehlohonolo Pitso"),
}


def _ts(day, hour=9, minute=0):
    return f"2026-{day}T{hour:02d}:{minute:02d}:00Z"


class Seeder:
    def __init__(self, db, upload_dir):
        self.db, self.upload_dir = db, upload_dir
        self.users, self.members = {}, {}

    def user_for(self, role, member_code):
        if ROLES[role]["scope"] == "member":
            prefix = MEMBER_USERS[member_code][0]
            suffix = {"mda_focal": "focal", "mda_admin": "admin", "mda_ps": "ps"}[role]
            return self.users[f"{prefix}.{suffix}"]
        return next(v for v in self.users.values() if v[1] == role)

    def audit(self, ts, uid, mid, action, detail):
        self.db.execute("INSERT INTO audit (ts, user_id, member_id, action, detail) VALUES (?,?,?,?,?)",
                        (ts, uid, mid, action, detail))

    def add_doc(self, rec_id, mid, member_code, stage, doc, uid, ts, level):
        stored = f"{uuid.uuid4().hex}.pdf"
        name = f"{member_code}_{doc['type']}_SYNTHETIC.pdf"
        pdf = make_pdf(doc["label"], [
            f"Member: {member_code}", f"Stage: {stage['no']}. {stage['title']}",
            f"Evidence level: {level}", "Prepared for the ICT Cadre Management Workshop, 24 November 2026.",
            "This file exists only to demonstrate the evidence upload and review workflow."])
        with open(os.path.join(self.upload_dir, stored), "wb") as f:
            f.write(pdf)
        self.db.execute("INSERT INTO documents (record_id, doc_type, filename, stored_name, size, evidence_level, "
                        "uploaded_by, uploaded_at) VALUES (?,?,?,?,?,?,?,?)",
                        (rec_id, doc["type"], name, stored, len(pdf), level, uid, ts))

    def stage(self, code, key, data, outcome, day, comments=None, level_docs=2):
        """outcome: 'draft' | 'approved' | ('in_review', level) | ('returned', at_level, reason)"""
        s, mid = STAGE_BY_KEY[key], self.members[code]
        chk = {c: True for c, _ in s["checklist"]}
        submitter = self.user_for(s["submitters"][0], code)[0]
        cur = self.db.execute(
            "INSERT INTO stage_records (member_id, stage_key, status, level, data, checklist, updated_at) "
            "VALUES (?,?,?,?,?,?,?)", (mid, key, "draft", 0, json.dumps(data), json.dumps(chk), _ts(day, 8)))
        rid = cur.lastrowid
        for d in s["documents"]:
            if d["required"] or outcome == "approved":
                self.add_doc(rid, mid, code, s, d, submitter, _ts(day, 8, 30), level_docs)
        if outcome == "draft":
            self.audit(_ts(day, 8), submitter, mid, "stage.save", f"{s['title']} saved as draft")
            return
        comments = comments or {}

        def decision(uid, role, action, comment, ts):
            self.db.execute("INSERT INTO decisions (record_id, user_id, role, action, comment, created_at) "
                            "VALUES (?,?,?,?,?,?)", (rid, uid, role, action, comment, ts))

        sub_ts = _ts(day, 9)
        decision(submitter, s["submitters"][0], "submitted", comments.get("submit", ""), sub_ts)
        self.audit(sub_ts, submitter, mid, "stage.submit", f"{s['title']} submitted")
        stop = len(s["chain"]) if outcome == "approved" else outcome[1]
        for i, role in enumerate(s["chain"][:stop]):
            uid = self.user_for(role, code)[0]
            word = {"mda_ps": "endorsed", "tc": "recommended", "sc": "approved"}.get(role, "approved")
            ts = _ts(day, 10 + 2 * i)
            decision(uid, role, word, comments.get(role, ""), ts)
            self.audit(ts, uid, mid, "stage.approve", f"{s['title']} {word} by {ROLES[role]['label']}")
        if outcome == "approved":
            self.db.execute("UPDATE stage_records SET status='approved', approved_at=?, submitted_at=?, "
                            "submitted_by=?, updated_at=? WHERE id=?",
                            (_ts(day, 16), sub_ts, submitter, _ts(day, 16), rid))
        elif outcome[0] == "in_review":
            self.db.execute("UPDATE stage_records SET status='in_review', level=?, submitted_at=?, submitted_by=?, "
                            "updated_at=? WHERE id=?", (outcome[1], sub_ts, submitter, _ts(day, 12), rid))
        elif outcome[0] == "returned":
            role = s["chain"][outcome[1]]
            uid = self.user_for(role, code)[0]
            ts = _ts(day, 15)
            decision(uid, role, "returned", outcome[2], ts)
            self.audit(ts, uid, mid, "stage.return", f"{s['title']} returned by {ROLES[role]['label']}")
            self.db.execute("UPDATE stage_records SET status='returned', level=0, submitted_at=?, submitted_by=?, "
                            "updated_at=? WHERE id=?", (sub_ts, submitter, ts, rid))


def _noms(focal, admin, ps, alt, extra_trainee):
    return [
        {"role": "Data Owner", "name": ps, "designation": "Principal Secretary", "email": "", "phone": ""},
        {"role": "Chief Data Officer", "name": "Kananelo Mofokeng", "designation": "Director, Planning",
         "email": "", "phone": ""},
        {"role": "Data Management Focal Point", "name": focal, "designation": "Senior Systems Analyst",
         "email": "", "phone": ""},
        {"role": "Security Officer", "name": "Ts'episo Mahao", "designation": "ICT Security Officer",
         "email": "", "phone": ""},
        {"role": "Security Server Administrator", "name": admin, "designation": "Systems Administrator",
         "email": "", "phone": ""},
        {"role": "Alternate Administrator", "name": alt, "designation": "Network Administrator",
         "email": "", "phone": ""},
        {"role": "Technical Committee Nominee", "name": focal, "designation": "Senior Systems Analyst",
         "email": "", "phone": ""},
        {"role": "Training Nominee", "name": admin, "designation": "Systems Administrator", "email": "", "phone": ""},
        {"role": "Training Nominee", "name": extra_trainee, "designation": "Database Administrator",
         "email": "", "phone": ""},
    ]


def _legal(purpose, attributes, ps, instruments, dpia="In preparation"):
    return {
        "lawful_basis": "Statutory function (named Act)",
        "instrument": instruments,
        "purpose": purpose,
        "attributes": attributes,
        "retention": "Exchange logs 7 years (audit); payload not retained beyond the transaction",
        "audit": "Message logs at both security servers; quarterly access review by the Security Officer; "
                 "annual audit by the Operator.",
        "signatory_name": ps, "signatory_title": "Principal Secretary",
        "dpia_status": dpia,
        "oversight": "Interim oversight by the Joint Steering Committee pending the Data Protection Commission",
    }


def seed(app, reset=False):
    cfg = app.config
    db = sqlite3.connect(cfg["DATABASE"])
    if reset:
        for t in ("audit", "decisions", "documents", "services", "stage_records", "users", "members"):
            db.execute(f"DROP TABLE IF EXISTS {t}")
        for f in os.listdir(cfg["UPLOAD_DIR"]):
            os.remove(os.path.join(cfg["UPLOAD_DIR"], f))
    init_schema(db)
    pw = generate_password_hash(cfg["DEMO_PASSWORD"])
    sd = Seeder(db, cfg["UPLOAD_DIR"])

    for code, name, short, systems, wave, op in MEMBERS:
        cur = db.execute("INSERT INTO members (code, name, short, systems, wave, is_operator) VALUES (?,?,?,?,?,?)",
                         (code, name, short, systems, wave, op))
        sd.members[code] = cur.lastrowid
    for username, name, title, role in OPERATOR_USERS:
        cur = db.execute("INSERT INTO users (username, password_hash, full_name, title, email, role, member_id) "
                         "VALUES (?,?,?,?,?,?,?)", (username, pw, name, title, f"{username}@demo.invalid", role,
                                                    sd.members["MICSTI"]))
        sd.users[username] = (cur.lastrowid, role)
    for code, (prefix, focal, admin, ps) in MEMBER_USERS.items():
        for suffix, nm, role, title in (("focal", focal, "mda_focal", "Data Management Focal Point"),
                                        ("admin", admin, "mda_admin", "Security Server Administrator"),
                                        ("ps", ps, "mda_ps", "Principal Secretary")):
            un = f"{prefix}.{suffix}"
            cur = db.execute("INSERT INTO users (username, password_hash, full_name, title, email, role, member_id) "
                             "VALUES (?,?,?,?,?,?,?)", (un, pw, nm, title, f"{un}@demo.invalid", role,
                                                        sd.members[code]))
            sd.users[un] = (cur.lastrowid, role)

    # ---------------------------------------------- Social Development: in technical onboarding
    c = "MGYSD"
    sd.stage(c, "legal", _legal(
        "Verify the identity of household members enrolled in NISSA against the national identity service, "
        "so that social assistance reaches the right child without repeated certified copies.",
        "Request: national ID or ABR identifier. Response: match (yes/no), surname, given names, date of birth, sex.",
        "Sello Mphutlane", ["Data Protection Act 2011", "National Identity Cards Act 2011 (MoU route)"],
        dpia="Submitted"), "approved", "10-28",
        {"micsti_legal": "Lawful basis confirmed. Service schedule complete."})
    sd.stage(c, "organisational", {"nominations": _noms("Nthati Khoeli", "Bokang Seeiso", "Sello Mphutlane",
                                                        "Lisebo Ntho", "Mohau Khatleli")}, "approved", "10-30",
             {"micsti_coord": "All nominations verified. Two trainees added to the December cohort."})
    sd.stage(c, "semantic", {
        "exchange_role": "Provider and consumer", "identifier": "National ID and ABR",
        "services": [{"subsystem": "NISSA", "code": "householdAssistanceStatus", "name": "Household assistance status",
                      "description": "Returns whether a child's household receives social assistance (yes/no, "
                                     "programme code). No household listing.", "version": "v1"}],
        "min_attributes": "Identifier; assistance status (yes/no); programme code; effective date.",
        "reason_codes": "SA-01 Eligibility check; SA-02 School support referral; DEC-xx decline codes per RC-001.",
        "consent_reference": "Consent reference ID captured at NISSA enrolment and carried in the X-Road "
                             "userId/issue header.",
    }, "approved", "11-03", {"micsti_semantic": "OpenAPI contract v1 agreed with Home Affairs."})
    sd.stage(c, "usecase", {
        "uc_title": "Verify household members' identity", "consuming_system": "NISSA",
        "providing_system": "Identity System (Home Affairs)", "children_est": 5000,
        "uc_description": "At NISSA enrolment and recertification, verify each household member's identifier "
                          "against the national identity service instead of collecting certified copies.",
        "ra003": {"screen": {q: "Yes" for q in ("S1", "S2", "S3", "S4", "S5", "S6")},
                  "scores": {"value": 4.5, "safeguards": 5, "technical": 4, "deliverable": 4, "identity": 4}},
    }, "approved", "11-05", {"tc": "Lead use case - endorsed by the Joint Committee on 5 November."})
    sd.stage(c, "readiness", {
        "system_name": "NISSA", "vendor": "Synthetic Vendor (Pty) Ltd", "vendor_support_until": "2027-06-30",
        "hosting": "National data centre",
        "ra001": {"evidence_level": 2, "scores": {"integration": 3, "data": 3, "technology": 3, "security": 3,
                                                  "legal": 2, "capacity": 3},
                  "gates": {g: "Yes" for g in ("D1", "A1", "C2", "L1", "L7", "L8")}},
    }, "approved", "11-10", {"micsti_security": "Evidence level 2. All six gates clear."})
    sd.stage(c, "clearance", {"statement": "Legal, organisational and semantic layers settled; RA-001 gates "
                                           "clear; vendor support confirmed to June 2027.",
                              "wave": "Pilot (founding members)", "budget": "Yes"}, "approved", "11-17",
             {"tc": "Recommended for technical onboarding.", "sc": "Approved by round robin."})
    sd.stage(c, "install", {
        "ss_hostname": "ss01.mgysd.xroad.demo", "ss_ip": "10.255.100.121", "segment": "VLAN 121 - MGYSD member zone",
        "xroad_version": "7.8.0", "os": "Ubuntu Server 24.04 LTS",
        "firewall": "In: 5500, 5577 from peer security servers; 443/8443 from NISSA app servers only; 4000 from "
                    "admin jump host only. Out: central server 80/4001, OCSP and TSA.",
        "ntp": "ntp.gov.ls.demo (stratum 2)"}, "approved", "11-20")
    sd.stage(c, "certify", {
        "member_class": "GOV", "member_code": "MGYSD", "subsystems": "NISSA",
        "key_storage": "Hardware token", "custodian": "Bokang Seeiso", "custodian_alt": "Lisebo Ntho"},
        ("in_review", 0), "11-23")

    # ---------------------------------------------- Health: semantic stage under review
    c = "MOH"
    sd.stage(c, "legal", _legal(
        "Confirm a child's identifier at immunisation so that the HMIS record links to the child registered at birth.",
        "Request: ABR identifier. Response: match (yes/no), date of birth, sex.", "Dr Mamello Phafane",
        ["Data Protection Act 2011", "National Identity Cards Act 2011 (MoU route)"]), "approved", "11-06")
    sd.stage(c, "organisational", {"nominations": _noms("Palesa Mokoena", "Teboho Ntsane", "Dr Mamello Phafane",
                                                        "Relebohile Sefako", "Karabo Motsamai")}, "approved", "11-12")
    sd.stage(c, "semantic", {
        "exchange_role": "Provider and consumer", "identifier": "ABR identifier",
        "services": [{"subsystem": "HMIS", "code": "immunisationStatus", "name": "Immunisation status",
                      "description": "Returns whether a child is up to date with the EPI schedule (yes/no).",
                      "version": "v1"}],
        "min_attributes": "Identifier; up-to-date status (yes/no); last dose date.",
        "reason_codes": "HL-01 Immunisation identifier check; DEC-xx decline codes per RC-001.",
        "consent_reference": "Consent reference captured at the clinic and stored against the DHIS2 tracker event.",
    }, ("in_review", 1), "11-21")

    # ---------------------------------------------- Home Affairs: legal returned
    c = "MHAP"
    sd.stage(c, "legal", _legal(
        "Provide identity verification and birth registration status to entitled members of the exchange.",
        "Response only: match (yes/no) and minimum attributes per service schedule.", "Masechaba Ramoholi",
        ["National Identity Cards Act 2011 (MoU route)", "Registration of Births and Deaths Act 1973 (under review)"],
        dpia="Not started"),
        ("returned", 1, "Civil registration data cannot be shared under the 1973 Act while it is under review. "
                        "Split the schedule: proceed with the identity service under the National Identity Cards "
                        "Act (MoU route); hold birth registration status until the Act is amended. "
                        "Please also initiate the DPIA."), "11-18")

    # ---------------------------------------------- Education: awaiting PS endorsement
    c = "MOET"
    sd.stage(c, "legal", _legal(
        "Confirm a learner's identifier at Grade 1 enrolment so that LEMIS records link to the child registered at "
        "birth, without certified copies.", "Request: ABR identifier. Response: match (yes/no), date of birth.",
        "Puleng Matela", ["Data Protection Act 2011", "National Identity Cards Act 2011 (MoU route)"]),
        ("in_review", 0), "11-22")

    # ---------------------------------------------- Service catalogue (provider-side proposals)
    for code, sub, svc, name, desc, status in [
        ("MHAP", "IDENTITY", "verifyPerson", "Verify person",
         "Verify a person by national ID or ABR identifier; returns match and minimum attributes.", "Proposed"),
        ("MHAP", "CIVREG", "birthRegistrationStatus", "Birth registration status",
         "Returns whether a birth is registered (yes/no). On hold pending review of the 1973 Act.", "Proposed"),
        ("MGYSD", "NISSA", "householdAssistanceStatus", "Household assistance status",
         "Returns whether a child's household receives social assistance (yes/no, programme code).", "Agreed"),
        ("MOH", "HMIS", "immunisationStatus", "Immunisation status",
         "Returns whether a child is up to date with the EPI schedule (yes/no).", "Proposed"),
    ]:
        db.execute("INSERT INTO services (member_id, subsystem, code, name, description, version, status) "
                   "VALUES (?,?,?,?,?,?,?)", (sd.members[code], sub, svc, name, desc, "v1", status))
    db.commit()
    db.close()
