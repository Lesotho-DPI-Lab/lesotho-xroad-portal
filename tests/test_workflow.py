"""End-to-end workflow tests. Run: .venv/bin/python -m unittest discover -s tests -v"""
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["PORTAL_DATA_DIR"] = tempfile.mkdtemp(prefix="xrp-test-")

from app import create_app  # noqa: E402

H = {"X-Requested-With": "portal"}
PW = "Demo@2026"
LG = 6  # Local Government member id in seed order

FULL = {
    "legal": {
        "lawful_basis": "Statutory function (named Act)", "instrument": ["Data Protection Act 2011"],
        "purpose": "Verify identity for chieftainship letters", "attributes": "ID, match yes/no",
        "retention": "7 years", "audit": "Logs at both ends", "signatory_name": "L. Pitso",
        "signatory_title": "Principal Secretary", "dpia_status": "In preparation"},
    "organisational": {"nominations": [
        {"role": "Data Owner", "name": "A"}, {"role": "Chief Data Officer", "name": "B"},
        {"role": "Data Management Focal Point", "name": "C"}, {"role": "Security Officer", "name": "D"},
        {"role": "Security Server Administrator", "name": "E"}, {"role": "Alternate Administrator", "name": "F"},
        {"role": "Training Nominee", "name": "E"}]},
    "semantic": {"exchange_role": "Consumer", "identifier": "National ID number",
                 "services": [{"subsystem": "CHIEF", "code": "residenceConfirmation", "name": "Residence confirmation"}],
                 "min_attributes": "ID", "reason_codes": "LG-01", "consent_reference": "Consent ID header"},
    "usecase": {"uc_title": "Chief's letter", "consuming_system": "Register", "providing_system": "Identity",
                "uc_description": "Replace paper letters",
                "ra003": {"screen": {f"S{i}": "Yes" for i in range(1, 7)},
                          "scores": {"value": 4, "safeguards": 4, "technical": 3, "deliverable": 3, "identity": 3}}},
    "readiness": {"system_name": "Register",
                  "ra001": {"evidence_level": 2,
                            "scores": {k: 3 for k in ("integration", "data", "technology", "security", "legal",
                                                      "capacity")},
                            "gates": {g: "Yes" for g in ("D1", "A1", "C2", "L1", "L7", "L8")}}},
    "clearance": {"statement": "Ready", "wave": "Wave 2 (2027/28)", "budget": "Yes"},
    "install": {"ss_hostname": "ss01", "ss_ip": "10.0.0.5", "segment": "VLAN 1", "xroad_version": "7.8.0",
                "os": "Ubuntu Server 24.04 LTS", "firewall": "5500/5577", "ntp": "ntp"},
    "certify": {"member_class": "GOV", "member_code": "MLGC", "subsystems": "CHIEF",
                "key_storage": "Hardware token", "custodian": "E", "custodian_alt": "F"},
    "connect": {"access_rights": "As schedule", "tests": "T1-T5", "result": "All passed"},
    "golive": {"dpia_date": "2027-02-01", "security_contact": "D", "golive_date": "2027-02-20"},
}

SUBMITTER = {"install": "localgov.admin", "certify": "localgov.admin", "connect": "localgov.admin",
             "readiness": "localgov.focal"}
USER_FOR_ROLE = {"mda_ps": "localgov.ps", "micsti_legal": "micsti.legal", "micsti_coord": "micsti.coord",
                 "micsti_semantic": "micsti.semantic", "micsti_security": "micsti.security",
                 "micsti_operator": "micsti.operator", "tc": "tc.chair", "sc": "sc.chair"}


class Workflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.model = cls.app.test_client().get("/api/v1/model").json

    def login(self, username):
        c = self.app.test_client()
        r = c.post("/api/v1/auth/login", json={"username": username, "password": PW}, headers=H)
        self.assertEqual(r.status_code, 200, username)
        return c

    def test_01_seeded_state(self):
        c = self.login("micsti.coord")
        d = c.get("/api/v1/dashboard").json
        states = {m["code"]: m["overall"] for m in d["members"]}
        self.assertEqual(states["MGYSD"], "Technical onboarding")
        self.assertEqual(states["MLGC"], "Not started")
        self.assertEqual(len(d["members"]), 5)

    def test_02_auth_and_csrf(self):
        c = self.app.test_client()
        self.assertEqual(c.get("/api/v1/dashboard").status_code, 401)
        r = c.post("/api/v1/auth/login", json={"username": "health.focal", "password": "wrong"}, headers=H)
        self.assertEqual(r.status_code, 401)
        r = c.post("/api/v1/auth/login", json={"username": "health.focal", "password": PW})
        self.assertEqual(r.status_code, 403)  # missing CSRF header

    def test_03_member_isolation(self):
        c = self.login("health.focal")
        self.assertEqual(c.get(f"/api/v1/members/{LG}").status_code, 403)
        self.assertEqual(len(c.get("/api/v1/members").json["members"]), 1)

    def test_04_locked_and_gate_enforced(self):
        c = self.login("localgov.focal")
        r = c.put(f"/api/v1/members/{LG}/stages/organisational", json={"data": {}}, headers=H)
        self.assertEqual(r.status_code, 403)  # locked until legal approved
        r = c.post(f"/api/v1/members/{LG}/stages/legal/submit", headers=H)
        self.assertEqual(r.status_code, 422)
        self.assertTrue(r.json["details"])

    def test_05_wrong_reviewer_cannot_decide(self):
        c = self.login("micsti.legal")  # Education legal is awaiting the Education PS, not Legal
        r = c.post("/api/v1/members/5/stages/legal/decision", json={"action": "approve"}, headers=H)
        self.assertEqual(r.status_code, 403)
        ps_other = self.login("health.ps")
        r = ps_other.post("/api/v1/members/5/stages/legal/decision", json={"action": "approve"}, headers=H)
        self.assertEqual(r.status_code, 403)

    def test_06_return_requires_reason_and_resubmit(self):
        ps = self.login("education.ps")
        r = ps.post("/api/v1/members/5/stages/legal/decision", json={"action": "return"}, headers=H)
        self.assertEqual(r.status_code, 422)
        r = ps.post("/api/v1/members/5/stages/legal/decision",
                    json={"action": "return", "comment": "Add retention"}, headers=H)
        self.assertEqual(r.json["record"]["status"], "returned")
        f = self.login("education.focal")
        r = f.post("/api/v1/members/5/stages/legal/submit", headers=H)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["record"]["status"], "in_review")

    def test_07_ra_gates(self):
        c = self.login("localgov.focal")
        from app.stages import ra001_score, ra003_score
        s = ra001_score({"evidence_level": 2, "scores": {k: 4 for k in ("integration", "data", "technology",
                                                                         "security", "legal", "capacity")},
                         "gates": {"D1": "No"}})
        self.assertEqual(s["index"], 100.0)
        self.assertEqual(s["band"], "Needs remediation")
        t = ra003_score({"screen": {f"S{i}": "Yes" for i in range(1, 7)},
                         "scores": {"value": 5, "safeguards": 2.5, "technical": 5, "deliverable": 5, "identity": 5}})
        self.assertEqual(t["outcome"], "Below floor - not ranked")
        self.assertIsNotNone(c)

    def test_08_full_path_to_go_live(self):
        for stage in self.model["stages"]:
            key = stage["key"]
            sub = self.login(SUBMITTER.get(key, "localgov.focal"))
            base = f"/api/v1/members/{LG}/stages/{key}"
            chk = {c["id"]: True for c in stage["checklist"]}
            r = sub.put(base, json={"data": FULL[key], "checklist": chk}, headers=H)
            self.assertEqual(r.status_code, 200, (key, r.json))
            for d in stage["documents"]:
                if d["required"]:
                    r = sub.post(base + "/documents", headers=H, content_type="multipart/form-data",
                                 data={"doc_type": d["type"], "evidence_level": "2",
                                       "file": (io.BytesIO(b"%PDF-1.4 synthetic"), f"{d['type']}.pdf")})
                    self.assertEqual(r.status_code, 200, (key, r.json))
            r = sub.post(base + "/submit", headers=H)
            self.assertEqual(r.status_code, 200, (key, r.json))
            for role in stage["chain"]:
                rv = self.login(USER_FOR_ROLE[role])
                r = rv.post(base + "/decision", json={"action": "approve", "comment": "ok"}, headers=H)
                self.assertEqual(r.status_code, 200, (key, role, r.json))
            self.assertEqual(r.json["record"]["status"], "approved", key)
        c = self.login("micsti.coord")
        m = c.get(f"/api/v1/members/{LG}").json["member"]
        self.assertEqual(m["overall"], "Live on X-Road")
        svc = [s for s in c.get("/api/v1/services").json["services"] if s["code"] == "residenceConfirmation"]
        self.assertEqual(svc[0]["status"], "Live")
        doc = c.get(f"/api/v1/members/{LG}/stages/legal").json["documents"][0]
        self.assertEqual(c.get(f"/api/v1/documents/{doc['id']}").status_code, 200)

    def test_09_upload_rejects_bad_type(self):
        c = self.login("homeaffairs.focal")
        r = c.post("/api/v1/members/4/stages/legal/documents", headers=H, content_type="multipart/form-data",
                   data={"doc_type": "agreement", "file": (io.BytesIO(b"MZ"), "x.exe")})
        self.assertEqual(r.status_code, 422)

    def test_10_reset(self):
        self.assertEqual(self.login("micsti.coord").post("/api/v1/admin/reset", headers=H).status_code, 403)
        self.assertEqual(self.login("portal.admin").post("/api/v1/admin/reset", headers=H).status_code, 200)
        m = self.login("micsti.coord").get(f"/api/v1/members/{LG}").json["member"]
        self.assertEqual(m["overall"], "Not started")


if __name__ == "__main__":
    unittest.main()
