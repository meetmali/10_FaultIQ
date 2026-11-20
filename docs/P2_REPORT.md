# FaultIQ: INFO 490 Project 2 report (first draft)

Individual project. Responsible member for every task: Meet Kailash Mali.
Repository: https://github.com/meetmali/10_FaultIQ. App code: `web/`. AI details: [README_AI.md](../README_AI.md).

## Part 1: Product scope and user experience

### 1.1 Final product scope (First-Draft Requirement 1)

- **Startup name:** FaultIQ.
- **Problem:** rooftop HVAC units serve most small and mid-size commercial buildings. Faults like a stuck
  economizer damper, low refrigerant or a biased sensor run unnoticed for weeks, wasting energy and causing
  comfort complaints. The data to catch them already exists in building automation system (BAS) trend logs,
  but small facility teams have no time to read them and enterprise fault-detection platforms are costly
  and need integration projects.
- **Target users:** facility managers of small and mid-size commercial buildings, HVAC service contractors and
  their field technicians.
- **Value proposition:** upload a trend export you already have and get named, ranked faults with what to check,
  plus an assistant that turns a technician's description into likely causes, in minutes and without integration.
- **Primary features:** (1) trend upload with ML fault detection, (2) AI diagnostic assistant, (3) review
  workflow with dashboard, export and API. Supporting: sites and units management, searchable fault library.
- **Changes from P2-A2:** the startup concept is unchanged. The significant change is architectural: the
  product's web layer is now a Django application (models, ORM, auth, forms, templates, JSON API), which
  hosts the AI directly. The existing FaultIQ research pipeline and .NET/React prototype remain in the
  repository as background work; the Django app is self-contained and uses synthetic sample data, so it can be
  run and deployed without licensed datasets.

### 1.2 Core features (implemented)

| Feature | How it solves the problem |
|---|---|
| Upload and detect | Turns a raw trend CSV into fault events with a name, duration, confidence and a chart. |
| AI diagnostic assistant | Ranks likely faults and checks from free-text symptoms, using the library and the team's confirmed cases. |
| Review, dashboard, export | Technicians confirm or reject events (notes required to confirm); managers see fault hours by type; CSV export and JSON API. |

### 1.3 User experience

End-to-end workflow: sign up → a sample portfolio of 6 units is created and analysed automatically → Overview
(health ring, units needing attention, fault hours chart, fleet table) → unit page (animated rooftop unit with
the faulty part highlighted) → fault event → ask the AI assistant → confirm with notes → Overview and CSV export
update. Users can also add their own sites and units and upload their own trend export. Navigation bar on every
page (template inheritance from `base.html`), one stylesheet with the design tokens of the earlier FaultIQ React
UI, light and dark themes, success/error messages after every action, inline form errors and empty states.

### 1.4 Differentiation

Enterprise fault-detection platforms are subscription products that need BAS integration and rule
configuration. BAS vendor alarms are simple thresholds that miss slow faults. FaultIQ differs because it:
works from a CSV export of any BAS (no integration), combines unsupervised ML with explainable physics rules,
gives technicians an assistant that learns from their own confirmed cases, keeps data on the server (no
external AI calls), and is open source and cheap to host.

## Part 2: Django application (First-Draft Requirement 2)

- **Models and relationships** (`web/diagnostics/models.py`): `Site` (FK owner User) → `Unit` → `Analysis`
  → `FaultEvent` (FK `FaultType`); `AssistantQuery` (FK User, optional FK FaultEvent). Unique constraint on site
  name per owner. Migrations in `web/diagnostics/migrations/`; `0002` seeds the fault library.
- **CRUD:** create sites; create, edit and delete units; create analyses and events; update events (review).
- **Views, templates, URLs:** function-based views, `base.html` inheritance, named URLs and
  `get_absolute_url` on models.
- **Forms and validation:** `SiteForm` (duplicate names), `UnitForm` (tonnage range, own sites only),
  `UploadForm` (extension, size, binary sniff), `ReviewForm` (note required to confirm), `AssistantForm`,
  plus CSV content validation in the detector.
- **Authentication and authorization:** sign up, login, logout; `login_required` on all data views; every query
  scoped to the owner (other users get 404, tested).
- **JSON API:** `GET /api/units/<id>/events/`, `GET /api/summary/`, `POST /api/assistant/`.
- **Data features:** dashboard with aggregated statistics and a Chart.js chart, event filter by review status,
  fault library search and component filter, CSV export.
- **Database-backed workflow:** upload form → view → detection → `Analysis` and `FaultEvent` rows → analysis
  page and dashboard.

## Part 3: AI integration (First-Draft Requirement 3)

Implemented and working (prototype stage complete). Summary below; full detail in [README_AI.md](../README_AI.md).

- **Technique:** Isolation Forest + physics rules for detection; semantic retrieval (bge-small-en-v1.5
  embeddings blended with TF-IDF) for the assistant.
- **Input/output:** CSV trends → fault events; symptom text → top 3 faults with checks, similar confirmed cases,
  confidence flag.
- **Django interaction:** runs inside views via `services.py`, reads the fault library and confirmed events from
  the database, writes `Analysis`, `FaultEvent` and `AssistantQuery` rows.
- **Reliability:** input validation, graceful failure (stored failed analyses with safe messages), automatic
  TF-IDF fallback, confidence gate, rate limit, human review.

## Part 4: Evaluation, testing and improvement

### 4.1 Criteria

Detection: injected faults found and correctly named (recall), false events on a healthy file. Assistant:
top-1 and top-3 accuracy on 10 labelled technician descriptions, correct "not confident" on off-topic input.
All: latency, graceful handling of invalid input.

Procedure: `python manage.py evaluate` (fixed seeds, same samples every run), MacBook (Apple silicon) CPU,
local SQLite. Outputs below are copied from that command.

### 4.2 Tests

| Test | Input | Expected behavior | Actual output | Quality (1-10) | Latency |
|---|---|---|---|---|---|
| 1 | `rtu_faulty.csv` (21 days, 4 injected faults) | All 4 faults found and named | Economizer not economizing, Excess outdoor air, Insufficient cooling capacity, Mixed-air temperature sensor fault, plus 1 unclassified anomaly (11 events) | 9 | 162 ms |
| 2 | `rtu_healthy.csv` (no faults) | No events | 1 event: unclassified anomaly, 4 h | 8 | 137 ms |
| 3 | CSV missing columns | Clear error, no crash | Failed analysis: "Missing required columns: rat, mat, sat_sp, damper_pct, cooling_pct, fan_on." | 10 | 1 ms |
| 4 | "Supply air stays around 18 C even though the compressor is at 100 percent on a hot afternoon" | Insufficient cooling capacity first | Insufficient cooling capacity (0.755), confident | 7 (correct, but first query after start is slow) | 9,581 ms (cold model load) |
| 5 | "My laptop screen flickers when I open the browser" (off-topic) | Flag no confident match | Top Excess outdoor air (0.498), confident=False, warning shown | 8 | 63 ms |

Assistant accuracy on 10 labelled descriptions (warm model):

| Backend | Top-1 | Top-3 | Mean latency |
|---|---|---|---|
| TF-IDF | 9/10 | 10/10 | 1 ms |
| bge embeddings | 8/10 | 10/10 | 60 ms |
| Hybrid (default) | 9/10 | 10/10 | 59 ms |

Django test suite: 10 tests pass (`python manage.py test diagnostics`).

### 4.3 Failure analysis

1. **False alarms from rare normal hours.** *What:* the first version raised 16 events on the healthy file and 9
   extra events on the faulty file, almost all 2 to 3 hours at 06:00. *Why:* morning economizer start-up is
   normal but rare, and Isolation Forest flags rare as anomalous. *Impact:* technicians would learn to ignore
   alerts. *Improvement:* see 4.4; next, train the forest on several weeks of known-good data per unit.
2. **Cold-start latency.** *What:* the first assistant query after a restart took 9.6 to 10.2 s. *Why:* loading
   PyTorch and the embedding model. *Impact:* the first user waits; on a 512 MB host the model does not fit at all.
   *Improvement:* `AI_WARMUP=1` loads it in a background thread at startup (implemented); TF-IDF mode on small hosts.
3. **Assistant miss.** "Rooms get warm every afternoon, unit runs flat out and never reaches setpoint" ranks
   "Supply fan off during occupancy" first for every backend. *Why:* the library text for insufficient cooling does
   not use words like "flat out" or "setpoint", and "rooms get warm" matches the fan entry. *Improvement:* add
   technician phrasing to library entries and grow the case base from confirmed reviews.

### 4.4 Improvement

**Before:** unexplained anomaly events (no physics rule) kept at 2 hours or more.
**Modification:** unexplained events must last at least 4 hours (`min_unexplained_hours=4` in
`detection.detect`); rule-explained events still need only 2 hours.
**After** (`python manage.py evaluate`):

| Setting | File | Faults found | False events |
|---|---|---|---|
| Before (2 h) | rtu_faulty.csv | 4/4 | 9 |
| Before (2 h) | rtu_healthy.csv | 0/0 | 16 |
| After (4 h) | rtu_faulty.csv | 4/4 | 1 |
| After (4 h) | rtu_healthy.csv | 0/0 | 1 |

It worked: false events fell from 25 to 2 with no lost faults. Second improvement from testing: embeddings alone
scored 8/10 top-1; blending with TF-IDF raised it to 9/10 (table in 4.2).

## Part 5: Deployment, cost and production readiness

### 5.1 Deployment

`render.yaml` defines a Render Blueprint: a free Python web service (`web/build.sh` installs, collects static
files, migrates, optionally seeds the demo user) and a free PostgreSQL database. Gunicorn serves the app,
WhiteNoise serves static files, `DJANGO_SECRET_KEY` is generated by Render. The free plan has 512 MB RAM, so it
runs `AI_EMBEDDINGS=tfidf` (measured 206 MB); the hybrid model needs about 540 MB and runs on the 2 GB plan or
locally. Deploy: Render dashboard → New → Blueprint → select this repository → set `DEMO_PASSWORD` → Apply.

### 5.2 Infrastructure (measured on the sample workload)

| Resource | Requirement |
|---|---|
| CPU | 1 vCPU: detection about 150 ms per 3-week file; assistant 60 ms per query (hybrid) |
| GPU | Not needed |
| RAM | 206 MB peak (TF-IDF) / 538 MB peak (hybrid with PyTorch) per process |
| Storage | about 120 KB per 3-week CSV; model 130 MB; Python environment about 940 MB with PyTorch |
| Database | PostgreSQL (SQLite locally); small rows plus a JSON chart series per analysis |
| AI inference | In-process on the web server's CPU |

### 5.3 Cost comparison (approximate list prices, to be confirmed before launch)

| Factor | Self-hosted AI (bge on our server) | Hosted AI API (embeddings API, e.g. OpenAI text-embedding-3-small) |
|---|---|---|
| Hardware requirements | 2 GB RAM instance for the model | 512 MB instance is enough |
| Estimated monthly cost | about $25 (Render Standard) + about $7 database | about $7 (Starter) + about $7 database + API about $0.02 per 1M tokens (pennies at our volume) |
| Latency | about 60 ms warm, about 10 s cold start | about 100 to 300 ms network round trip per query |
| Maintenance | Model updates and memory tuning are ours | Provider maintains the model; API key management, model deprecations |
| Scalability | Add CPU instances; one core serves about 15 queries/s | Scales with the provider; rate limits apply |
| Privacy | Building data never leaves our server | Symptom text sent to a third party; needs a data agreement |

Choice: self-hosted, because the volume is low, privacy matters to building owners, and there is no per-query
cost or key to protect. TF-IDF mode is the zero-cost fallback.

### 5.4 Scalability to 10,000 daily active users

Assumptions: 20% upload one 3-week CSV per day (2,000 analyses), each user asks 3 assistant questions
(30,000 queries/day, about 0.35/s average, about 2/s at peak).

- **Infrastructure:** 2 to 3 web instances (2 GB) behind the load balancer, managed PostgreSQL with backups,
  object storage (S3) for uploads, a Redis-backed task queue (Celery or RQ) with 1 to 2 worker instances.
- **Primary bottleneck:** analysis runs inside the web request; a year-long file would block a worker for
  seconds. Second: the assistant re-embeds every library document and confirmed case on each query.
- **AI cost:** self-hosted stays flat (CPU already paid for, about 2 queries/s is far below capacity). A hosted
  embeddings API would cost cents per day at this volume; an LLM-based assistant would cost far more.
- **Performance:** cache document embeddings (store vectors in PostgreSQL with pgvector), move analysis to
  background jobs with status polling, index foreign keys and review status, cache dashboard aggregates.
- **Architecture changes:** task queue and worker, object storage, pgvector, per-tenant rate limits,
  monitoring with error tracking.

### 5.5 Security and reliability

| Measure | Status |
|---|---|
| Environment variables | Secret key, debug flag, hosts, database URL from the environment; app refuses to start in production without a secret key |
| Input validation | Form validation, CSV extension, size and binary checks, column and row limits, assistant text rules |
| Authentication and permissions | Login required; all queries scoped to the owner; tested 404 for other users |
| API key protection | No AI API keys used (local models); none in the repository; `.env` is git-ignored |
| Error handling | Detection errors stored with safe messages; unexpected errors logged; AI fallback to TF-IDF |
| Rate limiting | Assistant limited to 30 queries per user per hour (page and API, HTTP 429) |
| Logging and monitoring | Console logs for every analysis and AI fallback; host logs on Render |
| Privacy | Data stays on the server; secure cookies and HTTPS proxy settings in production |
| AI-related risks | Confidence gate, scores shown, "supports, not replaces" notice, human confirm/reject before results become training data |

## Part 6: Documentation

Root [README.md](../README.md) (install, environment, database, run, AI access), [README_AI.md](../README_AI.md),
this report, `requirements.txt` files, `.gitignore` (env files, database, uploads, model weights).

## Development progress and roadmap (First-Draft Requirement 4)

| Task | Current status | Responsible member | Expected completion |
|---|---|---|---|
| Django core features | Done for the draft: models, auth, CRUD, forms, templates, dashboard, preloaded sample portfolio | Meet Kailash Mali | Polish by Dec 1 |
| Database and APIs | Done: migrations, seeded library, 3 JSON endpoints, CSV export | Meet Kailash Mali | Nov 28 (PostgreSQL on Render) |
| AI integration | Working: detection and hybrid assistant in the app | Meet Kailash Mali | Dec 3 (cached embeddings, richer library phrasing) |
| Evaluation and testing | 5 tests, 2 labelled benchmarks, 9 unit tests, 1 improvement | Meet Kailash Mali | Dec 5 (larger labelled set, more failure cases) |
| Deployment | Render Blueprint ready; deploy in TF-IDF mode | Meet Kailash Mali | Nov 26 |
| Documentation | README, README_AI and this report drafted | Meet Kailash Mali | Dec 7 |
