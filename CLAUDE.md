# CLAUDE.md — Community Scam Map (Mitigata CyberForge hackathon)

Read this file first, every session. It tells you what we are building, the rules you must
never break, and how to work. Topic details live in `docs/` — open only the one you need.

## What we are building (one paragraph)
A server + mobile website where people report scam phone numbers, UPI IDs, links and SMS
senders, and look one up before trusting it. A judges' test tool hits our 7 API endpoints
with secret data full of fake reports. We win on: (1) trust rules that stop fakes without
missing real scams, (2) a live licence demo that locks/unlocks the server without restart,
(3) privacy that never slips (any slip = disqualification).

## Stack (decided — don't change without asking)
- Server: Python 3.11+, FastAPI, SQLAlchemy 2.0 (Core or ORM), Pydantic v2
- DB: SQLite locally (`DATABASE_URL=sqlite:///./dev.db`), Postgres in production (same code)
- Licence: PyNaCl (Ed25519)
- Tests: pytest + FastAPI TestClient; scenario scripts in `tools/`
- Frontend: plain mobile website (Vite + React or vanilla JS), Leaflet + OpenStreetMap, i18n EN/HI
- Deploy: Render/Railway/Fly with managed Postgres, HTTPS, always-on (no cold starts)

## Doc index — open the one you need
| Doc | Open it when you are… |
|---|---|
| `docs/00-prd.md` | **the organisers' brief: it outranks every other doc.** Check it whenever a doc seems unclear, and above all for how the judges test |
| `docs/01-api-contract.md` | writing or changing any endpoint (exact request/response shapes) |
| `docs/02-normalization.md` | parsing phone / UPI / URL / sender values, validation, 400 rules |
| `docs/03-trust-rules.md` | working on report weighting, verdicts, distinct_reporters |
| `docs/04-privacy.md` | storing, logging, displaying anything (masking, wording, hashing) |
| `docs/05-license.md` | licence signing, middleware, /license, clock rollback |
| `docs/06-map-alerts.md` | /map, /alerts, time windows, severity |
| `docs/07-frontend.md` | any app screen |
| `docs/08-implementation-plan.md` | deciding what to do next; each step's "done when" + tests |
| `docs/09-demo-script.md` | rehearsing / preparing judging day |
| `docs/10-working-agreement.md` | **every session**: how to report to the user after each feature or bug fix |
| `server/app/data/*.json` | areas (25 pincodes + lat/lng), verified identifiers, scam types, channels |
| `PROGRESS.md` | what is already built and how to test it (update it — see below) |

## Hard rules (never break)
1. **Privacy** (see docs/04): never store/show/log reporter name, phone, exact location. Area only.
   Mask identifiers until ≥3 distinct reporters (after trust rules). Say "reported", never "scammer/fraud".
   No request bodies, identifiers, IPs or notes in logs.
2. **No hardcoded test values.** Never write logic like `if number == "+9198..."`. Judges check.
   The verified list in `data/verified.json` is the only allowed identifier list.
3. **API contract is law.** Paths, field names, status codes and verdict strings exactly as in docs/01.
   No auth on the 7 test endpoints.
4. **Licence check runs on every request** (except `/health`, `/license`). Expiry locks, never deletes.
5. **Private key never in the repo.** `private.key`, `*.pem`, `licenses/*.json` are in `.gitignore`.
6. **Time:** all windows use each report's `occurred_at` compared with the server clock (UTC internally,
   IST `+05:30` in output).

## How to work (every step)
1. Look at `docs/08-implementation-plan.md`, pick the next step, read only the docs it lists.
2. Write code with **plain-English comments** (the team is learning from it):
   - Every file starts with a docstring: what this file is for, in 2–4 simple sentences.
   - Every function has a docstring: what goes in, what comes out, why it exists.
   - Inside functions, a short comment above each logical block (`# 1) Strip spaces and dashes`).
   - Explain *why* for any non-obvious rule (e.g. why same-ip reports merge).
3. Write tests for the step (pytest) and run them. All tests must pass before you say "done".
4. **Update `PROGRESS.md`** using its template: what was built (simple words), files touched,
   exactly how to test it (copy-paste commands + expected output), known gaps.
5. Report to the user after **each feature** (short, simple words, in this order):
   1. **What I built**: 2–4 plain bullets.
   2. **Run it yourself**: copy-paste commands to start the server and try the feature, with expected output.
   3. **Code walkthrough**: very brief. Name each file/function and say in one line how it works. Not line by line.
   4. **How the judges will test it**: what the test tool or judge sends, and what must come back (cite [PRD §…]).
   5. **Where we are**: the step from docs/08, done / in progress, and what's next.
   For **bug fixes only**: skip all that. Say what was wrong, what changed, and give a one-line code overview.

## Commands
```bash
cd server && pip install -r requirements.txt
uvicorn app.main:app --reload          # run locally on :8000
pytest -q                               # all tests
python ../tools/scenarios.py --base http://localhost:8000   # attack + real-scam scenarios
```

## Layout (target)
```
server/app/main.py          FastAPI app, routes wired here
server/app/normalize.py     identifier parsing + validation (pure functions)
server/app/db.py            tables + session
server/app/trust.py         report weighting + verdict
server/app/privacy.py       masking, hashing, safe logging
server/app/license.py       verify, middleware, clock guard
server/app/geo.py           areas, haversine, map clusters
server/app/alerts.py        SPIKE / NEW_TYPE
server/app/data/*.json      reference data from the brief's appendix
server/tests/               pytest per module
tools/                      make_license.py, keygen.py, scenarios.py, replay_logs.py
web/                        mobile website
