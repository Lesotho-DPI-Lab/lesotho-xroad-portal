# Lesotho X-Road Member Onboarding Portal (demonstration)

A lightweight web portal where line ministries complete the **non-technical onboarding** for Lesotho's National
Data Exchange (X-Road): the legal, organisational and semantic layers, the use-case and MIS readiness assessments, and
governance clearance. After that comes **technical onboarding**: install, certify, connect and go live.

Built for the X-Road pilot demonstration at the ICT Cadre Management Workshop (Day 2, 24 November 2026).
**This is a demonstration environment that uses synthetic data only.** All names, accounts and documents are made up.

- **Live (staging VM):** http://10.255.100.188
- **Demo password for every account:** `Demo@2026` (the accounts are listed on the sign-in page)
- **API:** `http://10.255.100.188/api/v1/openapi.json`

## How it maps to PR-013 (slides 16 to 18)

| PR-013 | In the portal |
|---|---|
| Slide 16: the four layers (Legal, Organisational, Semantic, Technical) must be settled before any server is configured (Joint Committee resolution R12) | Phase A (stages 1 to 6) must be approved before Phase B (stages 7 to 10) unlocks |
| Slide 17, step 1 **Agree**: standard agreement and service schedule | Stage 1, Legal readiness. Includes an online agreement template pre-filled from the submission |
| Slide 17, step 2 **Register**: focal points, administrator and alternate; RA-001 | Stages 2 to 6: Organisational (nominations register), Semantic (OpenAPI contract, identifier, reason codes, consent reference), Use case (RA-003), MIS readiness (RA-001 at evidence level 2 or above), Clearance (Technical Committee and Steering Committee) |
| Slide 17, step 3 **Install** | Stage 7: security server in the ministry's own segment; hardening, firewall and NTP |
| Slide 17, step 4 **Certify** | Stage 8: keys in an HSM or token; custody and alternate recorded |
| Slide 17, step 5 **Connect** | Stage 9: access rights match the agreement; TLS, consent reference, reason codes and audit logs tested on synthetic data |
| Slide 17, step 6 **Go live** | Stage 10: DPIA accepted; Technical Committee recommends; Steering Committee approves |
| Slide 17 features: agreement templates, nominations register, evidence uploads, status view per member, service catalogue | All five are implemented: *Templates & guidance*, *Nominations register*, *Evidence* on every stage (evidence levels 1 to 3), *Member status*, *Service catalogue* |
| Slide 18: RA-001 (six weighted dimensions, six gates, bands) and RA-003 (safeguards screen, five weighted criteria, 3.0 floors) | Scored live in the form. The server enforces the gates when a stage is submitted |

### Governance hierarchy (approval chains)

Each submission goes up a chain of approvers. Any approver can return it, but must give a reason.

| Stage | Prepared by | Approval chain |
|---|---|---|
| 1 Legal | Data Management Focal Point | Principal Secretary / Data Owner → Legal & Data Protection Officer |
| 2 Organisational | Focal Point | PS → Onboarding Coordinator (PMO) |
| 3 Semantic | Focal Point | PS → Interoperability & Semantic Architect |
| 4 Use case (RA-003) | Focal Point | PS → Onboarding Coordinator → Technical Committee |
| 5 MIS readiness (RA-001) | Focal Point / Security Server Admin | PS → Cybersecurity Lead |
| 6 Clearance | Focal Point | PS → Technical Committee → Steering Committee |
| 7 Install | Security Server Administrator | X-Road Operator → Cybersecurity Lead |
| 8 Certify | Security Server Administrator | X-Road Operator |
| 9 Connect | Security Server Administrator | X-Road Operator → Cybersecurity Lead |
| 10 Go live | Focal Point | PS → Technical Committee → Steering Committee |

### Starting state of the synthetic data

| Ministry | State | Demonstrates |
|---|---|---|
| Social Development (NISSA) | Cleared; Install approved; **Certify awaiting X-Road Operator** | Technical onboarding |
| Health (HMIS) | **Semantic awaiting Semantic Architect** | Mid-chain review |
| Home Affairs | **Legal returned** (review of the Births and Deaths Act 1973) | Return with reason |
| Education (LEMIS) | **Legal awaiting PS endorsement** | Ministry-internal endorsement |
| Local Government (Wave 2) | Not started | A full walk-through from scratch |

## Suggested live demo (about 10 minutes)

1. Sign in as `micsti.coord`: dashboard KPIs, member status, service catalogue, nominations register.
2. Sign in as `localgov.focal`: open stage 1 and fill it in. Press **Submit** to show the gate refusing an incomplete package. Tick the checklist, upload evidence and submit.
3. Sign in as `localgov.ps`: endorse it, or return it with a reason. Then sign in as `micsti.legal` and approve it. Stage 2 unlocks.
4. Sign in as `micsti.operator`: approve Social Development's **Certify** stage (technical onboarding).
5. Sign in as `education.ps`: endorse Education's legal package.
6. Sign in as `portal.admin`: **Reset demonstration data** puts everything back to the starting state.

## Architecture

- **Backend:** Python 3.12, Flask REST API (`/api/v1`), SQLite (WAL), cookie sessions, werkzeug password hashing
- **Frontend:** a dependency-free single-page app (vanilla JS and CSS) with a minimalist corporate style, the coat of arms and the Lesotho tricolour accent
- **Runtime:** gunicorn (3 workers, `--preload`) on 127.0.0.1:8000, behind nginx on port 80, managed by systemd
- **Controls:** role-based access, data scoped to each ministry, separation of duties (approvers cannot prepare a submission), CSRF header on every write, upload type and size limits (10 MB), a full audit trail, and security headers

```
app/
  stages.py   process model: roles, 10 stages, gates, chains, RA-001/RA-003 scoring
  api.py      REST endpoints and workflow rules
  seed.py     synthetic ministries, users and progress
  static/     index.html, css/app.css, js/app.js, img/coat-of-arms.svg
deploy/       systemd unit and nginx site
tests/        end-to-end workflow tests (unittest)
```

## Operations

```bash
# install
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
sudo cp deploy/xroad-portal.service /etc/systemd/system/
sudo cp deploy/nginx-xroad-portal.conf /etc/nginx/sites-available/xroad-portal
sudo ln -sf /etc/nginx/sites-available/xroad-portal /etc/nginx/sites-enabled/
sudo systemctl daemon-reload && sudo systemctl enable --now xroad-portal && sudo systemctl reload nginx

# test
.venv/bin/python -m unittest discover -s tests -v

# logs / restart / reset data
journalctl -u xroad-portal -f
sudo systemctl restart xroad-portal
rm -rf instance && sudo systemctl restart xroad-portal   # reseeds on start
```

## Before any production use

This build is for demonstration only. Before production it needs: HTTPS, SSO or government identity and MFA, per-user
credentials (no shared demo password, and the demo-account endpoint removed), PostgreSQL, malware scanning of uploads,
backups, alignment with CF-001 controls, and a DPIA.

*Emblem: the coat of arms of Lesotho (public domain SVG, Wikimedia Commons). Replace it with MICSTI's official logo
file if one is supplied.*
