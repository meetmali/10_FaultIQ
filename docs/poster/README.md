# FaultIQ poster (22 × 36 in, portrait)

Everything on the poster is vector or a real screenshot of the app: the architecture diagram (from
`docs/architecture.svg`), the charts (drawn from the numbers `manage.py evaluate` prints), the rooftop-unit
drawing (the app's own template tag) and the QR codes. No AI-generated images.

Build it:

```bash
POSTER_EMAIL=you@illinois.edu python3 docs/poster/build.py
```

```bash
cd frontend && node ../docs/poster/render.mjs
```

This writes `docs/poster/out/FaultIQ_poster.pdf` (22 × 36 in, one page) and `preview.png`. The `out/` folder is
git-ignored because it holds your contact details. `render.mjs` uses the Playwright copy installed in `frontend/`.
