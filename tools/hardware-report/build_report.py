"""Build the hardware research report: an interactive bilingual page + two docs copies.

    python tools/hardware-report/build_report.py

Outputs
  tools/hardware-report/farm-hardware-plan.html   (published as a private page)
  docs/HARDWARE_RESEARCH.md / docs/HARDWARE_RESEARCH.ar.md
Inputs: data.py, the real farm layout (packages/map-model/src/farm-geometry.json) and the zone
catalog in apps/api/farm.db (falls back to built-in values).
"""
from __future__ import annotations

import html
import json
import math
import sqlite3
from pathlib import Path

import data as D

ROOT = Path(__file__).resolve().parents[2]
GEO = json.loads((ROOT / "packages/map-model/src/farm-geometry.json").read_text(encoding="utf-8"))
M = GEO["georef"]["m_per_unit"]
(LAT0, LON0), (LAT1, LON1) = GEO["georef"]["top_left_latlon"], GEO["georef"]["bottom_right_latlon"]
W, H = GEO["viewBox"][2], GEO["viewBox"][3]
CTRL = (402.0, 322.0)


def latlon(p):
    return round(LAT0 + (LAT1 - LAT0) * p[1] / H, 6), round(LON0 + (LON1 - LON0) * p[0] / W, 6)


def dist(a, b):
    return math.dist(a, b) * M


def centroid(pts):
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        c = x1 * y2 - x2 * y1
        a += c
        cx += (x1 + x2) * c
        cy += (y1 + y2) * c
    a *= 0.5
    return (cx / (6 * a), cy / (6 * a)) if a else pts[0]


def zone_catalog():
    try:
        c = sqlite3.connect(ROOT / "apps/api/farm.db")
        return {r[0]: r[1:] for r in c.execute("select id, name, name_ar, crop_type, area_ha, flow_max_m3h from zones")}
    except sqlite3.Error:
        return {}


def cable_m(v):
    pts = GEO["network"]["mainline"][v["trunk"]]
    best, acc = None, 0.0
    for a, b in zip(pts, pts[1:]):
        ab = (b[0] - a[0], b[1] - a[1])
        l2 = ab[0] ** 2 + ab[1] ** 2
        t = max(0.0, min(1.0, ((v["tap"][0] - a[0]) * ab[0] + (v["tap"][1] - a[1]) * ab[1]) / l2)) if l2 else 0.0
        q = (a[0] + t * ab[0], a[1] + t * ab[1])
        d = math.dist(q, v["tap"])
        if best is None or d < best[0]:
            best = (d, acc + dist(a, q))
        acc += dist(a, b)
    return best[1] + dist(v["tap"], v["valve"]) + dist(CTRL, pts[0])


def zone_plan():
    cat = zone_catalog()
    rows = []
    for zid, v in GEO["network"]["valves"].items():
        name, name_ar, crop, _area, fmax = cat.get(zid, (zid, zid, "pomegranate", 0.5, 8.0))
        feat = GEO["features"][zid]
        area = round(feat["area_m2"] / 10000, 2)
        depths = D.CROP_DEPTHS.get(crop, (30, 60))
        if area < D.SMALL_ZONE_HA:
            depths = (int(sum(depths) / 2 // 10 * 10),)
        c = centroid([tuple(p) for p in feat["points"]])
        rows.append({
            "id": zid, "name": {"en": name, "ar": name_ar}, "crop": crop, "area": area, "flow": fmax,
            "valve": '1"' if fmax <= 4 else '1½"' if fmax <= 11 else '2"',
            "valve_ll": latlon(v["valve"]), "valve_xy": v["valve"],
            "cable": round(cable_m(v) * 1.15 / 5) * 5, "sensor_ll": latlon(c), "sensor_xy": c, "depths": list(depths),
            "box": {"trunk_n": "north", "trunk_w": "west"}.get(v["trunk"], "south-east"),
        })
    rows.sort(key=lambda r: r["cable"])
    for i, r in enumerate(rows, 1):
        r["n"] = i
        r["near"] = i <= 6
    return rows


BOX_LABEL = {"north": {"en": "north box", "ar": "صندوق الشمال"}, "west": {"en": "west box", "ar": "صندوق الغرب"},
             "south-east": {"en": "south-east box", "ar": "صندوق الجنوب الشرقي"}}


def conn_text(z, lang):
    if z["near"]:
        return D.T["conn_cable"][lang]
    return f"{D.T['conn_box'][lang]} ({BOX_LABEL[z['box']][lang]})"


def preset_total(preset):
    hw = imported = 0.0
    for it in D.ITEMS:
        for o in it["options"]:
            if preset in o["presets"]:
                hw += o["qty"] * o["unit"]
                if not it.get("local"):
                    imported += o["qty"] * o["unit"]
                break
    rate = D.INSTALL_OWN if D.PRESET_INSTALL.get(preset) == "own" else D.INSTALL
    f, i = imported * D.FREIGHT_AND_PORT, imported * rate
    c = (hw + f + i) * D.CONTINGENCY
    return {"hardware": hw, "total": hw + f + i + c}


# ─── Map (SVG with hotspots) ────────────────────────────────────────────
def map_svg(zones):
    pts = lambda ps: " ".join(f"{x:.0f},{y:.0f}" for x, y in ps)
    bx = [x for x, _ in GEO["features"]["boundary"]["points"]]
    by = [y for _, y in GEO["features"]["boundary"]["points"]]
    x0, y0, x1, y1 = min(bx) - 30, min(by) - 50, max(bx) + 30, max(by) + 40
    o = [f'<svg viewBox="{x0:.0f} {y0:.0f} {x1 - x0:.0f} {y1 - y0:.0f}" class="map" role="group" aria-labelledby="map-h">']
    o.append(f'<polygon class="m-boundary" points="{pts(GEO["features"]["boundary"]["points"])}"/>')
    for z in zones:
        o.append(f'<polygon class="m-zone hot" data-zone="{z["id"]}" points="{pts(GEO["features"][z["id"]]["points"])}"/>')
    for line in GEO["network"]["mainline"].values():
        o.append(f'<polyline class="m-cable" points="{pts(line)}"/>')
    for z in zones:
        sx, sy = z["sensor_xy"]
        o.append(f'<g class="m-sensor hot" data-zone="{z["id"]}" data-kind="sensor" tabindex="0" role="button">'
                 f'<polygon points="{sx:.0f},{sy - 12:.0f} {sx - 11:.0f},{sy + 8:.0f} {sx + 11:.0f},{sy + 8:.0f}"/>'
                 f'<text class="ar-only" x="{sx:.0f}" y="{sy + 26:.0f}">{html.escape(z["name"]["ar"])}</text>'
                 f'<text class="en-only" x="{sx:.0f}" y="{sy + 26:.0f}">{html.escape(z["name"]["en"])}</text></g>')
    for z in zones:
        vx, vy = z["valve_xy"]
        o.append(f'<g class="m-valve hot" data-zone="{z["id"]}" data-kind="valve" tabindex="0" role="button">'
                 f'<circle cx="{vx:.0f}" cy="{vy:.0f}" r="12"/><text x="{vx:.0f}" y="{vy + 4.5:.0f}">{z["n"]}</text></g>')
    eq = GEO["equipment"]
    marks = [("C", "control", CTRL, (28, 0)), ("W", "well", tuple(eq["wellhead"]["at"]), (28, -16)),
             ("T", "tank", tuple(eq["tank"]["at"]), (-32, 12)), ("H", "head", tuple(eq["booster"]["at"]), (32, 20))]
    for k, loc, (x, y), (dx, dy) in marks:
        o.append(f'<line class="m-lead" x1="{x:.0f}" y1="{y:.0f}" x2="{x + dx:.0f}" y2="{y + dy:.0f}"/>'
                 f'<g class="m-eq hot" data-loc="{loc}" tabindex="0" role="button"><rect x="{x + dx - 13:.0f}" y="{y + dy - 13:.0f}" width="26" height="26" rx="5"/>'
                 f'<text x="{x + dx:.0f}" y="{y + dy + 5:.0f}">{k}</text></g>')
    o.append(f'<text class="m-north" x="{x1 - 50:.0f}" y="{y0 + 30:.0f}">N ↑</text>')
    o.append(f'<g class="m-scale"><line x1="{x0 + 20:.0f}" y1="{y1 - 15:.0f}" x2="{x0 + 20 + 100 / M:.0f}" y2="{y1 - 15:.0f}"/>'
             f'<text x="{x0 + 20:.0f}" y="{y1 - 25:.0f}">100 m</text></g>')
    o.append("</svg>")
    return "".join(o)


def preset_on(preset):
    return {it["id"] for it in D.ITEMS if any(preset in o["presets"] for o in it["options"])}


def cap_on(cap, on):
    return all(any(i in on for i in group) for group in cap["need"])


# ─── Markdown copies ────────────────────────────────────────────────────
def money_md(x, lang):
    return f"${x:,.0f} · {x * D.USD_TO_LYD:,.0f} {'د.ل' if lang == 'ar' else 'LYD'}"


def strip_b(s):
    return s.replace("<b>", "**").replace("</b>", "**")


def build_md(zones, lang):
    t = lambda k: D.T[k][lang]
    P = D.PRESETS
    L = ["<!-- Generated by tools/hardware-report/build_report.py from data.py. Edit the data, not this file. -->", ""]
    if lang == "ar":
        L += ['<div dir="rtl">', ""]
    other = "HARDWARE_RESEARCH.md" if lang == "ar" else "HARDWARE_RESEARCH.ar.md"
    L += [f"# {t('title')}", "",
          f"{'تاريخ البحث' if lang == 'ar' else 'Researched'} {D.RESEARCHED_ON} · 1 USD = {D.USD_TO_LYD} LYD · "
          f"[{'English' if lang == 'ar' else 'العربية'}]({other})", "", t("price_note"), ""]
    L += [*(f"- {strip_b(s[lang])}" for s in D.SUMMARY), ""]
    L += ["| | " + " | ".join(D.PRESET_LABEL[p][lang] for p in P) + " |", "|---|" + "---:|" * len(P)]
    L.append(f"| {t('hardware')} | " + " | ".join(money_md(preset_total(p)['hardware'], lang) for p in P) + " |")
    L.append(f"| **{t('total')}** | " + " | ".join(money_md(preset_total(p)['total'], lang) for p in P) + " |")
    L += ["", f"{t('total')} = {t('hardware')} + {t('freight')} {D.FREIGHT_AND_PORT:.0%} + {t('install')} {D.INSTALL:.0%} ({D.PRESET_LABEL['lowest'][lang]}: {D.INSTALL_OWN:.0%}) + {t('contingency')} {D.CONTINGENCY:.0%}.", ""]
    for p in P:
        L.append(f"- **{D.PRESET_LABEL[p][lang]}:** {D.PRESET_NOTE[p][lang]}")
    L += ["", f"### {t('caps')}", "", "| | " + " | ".join(D.PRESET_LABEL[p][lang] for p in P) + " |", "|---|" + ":---:|" * len(P)]
    for cap in D.CAPS:
        L.append(f"| {cap[lang]} | " + " | ".join("✓" if cap_on(cap, preset_on(p)) else "—" for p in P) + " |")
    L += ["", f"## {t('items')}"]
    group = None
    for it in D.ITEMS:
        if it["group"] != group:
            group = it["group"]
            L += ["", f"### {D.GROUPS[group][lang]}", "",
                  f"| | {t('phase')} | " + " | ".join(D.PRESET_LABEL[p][lang] for p in P) + " |", "|---|---|" + "---|" * len(P)]
        cells = []
        for p in P:
            o = next((o for o in it["options"] if p in o["presets"]), None)
            if not o:
                cells.append("—")
                continue
            b = t("est") if o["basis"] == "est" else f"[{t('src')}]({D.SOURCES[o['basis']][1]})"
            cells.append(f"{o['product'][lang]}: **${o['qty'] * o['unit']:,.0f}** ({b})")
        tag = t("essential") if it["minimum"] else t("optional")
        what = it["what"][lang] + (f" — *{t('if_skipped')}: {it['skip'][lang]}*" if it["skip"][lang] else "")
        alts = [o for o in it["options"] if not o["presets"]]
        if alts:
            what += " — " + ("بدائل" if lang == "ar" else "Alternatives") + ": " + "; ".join(
                f"{o['product'][lang]} (${o['qty'] * o['unit']:,.0f}{', ' + o['note'][lang] if o['note'][lang] else ''})" for o in alts)
        L.append(f"| {what} ({tag}) | {it['phase']} | " + " | ".join(cells) + " |")
    L += ["", f"## {t('zones')}", "", t("zones_note"), "",
          f"| # | {'المنطقة' if lang == 'ar' else 'Zone'} | {t('crop')} | {t('area')} (ha) | {t('valve')} | {'موقع الصمام' if lang == 'ar' else 'Valve lat, lon'} | {t('cable')} (m) | {t('connection')} | {t('sensors')} | {'موقع المحطة' if lang == 'ar' else 'Station lat, lon'} |",
          "|---:|---|---|---:|---|---|---:|---|---|---|"]
    for z in zones:
        L.append(f"| {z['n']} | {z['name'][lang]} | {D.CROP_LABEL[z['crop']][lang]} | {z['area']} | {z['valve']} | {z['valve_ll'][0]}, {z['valve_ll'][1]} | "
                 f"{z['cable']} | {conn_text(z, lang)} | {len(z['depths'])} × {', '.join(map(str, z['depths']))} cm | {z['sensor_ll'][0]}, {z['sensor_ll'][1]} |")
    L += ["", f"## {t('map')}", ""]
    for loc in D.LOCATIONS.values():
        L.append(f"- **{loc[lang]}:** {loc['how_' + lang]}")
    L += ["", t("routes_guess"), "", f"## {t('override')}", "", "| " + " | ".join(D.OVERRIDE_HEAD[lang]) + " |", "|---|---|---|"]
    L += ["| " + " | ".join(r[lang]) + " |" for r in D.OVERRIDE]
    L += ["", f"## {t('plc')}", "", "| " + " | ".join(D.PLC_HEAD[lang]) + " |", "|---|---|---|---|---|"]
    L += ["| " + " | ".join(r[lang]) + " |" for r in D.PLC_OPTIONS]
    L += ["", f"## {t('wiring')}", "", "| " + " | ".join(D.WIRING_HEAD[lang]) + " |", "|---|---|---|---|---|"]
    L += ["| " + " | ".join(r[lang]) + " |" for r in D.WIRING]
    L += ["", f"## {t('buying')}", "", *(f"- {strip_b(b[lang])}" for b in D.BUYING)]
    L += ["", f"## {t('survey')}", "", *(f"- {s[lang]}" for s in D.SURVEY)]
    L += ["", f"## {t('future')}", "", "| " + " | ".join(D.FUTURE_HEAD[lang]) + " |", "|---|---|---|"]
    L += ["| " + " | ".join(r[lang]) + " |" for r in D.FUTURE]
    L += ["", f"## {t('sources')}", "", *(f"- [{label}]({url})" for label, url in D.SOURCES.values())]
    if lang == "ar":
        L += ["", "</div>"]
    return "\n".join(L) + "\n"


# ─── Interactive page ───────────────────────────────────────────────────
CSS = r"""
:root{
  /* Layout: one column (max 1120px); a sticky cost bar under the header; builder rows stack on phones */
  --bg:#f4f5f0;--surface:#ffffff;--ink:#16211b;--muted:#5a6a60;--line:#dde2d8;--soft:#e8eee5;
  --accent:#1d6b58;--accent-ink:#ffffff;--sand:#b8955a;--cable:#a5532f;--est:#8a6d2f;--essential:#1d6b58;
  --f-display:"Space Grotesk","IBM Plex Sans Arabic",system-ui,sans-serif;
  --f-body:"IBM Plex Sans","IBM Plex Sans Arabic",system-ui,sans-serif;
  --f-mono:"IBM Plex Mono",ui-monospace,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#0f1512;--surface:#16201a;--ink:#e5ebe5;--muted:#9aa89f;--line:#28342d;--soft:#1c2923;--accent:#5fc3a6;--accent-ink:#0c1410;--sand:#d4b277;--cable:#e08a5f;--est:#d4b277;--essential:#5fc3a6;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0f1512;--surface:#16201a;--ink:#e5ebe5;--muted:#9aa89f;--line:#28342d;--soft:#1c2923;--accent:#5fc3a6;--accent-ink:#0c1410;--sand:#d4b277;--cable:#e08a5f;--est:#d4b277;--essential:#5fc3a6;color-scheme:dark}
html[lang="ar"] body{font-family:"IBM Plex Sans Arabic","IBM Plex Sans",system-ui,sans-serif}
html[lang="ar"] h1,html[lang="ar"] h2,html[lang="ar"] h3{font-family:"IBM Plex Sans Arabic",sans-serif;font-weight:700}
body{background:var(--bg);color:var(--ink);font-family:var(--f-body);font-size:15px;line-height:1.6}
.wrap{max-width:1120px;margin:0 auto;padding-block:28px 64px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));display:flex;flex-direction:column;gap:36px}
header{display:flex;flex-direction:column;gap:10px}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.eyebrow{font-family:var(--f-mono);font-size:12px;letter-spacing:.04em;color:var(--muted)}
h1{font-family:var(--f-display);font-size:clamp(26px,4vw,38px);line-height:1.25;margin:0;text-wrap:balance}
h2{font-family:var(--f-display);font-size:21px;margin:0;text-wrap:balance}
h3{font-family:var(--f-display);font-size:16px;margin:8px 0 0}
p{margin:0;max-width:72ch}
.lede{color:var(--muted)}
section{display:flex;flex-direction:column;gap:12px;min-width:0}
button{font:inherit;color:inherit;cursor:pointer}
.btn{border:1px solid var(--line);background:var(--surface);border-radius:8px;padding:6px 14px;min-height:38px}
.seg{display:inline-flex;flex-wrap:wrap;border:1px solid var(--line);border-radius:10px;background:var(--surface);padding:3px;gap:3px}
.seg button{border:0;background:none;border-radius:7px;padding:6px 12px;min-height:36px;color:var(--muted)}
.seg button[aria-pressed="true"]{background:var(--accent);color:var(--accent-ink);font-weight:600}
.controls{display:flex;flex-wrap:wrap;gap:12px 20px;align-items:center}
.controls>div{font-size:13px;color:var(--muted);display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.bar{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:color-mix(in srgb,var(--bg) 92%,transparent);backdrop-filter:blur(6px);border-block:1px solid var(--line);padding-block:10px}
.bar-in{display:flex;flex-wrap:wrap;gap:4px 20px;align-items:baseline}
.big{font-family:var(--f-display);font-size:26px;font-variant-numeric:tabular-nums}
.kv{font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}
.kv b{color:var(--ink);font-weight:600}
.phases{display:flex;gap:4px 14px;flex-wrap:wrap}
ul.points{margin:0;padding-inline-start:20px;display:flex;flex-direction:column;gap:8px;max-width:80ch}
.note{background:var(--soft);border-radius:10px;padding:10px 14px;font-size:14px;max-width:none}
.note.approve{border-inline-start:4px solid var(--accent)}
.note.warn{border-inline-start:4px solid var(--cable)}
.note.warn ul{margin:4px 0 0;padding-inline-start:18px}
ul.caps{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:6px 18px}
ul.caps li{display:flex;gap:8px;align-items:baseline;font-size:14px}
ul.caps li.no{color:var(--muted)}
ul.caps .mark{font-weight:700;width:1em;flex-shrink:0;text-align:center}
ul.caps li.yes .mark{color:var(--accent)}
.mapgrid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:16px;align-items:start}
@media (max-width:780px){.mapgrid{grid-template-columns:1fr}}
.map{width:100%;height:auto;background:var(--soft);border-radius:12px;border:1px solid var(--line)}
.m-boundary{fill:none;stroke:var(--sand);stroke-width:3;stroke-dasharray:8 6}
.m-zone{fill:color-mix(in srgb,var(--accent) 10%,transparent);stroke:var(--accent);stroke-width:1.4}
.m-zone.sel{fill:color-mix(in srgb,var(--accent) 30%,transparent)}
.m-cable{fill:none;stroke:var(--cable);stroke-width:5;stroke-linecap:round;stroke-linejoin:round;opacity:.85;pointer-events:none}
.hot{cursor:pointer}
.hot:focus{outline:none}
.hot:focus-visible circle,.hot:focus-visible rect,.hot:focus-visible polygon{stroke:var(--ink);stroke-width:4}
.m-valve circle{fill:var(--accent);stroke:var(--surface);stroke-width:3}
.m-valve.sel circle{fill:var(--cable)}
.m-valve text{fill:var(--accent-ink);font:700 13px var(--f-mono);text-anchor:middle;pointer-events:none}
.m-sensor polygon{fill:var(--sand);stroke:var(--surface);stroke-width:2}
.m-sensor.sel polygon{fill:var(--cable)}
.m-sensor text{fill:var(--ink);font:600 15px "IBM Plex Sans Arabic",sans-serif;text-anchor:middle;paint-order:stroke;stroke:var(--soft);stroke-width:4;pointer-events:none}
.m-eq rect{fill:var(--ink)}
.m-eq.sel rect{fill:var(--cable)}
.m-eq text{fill:var(--bg);font:700 14px var(--f-mono);text-anchor:middle;pointer-events:none}
.m-lead{stroke:var(--ink);stroke-width:1.5}
.m-north,.m-scale text{fill:var(--muted);font:600 16px var(--f-mono)}
.m-scale line{stroke:var(--muted);stroke-width:3}
html[lang="ar"] .en-only, html[lang="en"] .ar-only{display:none}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13px;color:var(--muted)}
.legend>span{display:inline-flex;align-items:center;gap:6px}
.sw{width:14px;height:14px;border-radius:50%;background:var(--accent);display:inline-block}
.sw.tri{border-radius:0;background:none;width:0;height:0;border-left:7px solid transparent;border-right:7px solid transparent;border-bottom:13px solid var(--sand)}
.sw.sq{border-radius:3px;background:var(--ink)}
.sw.line{border-radius:0;height:0;width:22px;border-top:4px solid var(--cable)}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px;display:flex;flex-direction:column;gap:10px;min-width:0}
.panel h3{margin:0}
.panel dl{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;margin:0;font-size:14px}
.panel dt{color:var(--muted)}
.panel dd{margin:0}
.panel ul{margin:4px 0 0;padding-inline-start:18px;font-size:14px;display:flex;flex-direction:column;gap:4px}
.group{display:flex;flex-direction:column;gap:8px}
.row{display:grid;grid-template-columns:auto minmax(0,1fr) minmax(0,1.25fr) auto;gap:8px 14px;align-items:start;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.row.off{opacity:.55}
.row.off .cost{text-decoration:line-through}
@media (max-width:780px){.row{grid-template-columns:auto minmax(0,1fr)}.row .opt,.row .cost{grid-column:2}.row .cost{text-align:start}}
.row input[type=checkbox]{width:20px;height:20px;margin-top:3px;accent-color:var(--accent)}
.what{display:flex;flex-direction:column;gap:4px;min-width:0}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{font-size:11.5px;border-radius:999px;padding:1px 8px;border:1px solid var(--line);color:var(--muted)}
.chip.ess{border-color:var(--essential);color:var(--essential);font-weight:600}
.skip{font-size:13px;color:var(--muted)}
.opt{display:flex;flex-direction:column;gap:4px;min-width:0}
select{font:inherit;font-size:14px;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:6px 8px;max-width:100%;min-height:38px}
.optnote{font-size:12.5px;color:var(--muted)}
.cost{font-family:var(--f-mono);font-size:14px;text-align:end;white-space:nowrap;font-variant-numeric:tabular-nums}
.cost small{display:block;color:var(--muted);font-size:11.5px}
.src{font-family:var(--f-mono);font-size:11.5px;color:var(--accent)}
.est{font-family:var(--f-mono);font-size:11.5px;color:var(--est)}
.tablebox{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:start;vertical-align:top}
th{font-size:12px;color:var(--muted);background:var(--soft);font-weight:600}
td.num{text-align:end;font-variant-numeric:tabular-nums;white-space:nowrap}
td.mono{font-family:var(--f-mono);font-size:12.5px;white-space:nowrap}
tr:last-child td{border-bottom:0}
tr.sel td{background:var(--soft)}
a{color:var(--accent)}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
footer{color:var(--muted);font-size:13px}
@media (prefers-reduced-motion:no-preference){.row,.m-zone{transition:opacity .15s,fill .15s}}
"""

JS = r"""
const DATA = JSON.parse(document.getElementById('data').textContent);
const S = {lang:'ar', cur:'USD', preset:'recommended', install:'contractor', sel:{}, focus:null};
try { const v = JSON.parse(localStorage.getItem('farmHw') || '{}'); if (v.lang) S.lang = v.lang; if (v.cur) S.cur = v.cur; } catch (e) {}
const save = () => { try { localStorage.setItem('farmHw', JSON.stringify({lang:S.lang, cur:S.cur})); } catch (e) {} };
const t = k => (DATA.T[k] || {})[S.lang] || k;
const L = o => (o && typeof o === 'object' && 'en' in o) ? o[S.lang] : o;
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const nf = new Intl.NumberFormat('en-US', {maximumFractionDigits: 0});
const lydLabel = () => S.lang === 'ar' ? ' د.ل' : ' LYD';
const money = usd => S.cur === 'USD' ? '$' + nf.format(usd) : nf.format(usd * DATA.rate) + lydLabel();
const other = usd => S.cur === 'USD' ? nf.format(usd * DATA.rate) + lydLabel() : '$' + nf.format(usd);

function defaultOpt(it) {
  for (const p of ['recommended','basic','premium','minimum']) { const o = it.options.find(o => o.presets.includes(p)); if (o) return o.key; }
  return it.options[0].key;
}
function applyPreset(p) {
  S.preset = p;
  S.install = DATA.presetInstall[p] || 'contractor';
  for (const it of DATA.items) {
    const o = it.options.find(o => o.presets.includes(p));
    S.sel[it.id] = o ? {on:true, opt:o.key} : {on:false, opt:defaultOpt(it)};
  }
}
const optOf = it => it.options.find(o => o.key === S.sel[it.id].opt) || it.options[0];
const costOf = it => S.sel[it.id].on ? optOf(it).qty * optOf(it).unit : 0;

function totals() {
  const k = Object.assign({}, DATA.k, {install: S.install === 'own' ? DATA.k.installOwn : DATA.k.install});
  let hw = 0, imp = 0, n = 0; const ph = {1:0, 2:0, 3:0};
  for (const it of DATA.items) {
    const c = costOf(it); if (!c) continue;
    n++; hw += c; if (!it.local) imp += c;
    ph[it.phase] += (it.local ? c : c * (1 + k.freight + k.install)) * (1 + k.contingency);
  }
  const f = imp * k.freight, i = imp * k.install, c = (hw + f + i) * k.contingency;
  return {hw, f, i, c, n, total: hw + f + i + c, ph};
}
const isOn = id => S.sel[id] && S.sel[id].on;
function condOk(cond) {
  const [id, ...vals] = cond;
  if (vals[0] === 'on') return isOn(id);
  if (vals[0] === 'off') return !isOn(id);
  return isOn(id) && vals.includes(S.sel[id].opt);
}
function renderCaps() {
  document.getElementById('caps').innerHTML = DATA.caps.map(c => {
    const ok = c.need.every(g => g.some(isOn));
    return `<li class="${ok ? 'yes' : 'no'}"><span class="mark" aria-hidden="true">${ok ? '✓' : '—'}</span>${esc(L(c))}</li>`;
  }).join('');
  const warn = DATA.checks.filter(ch => ch.when.every(condOk));
  const box = document.getElementById('checks');
  box.hidden = !warn.length;
  box.innerHTML = `<b>${t('checks')}</b><ul>${warn.map(w => `<li>${esc(L(w))}</li>`).join('')}</ul>`;
}
function basis(o) {
  if (o.basis === 'est') return `<span class="est">${t('est')}</span>`;
  const s = DATA.sources[o.basis];
  return `<a class="src" href="${s[1]}" target="_blank" rel="noopener" title="${esc(s[0])}">${t('src')}</a>`;
}

function renderStatic() {
  document.documentElement.lang = S.lang;
  document.documentElement.dir = S.lang === 'ar' ? 'rtl' : 'ltr';
  document.querySelectorAll('[data-t]').forEach(el => { el.innerHTML = t(el.dataset.t); });
  document.getElementById('lang').textContent = t('lang');
  document.getElementById('summary').innerHTML = DATA.summary.map(s => `<li>${L(s)}</li>`).join('');
  document.getElementById('presets').innerHTML = DATA.presets.map(p =>
    `<button type="button" data-preset="${p}" aria-pressed="${S.preset === p}">${esc(L(DATA.presetLabel[p]))}</button>`).join('');
  document.getElementById('curs').innerHTML = ['USD','LYD'].map(c =>
    `<button type="button" data-cur="${c}" aria-pressed="${S.cur === c}">${c === 'USD' ? '$ USD' : (S.lang === 'ar' ? 'دينار ليبي' : 'LYD')}</button>`).join('');
  document.getElementById('installs').innerHTML = ['contractor','own'].map(m =>
    `<button type="button" data-install="${m}" aria-pressed="${S.install === m}">${t('install_' + m)}</button>`).join('');
  document.getElementById('presetNote').textContent = S.preset ? L(DATA.presetNote[S.preset]) : '';
  document.getElementById('approve').hidden = S.preset !== 'minimum';
  renderZones(); renderTables();
}

function renderBuilder() {
  const out = [];
  for (const [g, gl] of Object.entries(DATA.groups)) {
    out.push(`<div class="group"><h3>${esc(L(gl))}</h3>`);
    for (const it of DATA.items.filter(i => i.group === g)) {
      const s = S.sel[it.id], o = optOf(it), cost = o.qty * o.unit;
      const opts = it.options.map(x => {
        const tags = x.presets.map(p => L(DATA.presetLabel[p])).join(' · ');
        return `<option value="${x.key}" ${x.key === o.key ? 'selected' : ''}>${esc(L(x.product))}${tags ? ' — ' + esc(tags) : ''}</option>`;
      }).join('');
      out.push(`<div class="row ${s.on ? '' : 'off'}">
        <input type="checkbox" id="chk-${it.id}" data-item="${it.id}" ${s.on ? 'checked' : ''}>
        <div class="what"><label for="chk-${it.id}">${esc(L(it.what))}</label>
          <div class="chips"><span class="chip ${it.minimum ? 'ess' : ''}">${t(it.minimum ? 'essential' : 'optional')}</span><span class="chip">${esc(L(DATA.phases[it.phase]))}</span></div>
          ${L(it.skip) ? `<div class="skip">${t('if_skipped')}: ${esc(L(it.skip))}</div>` : ''}
          ${it.local ? `<div class="skip">${t('local_note')}</div>` : ''}</div>
        <div class="opt"><select id="sel-${it.id}" data-opt="${it.id}" aria-label="${esc(L(it.what))}">${opts}</select>
          ${L(o.note) ? `<div class="optnote">${esc(L(o.note))}</div>` : ''}</div>
        <div class="cost">${money(cost)}<small>${nf.format(o.qty)} × ${S.cur === 'USD' ? '$' + (o.unit < 10 ? o.unit : nf.format(o.unit)) : money(o.unit)} · ${basis(o)}</small></div></div>`);
    }
    out.push('</div>');
  }
  document.getElementById('builder').innerHTML = out.join('');
}

function renderTotals() {
  const x = totals();
  document.getElementById('total').textContent = money(x.total);
  document.getElementById('totalOther').textContent = '≈ ' + other(x.total);
  document.getElementById('breakdown').innerHTML =
    `${t('hardware')} <b>${money(x.hw)}</b> · ${t('freight')} <b>${money(x.f)}</b> · ${t('install')} <b>${money(x.i)}</b> · ${t('contingency')} <b>${money(x.c)}</b>`;
  document.getElementById('phases').innerHTML = [1,2,3].map(p => `<span class="kv">${esc(L(DATA.phases[p]))}: <b>${money(x.ph[p])}</b></span>`).join('')
;
  document.getElementById('count').innerHTML = `· ${t('items_on')}: <b>${x.n}</b>`;
  renderCaps();
}

function renderZones() {
  document.getElementById('zoneRows').innerHTML = DATA.zones.map(z => `<tr class="${S.focus && S.focus.zone === z.id ? 'sel' : ''}">
    <td class="num">${z.n}</td><td>${esc(L(z.name))}</td><td>${esc(L(DATA.crops[z.crop]))}</td><td class="num">${z.area}</td>
    <td class="num">${z.valve}</td><td class="mono">${z.valve_ll.join(', ')}</td><td class="num">${z.cable}</td>
    <td>${esc(L(z.conn))}</td><td>${z.depths.length} × ${z.depths.join(', ')} cm</td><td class="mono">${z.sensor_ll.join(', ')}</td></tr>`).join('');
}

function table(head, rows) {
  return `<table><thead><tr>${head.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}
function renderTables() {
  document.getElementById('plcTable').innerHTML = table(L(DATA.plcHead), DATA.plc.map(r => L(r)));
  document.getElementById('wiringTable').innerHTML = table(L(DATA.wiringHead), DATA.wiring.map(r => L(r)));
  document.getElementById('futureTable').innerHTML = table(L(DATA.futureHead), DATA.future.map(r => L(r)));
  document.getElementById('overrideTable').innerHTML = table(L(DATA.overrideHead), DATA.override.map(r => L(r)));
  document.getElementById('buying').innerHTML = DATA.buying.map(b => `<li>${L(b)}</li>`).join('');
  document.getElementById('survey').innerHTML = DATA.survey.map(b => `<li>${esc(L(b))}</li>`).join('');
  document.getElementById('sources').innerHTML = Object.values(DATA.sources).map(s => `<li><a href="${s[1]}" target="_blank" rel="noopener">${esc(s[0])}</a></li>`).join('');
}

function itemsAt(loc) {
  return DATA.items.filter(it => it.loc === loc && S.sel[it.id].on)
    .map(it => `<li>${esc(L(optOf(it).product))} <span class="kv">· ${money(costOf(it))}</span></li>`).join('');
}
function hereList(loc) {
  const items = itemsAt(loc);
  return `<div><b>${t('here')}</b>${items ? `<ul>${items}</ul>` : `<p class="kv">${t('nothing_here')}</p>`}</div>`;
}
function renderPanel() {
  const el = document.getElementById('panel');
  document.querySelectorAll('.map .sel').forEach(n => n.classList.remove('sel'));
  const f = S.focus;
  if (!f) {
    el.innerHTML = `<p class="lede">${t('map_hint')}</p>` + Object.values(DATA.locations).map(l =>
      `<div><b>${esc(L(l))}</b><div class="kv">${esc(l['how_' + S.lang])}</div></div>`).join('');
    return;
  }
  if (f.zone) {
    const z = DATA.zones.find(z => z.id === f.zone);
    document.querySelectorAll(`.map [data-zone="${z.id}"]`).forEach(n => n.classList.add('sel'));
    const key = f.kind === 'sensor' ? 'zones' : 'field';
    el.innerHTML = `<h3>${z.n}. ${esc(L(z.name))}</h3><dl>
      <dt>${t('crop')}</dt><dd>${esc(L(DATA.crops[z.crop]))} · ${z.area} ha</dd>
      <dt>${t('valve')}</dt><dd>${z.valve} · <span class="kv">${z.valve_ll.join(', ')}</span></dd>
      <dt>${t('cable')}</dt><dd>${z.cable} m · ${esc(L(z.conn))}</dd>
      <dt>${t('sensors')}</dt><dd>${z.depths.length} × ${z.depths.join(', ')} cm · <span class="kv">${z.sensor_ll.join(', ')}</span></dd></dl>
      <div class="kv">${esc(DATA.locations[key]['how_' + S.lang])}</div>${hereList(key)}`;
    renderZones();
    return;
  }
  const l = DATA.locations[f.loc];
  document.querySelectorAll(`.map [data-loc="${f.loc}"]`).forEach(n => n.classList.add('sel'));
  el.innerHTML = `<h3>${esc(L(l))}</h3><div class="kv">${esc(l['how_' + S.lang])}</div>${hereList(f.loc)}`;
}

function all() { renderStatic(); renderBuilder(); renderTotals(); renderPanel(); }

document.addEventListener('click', e => {
  const b = e.target.closest('[data-preset],[data-cur],[data-install],#lang,.hot');
  if (!b) return;
  if (b.dataset.preset) { applyPreset(b.dataset.preset); all(); }
  else if (b.dataset.cur) { S.cur = b.dataset.cur; save(); all(); }
  else if (b.dataset.install) { S.install = b.dataset.install; all(); }
  else if (b.id === 'lang') { S.lang = S.lang === 'ar' ? 'en' : 'ar'; save(); all(); }
  else { S.focus = b.dataset.zone ? {zone:b.dataset.zone, kind:b.dataset.kind || 'valve'} : {loc:b.dataset.loc}; renderPanel(); }
});
document.addEventListener('keydown', e => {
  const b = e.target.closest && e.target.closest('.hot');
  if (b && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); b.dispatchEvent(new MouseEvent('click', {bubbles:true})); }
});
document.addEventListener('change', e => {
  const el = e.target;
  if (el.dataset.item) S.sel[el.dataset.item].on = el.checked;
  else if (el.dataset.opt) { S.sel[el.dataset.opt].opt = el.value; S.sel[el.dataset.opt].on = true; }
  else return;
  S.preset = null;
  document.querySelectorAll('[data-preset]').forEach(b => b.setAttribute('aria-pressed', 'false'));
  document.getElementById('presetNote').textContent = '';
  document.getElementById('approve').hidden = true;
  renderBuilder(); renderTotals(); renderPanel();
  const back = document.getElementById(el.id); if (back) back.focus();
});

applyPreset('recommended');
all();
"""


def build_html(zones):
    for z in zones:
        z["conn"] = {"en": conn_text(z, "en"), "ar": conn_text(z, "ar")}
    payload = {
        "rate": D.USD_TO_LYD, "k": {"freight": D.FREIGHT_AND_PORT, "install": D.INSTALL, "installOwn": D.INSTALL_OWN, "contingency": D.CONTINGENCY},
        "presetInstall": D.PRESET_INSTALL, "override": D.OVERRIDE, "overrideHead": D.OVERRIDE_HEAD,
        "presets": list(D.PRESETS), "presetLabel": D.PRESET_LABEL, "presetNote": D.PRESET_NOTE, "phases": D.PHASES,
        "groups": D.GROUPS, "items": D.ITEMS, "locations": D.LOCATIONS, "zones": zones, "crops": D.CROP_LABEL,
        "T": D.T, "summary": D.SUMMARY, "plc": D.PLC_OPTIONS, "plcHead": D.PLC_HEAD, "wiring": D.WIRING,
        "wiringHead": D.WIRING_HEAD, "buying": D.BUYING, "survey": D.SURVEY, "future": D.FUTURE,
        "futureHead": D.FUTURE_HEAD, "sources": D.SOURCES, "caps": D.CAPS, "checks": D.CHECKS,
    }
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return f"""<title>Farm Hardware Plan</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans+Arabic:wght@400;600;700&family=IBM+Plex+Sans:wght@400;600&family=Space+Grotesk:wght@500;700&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header>
  <div class="top"><div class="eyebrow" dir="ltr">Algaroshy Farm · مزرعة الجروشي · {D.RESEARCHED_ON} · 1 USD = {D.USD_TO_LYD} LYD</div>
  <button type="button" class="btn" id="lang">English</button></div>
  <h1 data-t="title"></h1>
  <p class="lede" data-t="lede"></p>
  <div class="controls">
    <div><span data-t="start"></span><span class="seg" id="presets"></span></div>
    <div><span data-t="currency"></span><span class="seg" id="curs"></span></div>
    <div><span data-t="install_mode"></span><span class="seg" id="installs"></span></div>
  </div>
  <p class="kv" id="presetNote"></p>
</header>
<div class="bar" aria-live="polite"><div class="bar-in">
  <span class="kv" data-t="total"></span><span class="big" id="total"></span><span class="kv" id="totalOther"></span><span class="kv" id="count"></span>
</div></div>
<p class="note approve" id="approve" data-t="approve" hidden></p>
<div class="note warn" id="checks" role="status" hidden></div>
<section><h2 data-t="caps"></h2><ul class="caps" id="caps"></ul>
  <p class="kv" id="breakdown"></p><div class="phases" id="phases"></div></section>
<section><ul class="points" id="summary"></ul></section>
<section><h2 id="map-h" data-t="map"></h2>
  <div class="legend"><span><i class="sw"></i><span data-t="legend_valve"></span></span><span><i class="sw tri"></i><span data-t="legend_sensor"></span></span>
  <span><i class="sw line"></i><span data-t="legend_cable"></span></span><span><i class="sw sq"></i><span data-t="legend_bldg"></span></span></div>
  <div class="mapgrid">{map_svg(zones)}<div class="panel" id="panel" aria-live="polite"></div></div>
  <p class="note" data-t="routes_guess"></p></section>
<section><h2 data-t="items"></h2><p class="kv" data-t="price_note"></p><div id="builder" class="group"></div></section>
<section><h2 data-t="zones"></h2><p data-t="zones_note"></p>
  <div class="tablebox"><table><thead><tr><th>#</th><th data-t="zone_col"></th><th data-t="crop"></th><th data-t="area"></th><th data-t="valve"></th><th data-t="valve_ll"></th><th data-t="cable"></th><th data-t="connection"></th><th data-t="sensors"></th><th data-t="station_ll"></th></tr></thead><tbody id="zoneRows"></tbody></table></div></section>
<section><h2 data-t="override"></h2><div class="tablebox" id="overrideTable"></div></section>
<section><h2 data-t="plc"></h2><div class="tablebox" id="plcTable"></div></section>
<section><h2 data-t="wiring"></h2><div class="tablebox" id="wiringTable"></div></section>
<section><h2 data-t="buying"></h2><ul class="points" id="buying"></ul></section>
<section><h2 data-t="survey"></h2><ul class="points" id="survey"></ul></section>
<section><h2 data-t="future"></h2><div class="tablebox" id="futureTable"></div></section>
<section><h2 data-t="sources"></h2><ul class="points" id="sources"></ul></section>
<footer data-t="footer"></footer>
</div>
<script type="application/json" id="data">{blob}</script>
<script>{JS}</script>"""


def main():
    zones = zone_plan()
    (ROOT / "docs/HARDWARE_RESEARCH.md").write_text(build_md(zones, "en"), encoding="utf-8")
    (ROOT / "docs/HARDWARE_RESEARCH.ar.md").write_text(build_md(zones, "ar"), encoding="utf-8")
    out = ROOT / "tools/hardware-report/farm-hardware-plan.html"
    out.write_text(build_html(zones), encoding="utf-8")
    for p in D.PRESETS:
        x = preset_total(p)
        print(f"{p:12s} hardware ${x['hardware']:>9,.0f}  total ${x['total']:>9,.0f}  {x['total'] * D.USD_TO_LYD:>11,.0f} LYD")


if __name__ == "__main__":
    main()
