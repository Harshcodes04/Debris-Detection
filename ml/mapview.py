"""Standalone map view: a single HTML file with the survey picture in it.

The dashboard will eventually render this from the API. This exists so the
survey-to-survey layer can be shown without waiting for that, and without a
server or a network - it writes one self-contained HTML file with the geometry
inlined as SVG. No tiles, no CDN, no Leaflet. It opens by double-clicking, and
it works on a boat with no signal, which is the same property the detector has.

There is no basemap, deliberately. A tile layer needs a network, and the thing
worth looking at here is the relationship between hazards, not the coastline.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

W, H, PAD = 900, 620, 60

STATUS_COLOUR = {
    "present": "#38bdf8",
    "unconfirmed": "#fbbf24",
    "gone": "#64748b",
    "recovered": "#4ade80",
}


def _project(entries, cells):
    """Lat/lon to pixels. Equirectangular - fine over a survey-sized area."""
    lats = [e.lat for e in entries] + [c.lat for c in cells]
    lons = [e.lon for e in entries] + [c.lon for c in cells]
    if not lats:
        return lambda la, lo: (W / 2, H / 2), (0, 0, 0, 0)

    pad_deg = 0.004
    la0, la1 = min(lats) - pad_deg, max(lats) + pad_deg
    lo0, lo1 = min(lons) - pad_deg, max(lons) + pad_deg
    span_la = max(la1 - la0, 1e-6)
    span_lo = max(lo1 - lo0, 1e-6)

    def to_px(la, lo):
        x = PAD + (lo - lo0) / span_lo * (W - 2 * PAD)
        y = PAD + (la1 - la) / span_la * (H - 2 * PAD)   # north at the top
        return x, y

    return to_px, (la0, la1, lo0, lo1)


def render(entries, cells, out_path, *, cell_deg=0.0045, title="Survey area"):
    """Write a self-contained HTML map of the registry and the risk grid."""
    out_path = Path(out_path)
    to_px, (la0, la1, lo0, lo1) = _project(entries, cells)
    peak = max((c.risk_sum for c in cells), default=1.0) or 1.0

    parts = []

    # risk cells underneath
    for c in cells:
        x0, y0 = to_px(c.lat + cell_deg / 2, c.lon - cell_deg / 2)
        x1, y1 = to_px(c.lat - cell_deg / 2, c.lon + cell_deg / 2)
        intensity = c.risk_sum / peak
        parts.append(
            f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1-x0:.1f}" '
            f'height="{y1-y0:.1f}" fill="#f97316" fill-opacity="{0.10 + 0.45*intensity:.3f}" '
            f'stroke="#f97316" stroke-opacity="0.35"><title>'
            f'{c.count} hazards, risk {c.risk_sum:.2f}, '
            f'{c.persistent} confirmed across surveys</title></rect>')

    # hazards on top
    for e in entries:
        x, y = to_px(e.lat, e.lon)
        colour = STATUS_COLOUR.get(e.status, "#94a3b8")
        r = 5 + min(e.times_seen, 4) * 1.6      # repeat sightings read as bigger
        tip = (f"{e.hazard_id}  {e.cls}\n{e.status}, seen {e.times_seen}x\n"
               f"first {e.first_seen}, last {e.last_seen}")
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{colour}" '
            f'fill-opacity="0.85" stroke="#0b0e14" stroke-width="1.5">'
            f'<title>{html.escape(tip)}</title></circle>')
        if e.times_seen > 1:
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r+5:.1f}" fill="none" '
                f'stroke="{colour}" stroke-opacity="0.4" stroke-dasharray="2 3"/>')

    legend = "".join(
        f'<span class="k"><i style="background:{c}"></i>{s}</span>'
        for s, c in STATUS_COLOUR.items())

    counts = {}
    for e in entries:
        counts[e.status] = counts.get(e.status, 0) + 1
    stats = " &nbsp;·&nbsp; ".join(f"{v} {k}" for k, v in sorted(counts.items()))

    doc = f"""<!doctype html>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
  body {{ margin:0; background:#0b0e14; color:#e6e9ef;
         font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif; }}
  .wrap {{ max-width:{W}px; margin:24px auto; padding:0 16px; }}
  h1 {{ font-size:17px; font-weight:600; margin:0 0 2px; }}
  .sub {{ color:#8b93a7; font-size:12.5px; margin-bottom:14px; }}
  svg {{ background:#11151d; border:1px solid #1f2632; border-radius:8px;
         display:block; }}
  .legend {{ margin-top:12px; display:flex; gap:16px; flex-wrap:wrap;
             font-size:12.5px; color:#aab3c5; }}
  .k {{ display:flex; align-items:center; gap:6px; }}
  .k i {{ width:11px; height:11px; border-radius:50%; display:inline-block; }}
  .note {{ margin-top:14px; color:#6b7488; font-size:12px; max-width:62ch; }}
  .stat {{ color:#e6e9ef; }}
</style>
<div class="wrap">
  <h1>{html.escape(title)}</h1>
  <div class="sub">
    <span class="stat">{stats}</span> &nbsp;·&nbsp;
    {la0:.4f}–{la1:.4f}°N, {lo0:.4f}–{lo1:.4f}°E &nbsp;·&nbsp;
    orange cells are accumulated risk &nbsp;·&nbsp; hover for detail
  </div>
  <svg viewBox="0 0 {W} {H}" width="100%" height="{H}">{''.join(parts)}</svg>
  <div class="legend">{legend}
    <span class="k">ringed = seen in more than one survey</span>
  </div>
  <div class="note">
    Hazard size grows with repeat sightings. A ringed marker has been detected
    in more than one survey, so it is confirmed real and still uncollected —
    those are the ones worth sending a crew to. No basemap and no network:
    this file is self-contained.
  </div>
</div>"""
    out_path.write_text(doc, encoding="utf-8")
    return out_path
