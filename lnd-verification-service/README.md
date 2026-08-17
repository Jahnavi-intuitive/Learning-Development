# L&D Agent — Certificate Verification Service

This is Phase 3 from the build plan: **Certificate Upload & Automated
Verification** (BRD FR-3.1–FR-3.4). It's a standalone FastAPI service that
does the deterministic, no-LLM verification path — cross-checking a
submitted credential (starting with a public link, e.g. Credly) against the
employee who submitted it, and routing anything it can't confirm to an
exception queue instead of auto-rejecting it.

It runs completely on its own — no Teams, no bot framework, no Gemini API —
so you can build and test the highest-risk piece of the whole agent in
isolation before wiring it into anything else. That wiring happens later,
once Phase 0 (Teams bot shell + SSO) exists.

## What's already working

Tested end to end before this was handed to you:
- `POST /employees` — create a test employee (stand-in for the real HRIS integration, which comes later)
- `POST /verify` — submit a certification name + public proof link; runs the full pipeline
- `GET /exceptions` — the L&D admin exception queue (everything auto-verification couldn't confirm)
- A small local web UI at **`/ui/`** (see Section 3a below) so you can drive all of this by
  clicking instead of curl — including clicking "Approve" on an exception and watching
  the queue clear live.
- `POST /exceptions/{id}/resolve` — an admin manually approves/rejects a queued item
- 6 passing unit tests covering the match / mismatch / unreachable-link cases, with no real network calls

## 1. One-time machine setup

You said you're starting from nothing but VS Code, so:

1. **Install Python 3.11+** if you don't have it: https://www.python.org/downloads/
   Confirm it worked: `python3 --version`
2. **Install these VS Code extensions** (Extensions panel, `Ctrl+Shift+X` / `Cmd+Shift+X`):
   - *Python* (Microsoft) — gives you the interpreter picker, debugging, linting
   - *Pylance* (usually installs alongside Python)
   - *Thunder Client* or *REST Client* (optional, but nicer than raw `curl` for hitting the API from inside VS Code)
3. **Install Git** if you don't have it, and set your name/email (`git config --global user.name "..."` / `user.email`).

## 2. Get this project open and running

```bash
# unzip wherever you keep projects, then:
cd lnd-verification-service

# create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# install dependencies
pip install -r requirements.txt

# copy the example env file (defaults are fine to start — SQLite, zero setup)
cp .env.example .env
```

In VS Code: `Ctrl+Shift+P` → "Python: Select Interpreter" → pick the one at
`.venv/bin/python`. That's what makes Pylance/debugging use the right
packages.

## 3. Run it

```bash
uvicorn app.main:app --reload
```

Or press `F5` in VS Code and pick **"FastAPI: uvicorn (debug)"** (already
configured in `.vscode/launch.json`) — that gives you breakpoints.

Open **http://127.0.0.1:8000/docs** — that's FastAPI's auto-generated
Swagger UI. You can call every endpoint from there without writing a single
HTTP request by hand. Also try **http://127.0.0.1:8000/health**.

## 3a. The local admin/test UI

Open **http://127.0.0.1:8000/ui/** — a small single-page console (plain
HTML/CSS/JS, no build step, served by this same FastAPI app via
`StaticFiles`) that gives you:

- Live stat tiles (employees, verified, needs-review, pending)
- A form to quick-create a test employee
- A form to submit a certificate for verification (calls the real `/verify`
  pipeline — public-link fetch, name-match guardrail, everything)
- The exception queue, with an **Approve** button per row that calls
  `/exceptions/{id}/resolve` and refreshes the table live

**This is scaffolding, not the production UI.** It exists so you have
something to click through while building the backend, instead of curl or
Swagger. Once Phase 0 (Teams bot shell) exists, the real interaction moves
into Teams — a conversational flow for employees submitting proof, and
either a Teams tab or another conversational flow for L&D admins working
the exception queue. See Section 9 for how that maps out. Nothing about
this page needs to survive into that version; feel free to modify or throw
it away once the real Teams flow exists.

## 4. Try the full flow

```bash
# create yourself as a test employee
curl -X POST http://127.0.0.1:8000/employees \
  -H "Content-Type: application/json" \
  -d '{"name":"Your Name","email":"you@intuitive.ai"}'

# submit a certificate for verification (use a real Credly public badge URL
# once you have one; see the note below on what to expect)
curl -X POST http://127.0.0.1:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"employee_id":1,"certification_name":"AWS Certified Cloud Practitioner","proof_url":"https://www.credly.com/badges/<some-uuid>/public_url"}'

# see anything that landed in the exception queue
curl http://127.0.0.1:8000/exceptions
```

Or run the seed script for a demo employee instead of POSTing by hand:
`python -m scripts.seed_demo_data`

## 5. Run the tests

```bash
python -m pytest app/tests -v
```

All 6 pass out of the box. They mock the Credly fetch, so they run offline
and won't break if Credly changes their page layout — that's exactly the
part you'll want to re-test manually against a real badge URL.

## 6. The one thing that will need real-world tuning

`app/services/credly.py` parses a Credly badge public page for the
recipient's name and badge name. Credly doesn't publish this as a stable
API, so the parser tries a couple of known locations (structured JSON-LD
data, then the `og:title` meta tag) and raises a clear error — which gets
routed to the exception queue, never silently ignored — if neither is
found.

**Before you trust this against real certificates:** get a real Credly
badge public URL (ask a colleague who has one, or issue yourself a free
badge on Credly to test with), open it in a browser, "View Page Source",
and confirm the parser actually finds the name/badge fields. If Credly's
markup differs from what's coded here, this is the file to adjust — it's
isolated on purpose so a markup change doesn't touch anything else.

Also tune `NAME_MATCH_THRESHOLD` in `.env` once you see real match scores —
0.82 is a reasonable starting guess, not a validated number.

## 7. What's deliberately stubbed / not built yet

- **Document-scan verification** (the other half of FR-3.2, for uploaded
  PDFs/images rather than public links) isn't implemented yet. Anything
  submitted as a document today should be added as its own service module
  (`app/services/document_scan.py`) following the same pattern as
  `credly.py` — fetch/parse, then hand the result to the same
  verify-or-exception-queue decision in `verifier.py`. OCR is the natural
  next dependency to bring in there.
- **Employees come from a POST endpoint here**, purely for local testing.
  In the real system they come from HRIS/the corporate directory (BRD
  Section 11) — swap `create_employee` for a directory sync once that
  integration exists.
- **SQLite is the default DB.** It's genuinely fine for solo development.
  Move to Postgres (the BRD's system of record — Section 11) before this
  goes anywhere near real employee data: change `DATABASE_URL` in `.env`,
  and once the schema is stable, add Alembic for migrations instead of
  relying on `create_all` at startup.
- **No Teams/bot integration.** That's Phase 0 + the bot framework layer —
  this service is designed to be called *by* that bot backend later
  (a plain HTTP call to `/verify`), not to talk to Teams directly.

## 8. Project layout

```
app/
  main.py                 - FastAPI app entrypoint
  config.py                - settings (.env-driven)
  database.py               - SQLAlchemy engine/session
  models.py                  - Employee, CertificateRecord, Verification, AuditLog
  schemas.py                  - request/response shapes
  routers/verification.py      - all the HTTP endpoints
  services/
    credly.py                   - public-link cross-check (FR-3.2)
    name_match.py                 - the name-match guardrail (FR-3.2)
    verifier.py                    - orchestration + audit logging (FR-3.1-3.4)
  tests/                            - offline, mocked tests
static/index.html                       - the local admin/test UI (Section 3a) -- dev-only
scripts/seed_demo_data.py              - quick local test data
```

## 9. What the *production* UI looks like (for later, not now)

Per the BRD (Section 5) and the tech stack doc, this agent doesn't get a
standalone website. **Microsoft Teams is the UI.** There are two different
production surfaces this verification workflow eventually needs, and
neither exists yet — both depend on Phase 0 (Teams bot shell + Bot Service +
SSO) being in place first:

- **Employee submission flow** — a conversational flow inside the Teams
  bot: the employee tells the bot which certification they completed and
  either pastes a public link or uploads a file; the bot backend calls this
  service's `/verify` endpoint and renders the result back as an **Adaptive
  Card** (a status chip, basically, but Teams-native) rather than a web
  page. This is built as part of Phase 5 (Exam-Prep Q&A) territory, since
  it shares the same bot conversation layer.
- **L&D admin exception-queue review** — two viable shapes, worth deciding
  between rather than defaulting: (a) a **conversational flow** — an admin
  messages the bot "show my exception queue" and gets Adaptive Cards with
  Approve/Send-back buttons, which stays fully inside Teams with no extra
  hosting; or (b) a **Teams tab** — a small web app embedded in a Teams tab
  (similar to how the tech stack doc describes the leadership dashboard),
  which gives admins a better bulk-review table experience at the cost of
  building and hosting a second small web app. For a queue that's mostly a
  handful of items a day, (a) is the lower-effort starting point; revisit
  (b) if exception volume grows enough that a table view earns its keep.

The local `/ui/` console in Section 3a is not a rough draft of either of
these — it's disposable dev tooling. Don't try to evolve it into the Teams
tab; build that separately against the Teams Toolkit/Microsoft 365 Agents
SDK when Phase 0 exists, reusing this service's existing `/verify` and
`/exceptions` endpoints as-is.

## 10. Suggested next steps, in order

1. Get a real Credly badge URL and confirm/adjust the parser (Section 6 above).
2. Resolve **Open Question #1** from the BRD with your stakeholders — should
   admin review be an exception path (what's built here) or a default gate
   for every certificate? That decision may change this design.
3. Add the document-scan path (Section 7 above) once the public-link path
   is proven out.
4. Containerize it (`Dockerfile` + `uvicorn` as the entrypoint) so it can
   run on Azure App Service/Functions per the tech stack doc.
5. Move to Postgres and add Alembic migrations.
6. Once Phase 0 (Teams bot shell) exists, decide the shape of the admin
   exception-queue surface (Section 9) and build the employee submission
   flow as Adaptive Cards — have the bot backend call this service's
   `/verify` endpoint rather than building verification logic into the bot
   itself, keeping them as two services exactly as the tech stack doc
   recommends (no LLM in this path, ever).
