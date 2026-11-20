"""Template tags: the animated isometric rooftop unit (ported from the FaultIQ React UI) and a health ring."""

import math
from itertools import count

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()
_ids = count()

S, OX, OY, C30 = 30, 196, 118, 0.866
L, D, H = 6, 3, 2.2


def iso(x, y, z):
    return (OX + (x - y) * C30 * S, OY + (x + y) * 0.5 * S - z * S)


def pts(*p):
    return " ".join(f"{a:.1f},{b:.1f}" for a, b in p)


def front(x0, x1, z0, z1):
    return pts(iso(x0, D, z0), iso(x1, D, z0), iso(x1, D, z1), iso(x0, D, z1))


def end(y0, y1, z0, z1):
    return pts(iso(L, y0, z0), iso(L, y1, z0), iso(L, y1, z1), iso(L, y0, z1))


# Fault library code -> (highlighted areas, anchor for the callout, part label).
PARTS = {
    "econ-stuck-closed": ([front(0.25, 1.45, 0.55, 1.75)], iso(0.85, D, 1.15), "Outdoor-air damper"),
    "econ-stuck-open": ([front(0.25, 1.45, 0.55, 1.75)], iso(0.85, D, 1.15), "Outdoor-air damper"),
    "mat-sensor": ([front(1.45, 1.75, 0.6, 1.2)], iso(1.6, D, 0.9), "Mixed-air sensor"),
    "low-refrigerant": ([front(3.2, 4.3, 0.3, 1.5), front(4.6, 5.85, 0.25, 1.95)], iso(3.75, D, 0.9), "Refrigerant circuit"),
    "cooling-leak": ([front(3.2, 4.3, 0.3, 1.5)], iso(3.75, D, 0.9), "Compressor control"),
    "fan-off-occupied": ([front(1.7, 3.0, 0.3, 1.9)], iso(2.35, D, 1.1), "Supply fan"),
}
GLOW = {"fault": "var(--fault-glow)", "unclear": "var(--warn-glow)", "normal": "var(--ok)", "off": "var(--idle)"}


def _louvres(x0, x1, z0, z1, n, face, y0=0, y1=0):
    out = []
    for i in range(n):
        z = z0 + (z1 - z0) * (i + 0.5) / n
        a, b = (iso(x0, D, z), iso(x1, D, z)) if face == "front" else (iso(L, y0, z), iso(L, y1, z))
        out.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="var(--metal-edge)" stroke-width="0.9" opacity="0.75"/>')
    return "".join(out)


@register.simple_tag
def rtu(state="normal", fault_code=None, title="Rooftop unit", variant="hero"):
    """state: normal | fault | unclear | off. variant: hero | card | thumb."""
    uid = next(_ids)
    animate = state != "off" and variant != "thumb"
    part = PARTS.get(fault_code) if state in ("fault", "unclear") else None
    glow = GLOW.get(state, GLOW["normal"])
    o = [f'<svg viewBox="0 0 400 300" role="img" aria-label="{escape(title)}" class="rtu rtu-{variant}"><title>{escape(title)}</title>',
         f'<defs><linearGradient id="roof{uid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="var(--roof)"/><stop offset="1" stop-color="var(--raised)"/></linearGradient></defs>',
         f'<polygon points="{pts(iso(-1.4, -1, -0.05), iso(L + 1.4, -1, -0.05), iso(L + 1.4, D + 1.8, -0.05), iso(-1.4, D + 1.8, -0.05))}" fill="url(#roof{uid})"/>',
         f'<polygon points="{pts(iso(-0.15, D + 0.15, 0), iso(L + 0.15, D + 0.15, 0), iso(L + 0.15, D + 0.15, -0.12), iso(-0.15, D + 0.15, -0.12))}" fill="var(--metal-3)"/>']
    for x, color, rising in ((1.95, "var(--air-warm)", True), (3.05, "var(--air-cool)", False)):
        a, b, c, e = iso(x, D + 0.55, 0), iso(x + 0.55, D + 0.55, 0), iso(x + 0.55, D + 0.55, -1.1), iso(x, D + 0.55, -1.1)
        o.append(f'<polygon points="{pts(a, b, c, e)}" fill="var(--metal-2)" stroke="var(--metal-edge)" stroke-width="0.8"/>')
        if animate:
            mid, low = iso(x + 0.27, D + 0.55, 0), iso(x + 0.27, D + 0.55, -1.0)
            y1, y2 = (low[1], mid[1]) if rising else (mid[1], low[1])
            o.append(f'<line x1="{mid[0]:.1f}" y1="{y1:.1f}" x2="{low[0]:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="2.4" stroke-linecap="round" class="fq-flow" opacity="0.9"/>')
    o += [f'<polygon points="{pts(iso(0, 0, H), iso(L, 0, H), iso(L, D, H), iso(0, D, H))}" fill="var(--metal-1)" stroke="var(--metal-edge)"/>',
          f'<polygon points="{front(0, L, 0, H)}" fill="var(--metal-2)" stroke="var(--metal-edge)"/>',
          f'<polygon points="{end(0, D, 0, H)}" fill="var(--metal-3)" stroke="var(--metal-edge)"/>',
          f'<polygon points="{front(0.25, 1.45, 0.55, 1.75)}" fill="var(--metal-3)" stroke="var(--metal-edge)" stroke-width="0.8"/>',
          _louvres(0.3, 1.4, 0.6, 1.7, 6, "front")]
    if animate:
        a, b = iso(0.85, D + 1.3, 1.15), iso(0.85, D + 0.15, 1.15)
        o.append(f'<path d="M {a[0]:.1f} {a[1]:.1f} L {b[0]:.1f} {b[1]:.1f}" stroke="var(--air-cool)" stroke-width="2.4" stroke-linecap="round" class="fq-flow" fill="none"/>')
    o += [f'<polygon points="{front(1.7, 3.0, 0.3, 1.9)}" fill="var(--metal-1)" stroke="var(--metal-edge)" stroke-width="0.8"/>',
          f'<polygon points="{front(3.2, 4.3, 0.3, 1.5)}" fill="var(--metal-1)" stroke="var(--metal-edge)" stroke-width="0.8"/>',
          f'<polygon points="{front(3.35, 4.15, 1.6, 2.0)}" fill="var(--surface)" stroke="var(--metal-edge)" stroke-width="0.8"/>']
    lx, ly = iso(4.0, D, 1.8)
    o.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.6" fill="{glow}" class="{"fq-pulse" if part else ""}"/>')
    for i, z in enumerate((0.48, 0.78)):
        a, b = iso(4.0, D, z), iso(4.75, D, z)
        o.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="var(--refrigerant)" stroke-width="{2 if i == 0 else 3.2}" stroke-linecap="round"/>')
    o += [f'<polygon points="{front(4.6, 5.85, 0.25, 1.95)}" fill="var(--metal-3)" stroke="var(--metal-edge)" stroke-width="0.8"/>',
          _louvres(4.65, 5.8, 0.3, 1.9, 9, "front"),
          f'<polygon points="{end(0.2, 2.8, 0.25, 1.95)}" fill="var(--metal-3)" stroke="var(--metal-edge)" stroke-width="0.8"/>',
          _louvres(0, 0, 0.3, 1.9, 9, "end", 0.25, 2.75)]
    fx, fy = iso(5.0, 1.5, H)
    blades = "".join(f'<path d="M0 0 C 6 -6, 18 -10, 23 -3 C 14 -1, 6 2, 0 0 Z" fill="var(--metal-edge)" transform="rotate({a})"/>' for a in (0, 90, 180, 270))
    o.append(f'<g transform="translate({fx:.1f} {fy:.1f}) scale(1 0.55)"><circle r="27" fill="var(--metal-2)" stroke="var(--metal-edge)" stroke-width="1.4"/>'
             f'<g class="{"fq-spin" if animate else ""}">{blades}<circle r="4" fill="var(--metal-3)"/></g></g>')
    if animate:
        for dx in (-14, 0, 14):
            o.append(f'<path d="M {fx + dx:.1f} {fy - 10:.1f} q 6 -12 0 -24 q -6 -12 0 -24" stroke="var(--air-warm)" stroke-width="2" fill="none" stroke-linecap="round" class="fq-flow" opacity="0.75"/>')
    sx, sy = iso(3.25, D + 0.55, -0.4)
    o.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="3.4" fill="var(--surface)" stroke="var(--metal-edge)" stroke-width="1.2"/>')
    if part:
        areas, (cx, cy), label = part
        for p in areas:
            o.append(f'<polygon points="{p}" fill="{glow}" fill-opacity="0.45" stroke="{glow}" stroke-width="2.2" class="{"" if variant == "thumb" else "fq-pulse"}"/>')
        if variant != "thumb":
            size = 15 if variant == "card" else 12.5
            w, h = len(label) * size * 0.56 + 18, size + 14
            left = cx < 200
            bx, by = (6 if left else 394 - w), 6
            o.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{bx + w * (0.6 if left else 0.4):.1f}" y2="{by + h:.1f}" stroke="{glow}" stroke-width="1.4"/>'
                     f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" fill="{glow}"/>'
                     f'<rect x="{bx:.1f}" y="{by}" width="{w:.1f}" height="{h}" rx="7" fill="var(--surface)" stroke="{glow}" stroke-width="1.4"/>'
                     f'<text x="{bx + w / 2:.1f}" y="{by + h / 2 + size * 0.36:.1f}" text-anchor="middle" font-size="{size}" font-weight="600" fill="var(--ink)">{escape(label)}</text>')
    o.append("</svg>")
    return mark_safe("".join(o))


@register.simple_tag
def health_ring(healthy, total, label="units healthy"):
    """A donut showing the share of healthy units, with the count in the middle."""
    share = healthy / total if total else 0
    r, c = 52, 2 * math.pi * 52
    return mark_safe(
        f'<svg viewBox="0 0 140 140" class="ring" role="img" aria-label="{healthy} of {total} {escape(label)}">'
        f'<circle cx="70" cy="70" r="{r}" fill="none" stroke="var(--fault-line)" stroke-width="14"/>'
        f'<circle cx="70" cy="70" r="{r}" fill="none" stroke="var(--ok)" stroke-width="14" stroke-linecap="round" '
        f'stroke-dasharray="{c * share:.1f} {c:.1f}" transform="rotate(-90 70 70)"/>'
        f'<text x="70" y="68" text-anchor="middle" font-size="30" font-weight="700" fill="var(--ink)">{healthy}/{total}</text>'
        f'<text x="70" y="90" text-anchor="middle" font-size="11" fill="var(--muted)">{escape(label)}</text></svg>'
    )
