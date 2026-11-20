# FaultIQ AI documentation

FaultIQ uses two AI components inside the Django app. Both are open source and run on the app's own server.
No hosted AI API and no API key are needed.

| Component | Model | Library | Code |
|---|---|---|---|
| Fault detection | Isolation Forest (unsupervised anomaly detection) + physics rules | scikit-learn | `web/diagnostics/ai/detection.py` |
| Diagnostic assistant | `BAAI/bge-small-en-v1.5` sentence embeddings (33M parameters, open weights) blended with TF-IDF | sentence-transformers, scikit-learn | `web/diagnostics/ai/assistant.py` |

Glue to the database: `web/diagnostics/services.py`.

## Why these models

- **Isolation Forest:** trend data has no labels at upload time, so detection must be unsupervised. It is fast
  (about 150 ms for 3 weeks of data on a laptop CPU) and needs no GPU. It is fitted per upload, so it adapts
  to each unit's normal behaviour.
- **Physics rules** (mixed air outside the outdoor/return range, cooling at 100% but supply air warm, damper
  closed when free cooling is available, damper open in hot weather, cooling without a command) give each
  anomaly a name and make the result explainable. An anomaly score alone does not tell a technician what to fix.
- **bge-small-en-v1.5:** one of the strongest small retrieval embedding models; 130 MB, CPU inference about 60 ms
  per query when warm. Running locally keeps building data private and costs nothing per query.
- **TF-IDF blend:** in evaluation, embeddings alone scored 8/10 top-1 and TF-IDF 9/10. The equal blend scored
  9/10 and fixed the embedding model's keyword miss ("belt squeals"), while keeping semantic matching for
  wording that does not share keywords with the library. TF-IDF is also the fallback when the model cannot load
  and the mode used on the 512 MB free hosting tier.

## Workflow

**Detection:** CSV upload → `UploadForm` (extension, 5 MB limit, binary sniff) → `services.run_analysis` →
`detection.read_trends` (required columns, numeric coercion, drop unusable rows, 100,000-row cap, hourly
resample, at least 24 hours) → keep fan-on hours → features (supply minus setpoint, outdoor-air fraction,
damper, cooling, outdoor minus return) → standardise → Isolation Forest scores + rules per hour → merge
consecutive flagged hours into events (minimum 2 h; at least 4 h when no rule explains them) → name =
most frequent rule, confidence = 0.5 + 0.5 × share of hours the rule fired (0.3 if unexplained) →
`Analysis` + `FaultEvent` rows in one transaction → analysis page with chart and events.

**Assistant:** symptom text (form, event page or JSON API) → rate limit (30 per user per hour) → `clean_query`
(10 to 1,000 characters, must contain words) → if launched from an event, the detector's finding is appended
as context → documents = fault library entries + the user's confirmed events with technician notes (from the
database) → embedding cosine and TF-IDF similarity, min-max normalised and averaged → top 3 faults with their
checks, plus similar confirmed cases → confidence gate: if the top embedding cosine is below 0.55 the page says
there is no confident match → saved as `AssistantQuery` (text, results, backend, latency) → shown to the user.

## Output handling and validation

- Every detection event comes from code paths covered by tests; unexpected exceptions are logged and the
  analysis is stored as failed with a safe message.
- Assistant results are always shown with scores and a note that they support, not replace, a technician's
  judgement. Low-similarity queries are flagged instead of presented as answers.
- Model load or inference failure falls back to TF-IDF automatically, so the assistant keeps working.
- The technician review (confirm or reject with notes) is the human check on every AI output; confirmed notes
  become retrieval data for future queries.

## Known limitations

- Rule thresholds assume °C and a typical RTU; they are not tuned per site.
- Evaluation uses synthetic data with injected faults; real BAS exports are noisier.
- Isolation Forest fitted on the same upload can miss a fault that lasts most of the file.
- Cold start: the first assistant query after a restart takes about 10 s while the model loads
  (`AI_WARMUP=1` loads it in the background at startup).
- The labelled assistant set is small (10 descriptions).

## Safety and privacy

Data never leaves the server (no external AI calls). Uploads are validated and stored in the media folder under Django's sanitised file names, never served publicly.
Every query and API is scoped to the signed-in user. The assistant is rate limited. No secrets are in the
repository; settings come from environment variables.
