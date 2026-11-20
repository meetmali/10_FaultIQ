"""Build the 22 x 36 in FaultIQ poster as one HTML page (vector diagrams, charts and QR codes).

    python docs/poster/build.py            # writes docs/poster/out/poster.html
    POSTER_EMAIL=you@illinois.edu python docs/poster/build.py

Then print it to PDF at 22 x 36 in (see docs/poster/README.md). Numbers come from `manage.py evaluate`.
"""

import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE / "out"
NAME = "Meet Kailash Mali"
EMAIL = os.environ.get("POSTER_EMAIL", "[your email]")


def svg_file(path: Path) -> str:
    s = path.read_text(encoding="utf-8")
    return s[s.index("<svg"):]


def architecture_light() -> str:
    """The README diagram, recoloured for print on a light poster and with namespaced classes."""
    s = svg_file(ROOT / "docs" / "architecture.svg")
    for dark, light in {
        "#121818": "#F3F5F9", "#1b2323": "#FCFDFE", "#9aa5a5": "#64748B", "#f2f5f5": "#14213D",
        "#aeb9b9": "#475569", "#8fa0a0": "#64748B", "#e8eeee": "#14213D", "#17302b": "#E6F6F1",
        "#5fd4b8": "#0F8F74",
    }.items():
        s = s.replace(dark, light)
    names = ["bg", "box", "h", "s", "lane", "lh", "ls", "step", "st", "ln", "teal"]
    s = re.sub(r"\.(" + "|".join(names) + r")\{", lambda m: ".a-" + m.group(1) + "{", s)
    s = re.sub(r'class="([^"]+)"', lambda m: 'class="' + " ".join("a-" + c if c in names else c for c in m.group(1).split()) + '"', s)
    s = s.replace('id="a"', 'id="a-arrow"').replace("url(#a)", "url(#a-arrow)")
    s = s.replace('id="t"', 'id="a-t"').replace('id="d"', 'id="a-d"').replace('aria-labelledby="t d"', 'aria-labelledby="a-t a-d"')
    # Larger labels so the diagram reads from about 3 feet once printed.
    for small, large in {"700 17px": "700 20px", "400 14px": "400 16px", "400 13px": "400 15px",
                         "700 19px": "700 22px", "600 13.5px": "600 14px"}.items():
        s = s.replace(small, large)
    # Centre the data-layer label so the larger text clears the upload arrow.
    s = s.replace('x="962" y="458" text-anchor="end"', 'x="590" y="458" text-anchor="middle"')
    return s.replace('width="1040" height="830"', 'class="arch"')


def vbars(title, groups, series, max_value, note="", width=560, height=430):
    """Vertical bar chart. groups: [(label, [values per series])]; series: [(name, colour)]."""
    left, top, bottom = 20, 130 if len(series) > 1 else 96, 70
    plot_h = height - top - bottom
    gw = (width - left) / len(groups)
    bw = min(78, (gw - 40) / len(series))
    out = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="{title}">',
           f'<text x="0" y="34" class="ct">{title}</text>']
    if len(series) > 1:
        x = 0
        for name, colour in series:
            out.append(f'<rect x="{x}" y="52" width="22" height="22" rx="4" fill="{colour}"/><text x="{x + 30}" y="71" class="cn">{name}</text>')
            x += 30 + len(name) * 14 + 30
    base = top + plot_h
    out.append(f'<line x1="{left}" y1="{base}" x2="{width}" y2="{base}" stroke="#94A3B8" stroke-width="2"/>')
    for gi, (label, values) in enumerate(groups):
        gx = left + gi * gw + (gw - bw * len(series) - 8 * (len(series) - 1)) / 2
        for si, v in enumerate(values):
            h = max(4, plot_h * v / max_value)
            x = gx + si * (bw + 8)
            out.append(f'<rect x="{x:.0f}" y="{base - h:.0f}" width="{bw:.0f}" height="{h:.0f}" rx="5" fill="{series[si][1] if len(series) > 1 else values_colour(label)}"/>')
            out.append(f'<text x="{x + bw / 2:.0f}" y="{base - h - 10:.0f}" text-anchor="middle" class="cv">{v}</text>')
        out.append(f'<text x="{left + gi * gw + gw / 2:.0f}" y="{base + 36}" text-anchor="middle" class="cl">{label}</text>')
    if note:
        out.append(f'<text x="0" y="{height - 4}" class="cn">{note}</text>')
    out.append("</svg>")
    return "".join(out)


def values_colour(label):
    return "#6D28D9" if label.startswith("Hybrid") else "#A3AEC2"


def build() -> str:
    img = HERE / "img"
    false_events = vbars(
        "False fault events",
        [("Healthy file", [16, 1]), ("Faulty file", [9, 1])],
        [("Before", "#A3AEC2"), ("After 4 h rule", "#6D28D9")], 16,
        note="Injected faults found: 4 / 4 before and after.",
    )
    assistant = vbars(
        "Assistant: right top match / 10",
        [("TF-IDF", [9]), ("Embeddings", [8]), ("Hybrid", [9])],
        [("Top-1", "#6D28D9")], 10,
        note="Warm latency: 1 ms · 60 ms · 60 ms",
    )
    return TEMPLATE.format(
        name=NAME, email=EMAIL, rtu=svg_file(img / "rtu.svg"), arch=architecture_light(),
        chart1=false_events, chart2=assistant,
        qr_github=svg_file(img / "qr-github.svg"), qr_app=svg_file(img / "qr-app.svg"),
    )


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>FaultIQ poster</title>
<style>
@page {{ size: 22in 36in; margin: 0; }}
:root {{ --surface:#FCFDFE; --raised:#EEF2F7; --ink:#14213D; --metal-1:#E7ECF2; --metal-2:#CFD8E3; --metal-3:#AAB7C7;
  --metal-edge:#7B8AA0; --roof:#D9DEE6; --air-cool:#38BDF8; --air-warm:#FB923C; --refrigerant:#A78BFA;
  --fault-glow:#EF4444; --warn-glow:#F59E0B; --ok:#047857; --idle:#475569; }}
* {{ box-sizing: border-box; }}
html, body {{ margin:0; width:2112px; height:3456px; }}
body {{ background:#F3F5F9; color:#14213D; font-family:"Helvetica Neue", Helvetica, Arial, sans-serif; font-size:29px; line-height:1.36;
  -webkit-print-color-adjust:exact; print-color-adjust:exact; display:flex; flex-direction:column; }}
header {{ background:#14213D; color:#F3F5F9; height:340px; padding:40px 90px; display:flex; align-items:center; gap:56px; flex:0 0 340px; }}
header .t {{ flex:1; }}
h1 {{ font-size:150px; line-height:1; margin:0; letter-spacing:-2px; }}
.tag {{ font-size:48px; color:#C4B5FD; margin:16px 0 0; font-weight:600; }}
.who {{ font-size:30px; color:#CBD5E1; margin:18px 0 0; }}
header svg {{ width:440px; height:auto; background:#E9EEF5; border-radius:26px; flex:0 0 440px; }}
main {{ flex:1; padding:30px 90px 0; display:flex; flex-direction:column; gap:28px; }}
.card {{ background:#FCFDFE; border:3px solid #DDE3EC; border-radius:26px; padding:30px 42px; }}
h2 {{ font-size:52px; margin:0 0 20px; display:flex; align-items:center; gap:20px; line-height:1.1; }}
h2 .n {{ width:68px; height:68px; border-radius:50%; background:#6D28D9; color:#FCFDFE; font-size:40px; display:inline-flex; align-items:center; justify-content:center; flex:0 0 68px; }}
h3 {{ font-size:34px; margin:0 0 10px; color:#4C1D95; }}
ul, ol {{ margin:0; padding-left:38px; }} li {{ margin:0 0 10px; }}
.row {{ display:grid; grid-template-columns: 1fr 1fr; gap:28px; }}
.rowC {{ display:grid; grid-template-columns: 1.4fr 1fr; gap:28px; flex:1; }}
.flow {{ display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin:6px 0 0; }}
.flow span {{ background:#EDE9FE; color:#3B0764; font-weight:700; border-radius:12px; padding:10px 18px; font-size:27px; }}
.flow i {{ font-style:normal; color:#6D28D9; font-weight:700; font-size:32px; }}
.note {{ font-size:26px; color:#475569; margin:14px 0 0; }}
.big {{ display:flex; gap:24px; align-items:center; margin:0 0 18px; }}
.big b {{ font-size:60px; color:#6D28D9; line-height:1; flex:0 0 250px; white-space:nowrap; }}
.big span {{ font-size:28px; }}
.ready {{ background:#FEF3C7; border:3px solid #FCD34D; border-radius:18px; padding:16px 24px; font-size:27px; }}
.archrow {{ display:flex; gap:40px; align-items:flex-start; }}
.arch {{ width:1060px; height:auto; display:block; flex:0 0 1060px; border-radius:18px; }}
.side {{ font-size:27px; }}
.side ol, .side ul {{ margin-bottom:18px; }} .side li {{ margin:0 0 8px; }}
.charts {{ display:grid; grid-template-columns:1fr 1fr; gap:28px; margin:8px 0 18px; }}
.chart {{ width:100%; height:auto; display:block; }}
.ct {{ font:700 32px "Helvetica Neue", Arial, sans-serif; fill:#14213D; }}
.cl {{ font:400 28px "Helvetica Neue", Arial, sans-serif; fill:#334155; }}
.cv {{ font:700 30px "Helvetica Neue", Arial, sans-serif; fill:#14213D; }}
.cn {{ font:400 25px "Helvetica Neue", Arial, sans-serif; fill:#475569; }}
.evalbottom {{ display:grid; grid-template-columns: 1.35fr 1fr; gap:28px; align-items:start; }}
table {{ width:100%; border-collapse:collapse; font-size:24px; }} td:last-child, th:last-child {{ white-space:nowrap; }}
th {{ text-align:left; color:#475569; font-weight:700; border-bottom:3px solid #CBD5E1; padding:6px 8px; }}
td {{ border-bottom:2px solid #E2E8F0; padding:7px 8px; vertical-align:top; }}
.shot {{ width:100%; border-radius:14px; border:3px solid #DDE3EC; display:block; }}
.cap {{ font-size:24px; color:#475569; margin:8px 0 0; }}
footer {{ flex:0 0 210px; background:#14213D; color:#E2E8F0; display:flex; align-items:center; gap:46px; padding:0 90px; margin-top:28px; }}
footer .qr {{ display:flex; align-items:center; gap:22px; }}
footer svg {{ width:160px; height:160px; background:#FCFDFE; border-radius:14px; padding:8px; }}
footer .lbl {{ font-size:29px; }} footer .lbl b {{ color:#C4B5FD; display:block; font-size:31px; }}
footer .credit {{ margin-left:auto; text-align:right; font-size:24px; color:#CBD5E1; max-width:640px; }}
</style></head>
<body>
<header>
  <div class="t">
    <h1>FaultIQ</h1>
    <p class="tag">AI fault detection and diagnostics for rooftop HVAC units</p>
    <p class="who">{name} · {email} · INFO 490 · University of Illinois Urbana-Champaign</p>
  </div>
  {rtu}
</header>
<main>
  <div class="row">
    <section class="card">
      <h2><span class="n">1</span>Problem &amp; Motivation</h2>
      <ul>
        <li>Rooftop units cool most <b>small and mid-size commercial buildings</b>.</li>
        <li>A stuck damper, refrigerant leak or drifting sensor <b>runs unnoticed for weeks</b>, wasting energy.</li>
        <li>The evidence sits in <b>building automation trend logs</b>; small teams lack time to read them, and enterprise tools are costly.</li>
      </ul>
      <h3 style="margin-top:18px">Our solution</h3>
      <div class="flow"><span>Upload CSV</span><i>→</i><span>ML flags hours</span><i>→</i><span>Rules name fault</span><i>→</i><span>AI ranks causes</span><i>→</i><span>Review</span></div>
      <p class="note">For facility managers and HVAC technicians · free, open source, no AI API key.</p>
    </section>
    <section class="card">
      <h2><span class="n">4</span>Key Results</h2>
      <div class="big"><b>25 → 2</b><span>false events with a 4-hour rule for unexplained alerts; no fault missed.</span></div>
      <div class="big"><b>9 / 10</b><span>right top match from the hybrid assistant (embeddings alone: 8 / 10).</span></div>
      <div class="big"><b>150 ms</b><span>to analyse 3 weeks of data on one CPU: no GPU, no API cost.</span></div>
      <div class="big"><b>206 MB</b><span>keyword mode fits a free host; embeddings need 540 MB. Quality vs cost.</span></div>
      <div class="ready"><b>Market ready?</b> Pilot-ready, not production-ready: deployed and working end to end, but not yet validated on real buildings.</div>
    </section>
  </div>

  <section class="card">
    <h2><span class="n">2</span>System Architecture</h2>
    <div class="archrow">
      {arch}
      <div class="side">
        <h3>Data flow: input → backend → AI → output</h3>
        <ol>
          <li><b>Input:</b> a trend CSV, or the preloaded sample units.</li>
          <li><b>Django view + form:</b> type, size and binary checks.</li>
          <li><b>Preprocess:</b> required columns, numbers, hourly resample.</li>
          <li><b>AI:</b> Isolation Forest scores each running hour; 5 physics rules name the fault.</li>
          <li><b>Store:</b> analysis + fault events in PostgreSQL, one transaction.</li>
          <li><b>Output:</b> chart, named events, review, JSON API, CSV export.</li>
        </ol>
        <h3>AI integration</h3>
        <ul>
          <li><b>Detection:</b> scikit-learn Isolation Forest, unsupervised, fitted per upload.</li>
          <li><b>Assistant:</b> retrieval over the fault library and confirmed cases: BAAI/bge-small-en-v1.5 embeddings blended with TF-IDF.</li>
          <li><b>Safeguards:</b> confidence gate, TF-IDF fallback, rate limit, human review.</li>
          <li><b>Stack:</b> Django 5.2, PostgreSQL, Render, Chart.js.</li>
        </ul>
      </div>
    </div>
  </section>

  <div class="rowC">
    <section class="card">
      <h2><span class="n">3</span>Evaluation &amp; Analytics</h2>
      <ul>
        <li><b>How:</b> <code>manage.py evaluate</code>, fixed seeds: <b>4 labelled injected faults</b>, a healthy file, 10 labelled technician queries.</li>
        <li><b>What:</b> faults found, false events, top-1 accuracy, latency.</li>
      </ul>
      <div class="charts">{chart1}{chart2}</div>
      <div class="evalbottom">
        <table>
          <tr><th>Test</th><th>Result</th><th>Time</th></tr>
          <tr><td>Faulty file</td><td>4 / 4 faults named</td><td>162 ms</td></tr>
          <tr><td>Healthy file</td><td>1 extra event</td><td>137 ms</td></tr>
          <tr><td>Bad CSV</td><td>Clear error, no crash</td><td>1 ms</td></tr>
          <tr><td>Symptom</td><td>Correct top cause</td><td>60 ms</td></tr>
          <tr><td>Off-topic</td><td>“Not confident”</td><td>63 ms</td></tr>
        </table>
        <div><img class="shot" src="../img/overview.png" alt="FaultIQ analytics dashboard"><p class="cap">Analytics dashboard: fleet health, fault hours by type, faulty parts highlighted.</p></div>
      </div>
    </section>
    <section class="card">
      <h2><span class="n">5</span>Limitations &amp; Future Work</h2>
      <h3>What does not work well yet</h3>
      <ul>
        <li>Tested on <b>synthetic data</b>; real BAS exports are noisier.</li>
        <li>Rule thresholds are fixed (°C, a typical unit), not tuned per site.</li>
        <li>One 4-hour unexplained event remains on the healthy file.</li>
        <li>First embedding query after a restart takes about 10 s.</li>
      </ul>
      <h3 style="margin-top:20px">What we would improve next</h3>
      <ul>
        <li>Per-unit baselines from weeks of known-good data.</li>
        <li>Background job queue for year-long files.</li>
        <li>Cached embeddings in PostgreSQL (pgvector).</li>
        <li>Pilot on real buildings; direct BAS connectors.</li>
      </ul>
    </section>
  </div>
</main>
<footer>
  <div class="qr">{qr_github}<div class="lbl"><b>GitHub</b>github.com/meetmali/10_FaultIQ</div></div>
  <div class="qr">{qr_app}<div class="lbl"><b>Live app</b>faultiq-web.onrender.com</div></div>
  <div class="credit">Synthetic sample data · MIT licence<br>Open-source models: scikit-learn, BAAI/bge-small-en-v1.5</div>
</footer>
</body></html>
"""

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    (OUT / "poster.html").write_text(build(), encoding="utf-8")
    print(OUT / "poster.html")
