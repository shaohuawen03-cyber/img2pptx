#!/usr/bin/env python3
"""Blind reconstruction of fig1_graphical_abstract.png (P. gingivalis -> AD).

Composition model (from programmatic analysis only):
- raster "cards"/motifs: complex biological illustrations (crop + inpaint text)
- vector <text>: all OCR-recovered labels (color sampled from source pixels)
- vector arrows: medial-axis traces of residual ink between modules
- vector chart: RMSD line chart (axes, ticks, traced navy curve)
- vector frame: bottom methods strip (navy border + pale dividers)
"""
from __future__ import annotations

import base64
import io
import json
import re

import cv2
import numpy as np
import potrace
from PIL import Image
from skimage.morphology import medial_axis

SRC = "fig1.png"
W, H = 1619, 971
ocr = json.load(open("ocr.json"))
img = np.asarray(Image.open(SRC).convert("RGB"))
bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

# ---------------------------------------------------------------- regions
CARDS = [
    ("card_pg_bacterium", 14, 58, 336, 644),
    ("card_bloodstream", 595, 158, 292, 502),
    ("card_ab_structure", 1258, 370, 348, 302),
]
MOTIFS = [
    ("motif_gingipains", 300, 226, 236, 266),
    ("motif_omv_dots", 336, 476, 188, 126),
    ("motif_brainhead", 868, 128, 262, 252),
    ("motif_pale_corridor", 1038, 193, 192, 377),
    ("motif_neuron", 1383, 23, 212, 102),
    ("motif_plaques", 1433, 83, 177, 207),
    ("motif_tau", 1463, 193, 127, 97),
    ("motif_tau_frag", 1463, 293, 147, 127),
    ("motif_blue_icon", 1323, 138, 94, 94),
    ("motif_icon_geo", 48, 726, 94, 132),
    ("motif_heatmap", 148, 733, 234, 182),
    ("motif_docking", 523, 743, 239, 162),
    ("motif_md_model", 863, 748, 114, 142),
    ("motif_protein_br", 1343, 693, 264, 226),
]
FRAME = {"x0": 15, "y0": 687, "x1": 1605, "y1": 941,
         "stroke": "#1C4065", "width": 2.6, "dividers": [451, 840],
         "divider_stroke": "#A0AEB9", "divider_width": 1.6}
CHART = {
    "axis_x": 1056, "axis_y": 879.5,        # pixel position of (0, 0)
    "px_per_unit_x": 266.5, "px_per_unit_y": 271.25,
    "x_ticks": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    "y_ticks": [0.0, 0.1, 0.2, 0.3, 0.4],
    "tick_font": 20, "label_font": 26,
    "x_title": "Time (\u03bcs)",            # low-confidence OCR, flagged in manifest
    "y_title": "RMSD (nm)",
    "curve_color": "#003078",
}

TEXT_OVERRIDES = {
    "P. gingivalis": {"italic": True, "bold": True},
    "(srl) aw": {"drop": True},             # replaced by chart x-title
    "3 20": {"drop": True},                 # replaced by explicit y ticks
    "0.4-": {"drop": True},
    # bare tick numbers are owned by the chart module (axes + ticks drawn there)
    "0.0": {"drop": True}, "0.2": {"drop": True}, "0.4": {"drop": True},
    "0.6": {"drop": True}, "0.8": {"drop": True}, "1.0": {"drop": True},
    "0.1": {"drop": True}, "0.3": {"drop": True},
    "RMSD (nm)": {"drop": True},            # drawn rotated by chart module
}


def text_key(t):
    return t["text"].strip()


# ---------------------------------------------------------------- helpers
def dominant_dark_color(x0, y0, x1, y1):
    box = img[max(0, y0):y1, max(0, x0):x1].reshape(-1, 3).astype(int)
    lum = box.mean(1)
    dark = box[lum < max(60, np.quantile(lum, 0.25))]
    if len(dark) < 8:
        dark = box
    c = np.median(dark, 0).astype(int)
    return "#{:02X}{:02X}{:02X}".format(*c)


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def crop_module(name, x, y, w, h, text_boxes):
    """Crop region and inpaint overlapping text so crops stay text-free."""
    region = bgr[max(0, y):y + h, max(0, x):x + w].copy()
    mask = np.zeros(region.shape[:2], np.uint8)
    for t in text_boxes:
        tx0, ty0, tx1, ty1 = t["x0"] - x, t["y0"] - y, t["x1"] - x, t["y1"] - y
        if tx1 < 0 or ty1 < 0 or tx0 >= region.shape[1] or ty0 >= region.shape[0]:
            continue
        cv2.rectangle(mask, (max(0, tx0 - 2), max(0, ty0 - 2)),
                      (min(region.shape[1] - 1, tx1 + 2),
                       min(region.shape[0] - 1, ty1 + 2)), 255, -1)
    if mask.any():
        region = cv2.inpaint(region, mask, 4, cv2.INPAINT_TELEA)
    clean = cv2.cvtColor(region, cv2.COLOR_BGR2RGB)
    buf = io.BytesIO()
    Image.fromarray(clean).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _trace_mask_to_d(mask2x):
    """potrace a 2x-upscaled binary mask -> SVG path data (2x coords).

    potracer's Bitmap inverts its bool input internally, so pass ~ink to
    have the ink region traced.
    """
    bm = potrace.Bitmap(~(mask2x > 127))
    try:
        pl = bm.trace(turdsize=16, alphamax=1.0, opttolerance=0.4)
    except Exception:
        return None
    parts = []
    for curve in pl:
        start = curve.start_point
        segs = "M {:.1f} {:.1f}".format(start.x, start.y)
        for seg in curve:
            if seg.is_corner:
                segs += " L {:.1f} {:.1f} L {:.1f} {:.1f}".format(
                    seg.c.x, seg.c.y, seg.end_point.x, seg.end_point.y)
            else:
                segs += " C {:.1f} {:.1f} {:.1f} {:.1f} {:.1f} {:.1f}".format(
                    seg.c1.x, seg.c1.y, seg.c2.x, seg.c2.y,
                    seg.end_point.x, seg.end_point.y)
        parts.append(segs + " Z")
    return " ".join(parts) if parts else None


def vectorize_module(name, x, y, w, h, text_boxes):
    """Region -> inpaint text -> k-means quantize -> per-color potrace paths.

    Returns (svg_group_body, stats). Coordinates: traced at 2x, mapped back
    via transform="translate(x,y) scale(0.5)".
    """
    region = bgr[max(0, y):y + h, max(0, x):x + w].copy()
    mask = np.zeros(region.shape[:2], np.uint8)
    for t in text_boxes:
        tx0, ty0, tx1, ty1 = t["x0"] - x, t["y0"] - y, t["x1"] - x, t["y1"] - y
        if tx1 < 0 or ty1 < 0 or tx0 >= region.shape[1] or ty0 >= region.shape[0]:
            continue
        cv2.rectangle(mask, (max(0, tx0 - 2), max(0, ty0 - 2)),
                      (min(region.shape[1] - 1, tx1 + 2),
                       min(region.shape[0] - 1, ty1 + 2)), 255, -1)
    if mask.any():
        region = cv2.inpaint(region, mask, 4, cv2.INPAINT_TELEA)
    rgb = cv2.cvtColor(region, cv2.COLOR_BGR2RGB)
    med = cv2.medianBlur(rgb, 5)
    K = 14 if w * h > 80000 else 10
    data = med.reshape(-1, 3).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, label, center = cv2.kmeans(data, K, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    label_img = label.reshape(med.shape[:2])
    fracs = [(int((label_img == i).sum()), i) for i in range(K)]
    fracs.sort(reverse=True)
    total = med.shape[0] * med.shape[1]
    body, stats = [], []
    for area, i in fracs:
        frac = area / total
        if frac > 0.985 or frac < 0.0005:
            continue
        if float(center[i].mean()) > 241:   # near-white: page bg is white
            continue
        m = (label_img == i).astype(np.uint8) * 255
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        m2 = cv2.resize(m, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
        m2 = cv2.medianBlur(m2, 3)
        d = _trace_mask_to_d(m2)
        if not d:
            continue
        col = "#%02X%02X%02X" % tuple(int(round(v)) for v in center[i])
        body.append(f'<path fill="{col}" fill-rule="evenodd" d="{d}"/>')
        stats.append({"color": col, "frac": round(frac, 4)})
    inner = "".join(body)
    group_body = (f'<g id="{name}_shapes" '
                  f'transform="translate({x} {y}) scale(0.5)">{inner}</g>')
    return group_body, {"n_colors": len(stats), "colors": stats}


# ---------------------------------------------------------------- arrows
def trace_arrows(exclude_rects, text_boxes):
    """Residual ink -> skeleton -> polylines + arrowheads."""
    g = img.mean(2).astype(np.uint8)
    ink = (g < 228).astype(np.uint8) * 255
    mask = np.zeros((H, W), np.uint8)
    for t in text_boxes:
        cv2.rectangle(mask, (t["x0"] - 3, t["y0"] - 3),
                      (t["x1"] + 3, t["y1"] + 3), 255, -1)
    for x, y, w, h in exclude_rects:
        cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)
    ink[mask > 0] = 0
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    arrows = []
    for i in range(1, n):
        x, y, w, h, area = [int(v) for v in stats[i]]
        if area < 260 or area > 20000:
            continue
        comp = (lab == i)
        if w * h < 1.5 * area:      # blob-like, not a stroke
            continue
        dt = cv2.distanceTransform(comp.astype(np.uint8), cv2.DIST_L2, 5)
        widths = dt[dt > 0]
        if len(widths) == 0:
            continue
        med_w = float(np.median(widths))
        skel = medial_axis(comp)
        ys, xs = np.where(skel)
        if len(xs) < 30:
            continue
        pts = set(zip(xs.tolist(), ys.tolist()))

        def neighbors(p):
            x, y = p
            return [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                    if (dx or dy) and (x + dx, y + dy) in pts]

        ends = [p for p in pts if len(neighbors(p)) == 1]
        used = set()
        paths = []
        for _ in range(3):
            cand = [p for p in ends if p not in used]
            if not cand:
                cand = list(pts)[:1]
            start = cand[0]
            dist = {start: 0}
            prev = {}
            stack = [start]
            order = [start]
            while stack:
                cur = stack.pop()
                for nb in neighbors(cur):
                    if nb not in dist:
                        dist[nb] = dist[cur] + 1
                        prev[nb] = cur
                        stack.append(nb)
                        order.append(nb)
            far = max(order, key=lambda p: dist[p])
            path = [far]
            while path[-1] != start:
                path.append(prev[path[-1]])
            if len(path) < 35:
                break
            paths.append(path[::-1])
            used |= set(path)
            skel_pts = set(path)
            ends = [p for p in skel_pts if len(neighbors(p)) == 1]
        col = img[comp].mean(0).astype(int)
        color = "#{:02X}{:02X}{:02X}".format(*col)
        for path in paths:
            simp = path[::6]
            if len(simp) < 3:
                continue
            heads = []
            for endpt in (simp[0], simp[-1]):
                lw = 2 * dt[endpt[1], endpt[0]]
                heads.append((lw, endpt))
            lw_max, e_max = max(heads)
            d = "M " + " L ".join(f"{x} {y}" for x, y in simp)
            arrows.append({
                "path": d, "color": color, "width": round(max(1.6, med_w * 2), 1),
                "head": (e_max if lw_max > 1.7 * med_w * 2 else None),
                "head_size": round(lw_max * 1.15, 1) if lw_max > 1.7 * med_w * 2 else 0,
                "bbox": [x, y, w, h],
            })
    return arrows


def arrow_svg(ar):
    out = [f'<path d="{ar["path"]}" fill="none" stroke="{ar["color"]}" '
           f'stroke-width="{ar["width"]}" stroke-linecap="round" '
           f'stroke-linejoin="round"/>']
    if ar["head"]:
        hx, hy = ar["head"]
        s = ar["head_size"]
        out.append(f'<circle cx="{hx}" cy="{hy}" r="{s / 2:.1f}" '
                   f'fill="{ar["color"]}"/>')
    return "".join(out)


# ---------------------------------------------------------------- chart
def trace_curve():
    box = img.astype(int)[758:888, 1050:1350]
    r, g, b = box[:, :, 0], box[:, :, 1], box[:, :, 2]
    navy = (b > r + 25) & (b > 70) & (r < 150) & (b > g + 15)
    pts = []
    for x in range(box.shape[1]):
        ys = np.where(navy[:, x])[0]
        if len(ys):
            pts.append((x + 1050, float(np.median(ys)) + 758))
    simp = pts[::3]
    return simp


def chart_svg():
    c = CHART
    el = []
    el.append(f'<line x1="{c["axis_x"]}" y1="{c["axis_y"]}" x2="1330" '
              f'y2="{c["axis_y"]}" stroke="#333" stroke-width="2.0"/>')
    el.append(f'<line x1="{c["axis_x"]}" y1="{c["axis_y"]}" x2="{c["axis_x"]}" '
              f'y2="765" stroke="#333" stroke-width="2.0"/>')
    for tv in c["x_ticks"]:
        px = c["axis_x"] + tv * c["px_per_unit_x"]
        el.append(f'<line x1="{px:.1f}" y1="{c["axis_y"]}" x2="{px:.1f}" '
                  f'y2="{c["axis_y"] + 7}" stroke="#333" stroke-width="1.6"/>')
        el.append(f'<text x="{px:.1f}" y="{c["axis_y"] + 22}" font-size="{c["tick_font"]}" '
                  f'text-anchor="middle" fill="#222">{tv:.1f}</text>')
    for tv in c["y_ticks"]:
        py = c["axis_y"] - tv * c["px_per_unit_y"]
        el.append(f'<line x1="{c["axis_x"] - 7}" y1="{py:.1f}" x2="{c["axis_x"]}" '
                  f'y2="{py:.1f}" stroke="#333" stroke-width="1.6"/>')
        el.append(f'<text x="{c["axis_x"] - 9}" y="{py + 5:.1f}" font-size="{c["tick_font"]}" '
                  f'text-anchor="end" fill="#222">{tv:.1f}</text>')
    el.append(f'<text x="{c["axis_x"] + 137}" y="{c["axis_y"] + 44}" '
              f'font-size="{c["label_font"]}" text-anchor="middle" fill="#222">'
              f'{esc(c["x_title"])}</text>')
    cx, cy = 1006, (765 + c["axis_y"]) / 2
    el.append(f'<text x="{cx}" y="{cy}" font-size="{c["label_font"] - 2}" '
              f'text-anchor="middle" fill="#222" '
              f'transform="rotate(-90 {cx} {cy})">{esc(c["y_title"])}</text>')
    pts = trace_curve()
    d = "M " + " L ".join(f"{x:.0f} {y:.0f}" for x, y in pts)
    el.append(f'<path d="{d}" fill="none" stroke="{c["curve_color"]}" '
              f'stroke-width="7.5" stroke-linejoin="round" stroke-linecap="round"/>')
    return "".join(el), pts


# ---------------------------------------------------------------- main build
def build():
    parts = []
    manifest = {
        "task": "img2pptx blind reconstruction of fig1_graphical_abstract.png",
        "normalized_input": {"file": SRC, "width": W, "height": H,
                             "aspect": round(W / H, 4)},
        "components": [], "raster_crops": [], "vector_regions": [],
        "low_confidence_items": [],
    }
    comps = manifest["components"]

    def comp(id_, label, level, bbox, role, export=True, notes="", **kw):
        entry = {"id": id_, "label": label, "level": level, "bbox": bbox,
                 "semantic_role": role, "export": export, "notes": notes}
        entry.update(kw)
        comps.append(entry)

    # ---- frame (vector)
    f = FRAME
    frame_el = [
        f'<rect x="{f["x0"]}" y="{f["y0"]}" width="{f["x1"]-f["x0"]}" '
        f'height="{f["y1"]-f["y0"]}" rx="10" fill="none" '
        f'stroke="{f["stroke"]}" stroke-width="{f["width"]}"/>']
    for dx in f["dividers"]:
        frame_el.append(f'<line x1="{dx}" y1="{f["y0"]+6}" x2="{dx}" '
                        f'y2="{f["y1"]-6}" stroke="{f["divider_stroke"]}" '
                        f'stroke-width="{f["divider_width"]}"/>')
    parts.append(('<g id=\"methods_strip_frame\">', "".join(frame_el), "</g>"))
    comp("methods_strip_frame", "Methods strip frame (3 cells)",
         "semantic-unit", [f["x0"], f["y0"], f["x1"], f["y1"]],
         "containers: transcriptomics | docking | MD simulation",
         representation="svg-shapes",
         source_observations=["dark navy border rgb(28,64,101) at y=687, x=15",
                              "pale dividers at x=451, x=840"])

    # ---- vectorized cards + motifs (k-means color quantization + potrace)
    text_boxes = ocr
    vstats = {}
    for name, x, y, w, h in CARDS + MOTIFS:
        gbody, st = vectorize_module(name, x, y, w, h, text_boxes)
        parts.append((f'<g id="{name}">', gbody, "</g>"))
        vstats[name] = st
        manifest["vector_regions"].append({
            "id": name, "bbox": [x, y, w, h],
            "n_colors": st["n_colors"],
            "render_strategy": "kmeans-quantize + potrace bezier trace",
        })
        comp(name, name.replace("_", " "), "semantic-unit" if name in
             [c[0] for c in CARDS] else "combination-submodule",
             [x, y, x + w, y + h], "illustration module",
             representation="svg-shapes",
             n_colors=st["n_colors"])

    # ---- arrows
    exclude = [(x, y, w, h) for _, x, y, w, h in CARDS + MOTIFS]
    exclude += [(FRAME["x0"], FRAME["y0"] - 2, FRAME["x1"] - FRAME["x0"], 6),
                (FRAME["x0"], FRAME["y1"] - 2, FRAME["x1"] - FRAME["x0"], 6),
                (FRAME["x0"] - 2, FRAME["y0"], 6, FRAME["y1"] - FRAME["y0"]),
                (985, 750, 375, 195)]
    arrows = trace_arrows(exclude, text_boxes)
    a_el = [arrow_svg(a) for a in arrows]
    parts.append(('<g id="flow_connectors">', "".join(a_el), "</g>"))
    comp("flow_connectors", "Flow connectors (traced arrows)", "semantic-unit",
         [min(a["bbox"][0] for a in arrows), min(a["bbox"][1] for a in arrows),
          max(a["bbox"][0] + a["bbox"][2] for a in arrows),
          max(a["bbox"][1] + a["bbox"][3] for a in arrows)] if arrows else [0, 0, 0, 0],
         "causal flow: bacterium -> bloodstream -> BBB -> brain",
         representation="svg-paths", n_arrows=len(arrows),
         source_observations=["no straight Hough lines: arrows are curved",
                              "traced via medial axis of residual ink"])

    # ---- chart
    chart_el, curve_pts = chart_svg()
    parts.append(('<g id="chart_rmsd">', chart_el, "</g>"))
    comp("chart_rmsd", "RMSD line chart (1 microsecond MD)", "semantic-unit",
         [985, 750, 1360, 945], "MD convergence evidence",
         representation="svg-chart",
         source_observations=[
             "L-shaped axes at x=1056, y=879.5",
             "x ticks 0.0-1.0 step 0.2; y ticks 0.0-0.4 step 0.1",
             "single navy trace ~7px thick, x 1057-1322, y 790-874"],
         visual_invariants=[
             "ticks strictly ascending", "curve stays inside axes",
             "curve single-valued in x"])

    # ---- texts
    t_el = []
    for t in sorted(ocr, key=lambda t: (t["y0"], t["x0"])):
        key = text_key(t)
        ov = TEXT_OVERRIDES.get(key, {})
        if ov.get("drop"):
            continue
        cx = (t["x0"] + t["x1"]) / 2
        by = t["y1"] - 0.14 * (t["y1"] - t["y0"])
        size = max(13, round((t["y1"] - t["y0"]) * 1.04))
        color = dominant_dark_color(t["x0"], t["y0"], t["x1"], t["y1"])
        fam = "Arial,Carlito,sans-serif"
        style = 'font-style="italic" ' if ov.get("italic") else ""
        bold_src = (t["y1"] - t["y0"]) >= 22
        weight = 'font-weight="bold" ' if (ov.get("bold") or bold_src) else ""
        vert = (t["x1"] - t["x0"]) < 0.55 * (t["y1"] - t["y0"]) and len(key) > 4
        if vert:
            cy = (t["y0"] + t["y1"]) / 2
            t_el.append(f'<text x="{cx:.0f}" y="{cy:.0f}" font-size="{size}" '
                        f'font-family="{fam}" fill="{color}" text-anchor="middle" '
                        f'{style}{weight}transform="rotate(-90 {cx:.0f} {cy:.0f})">'
                        f'{esc(key)}</text>')
        else:
            t_el.append(f'<text x="{cx:.0f}" y="{by:.0f}" font-size="{size}" '
                        f'font-family="{fam}" fill="{color}" '
                        f'text-anchor="middle" {style}{weight}>{esc(key)}</text>')
        comp(f"text_{abs(hash(key)) % 10**8}", f"label: {key!r}",
             "atomic-element",
             [t["x0"], t["y0"], t["x1"], t["y1"]], "editable text",
             representation="svg-text", export=False,
             source_observations=[f"OCR conf {t['conf']}"])
        if t["conf"] < 0.8:
            manifest["low_confidence_items"].append(
                {"text": key, "conf": t["conf"], "bbox":
                 [t["x0"], t["y0"], t["x1"], t["y1"]]})
    parts.append(('<g id="labels">', "".join(t_el), "</g>"))
    comp("labels", "All text labels (OCR-recovered)", "semantic-unit",
         [0, 0, W, H], "editable text layer", representation="svg-text",
         export=False, n_texts=len(t_el))

    manifest["low_confidence_items"].append({
        "item": "chart x-axis title", "rendered": CHART["x_title"],
        "reason": "source OCR garbled ('(srl) aw', conf 0.72); inferred from "
                  "'1 microsecond MD simulation' context",
        "status": "needs-human-review"})

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" '
           f'height="{H}" viewBox="0 0 {W} {H}">',
           f'<rect id="page_background" width="{W}" height="{H}" fill="#FFFFFF"/>']
    for open_tag, body, close_tag in parts:
        svg += [open_tag, body, close_tag]
    svg.append("</svg>")
    out = "\n".join(svg)
    open("full.svg", "w").write(out)
    json.dump(manifest, open("component_manifest.json", "w"),
              ensure_ascii=False, indent=1)
    n_paths = out.count("<path")
    print(f"full.svg written ({len(out)} bytes); arrows={len(arrows)}; "
          f"curve pts={len(curve_pts)}; texts={len(t_el)}; "
          f"vector shapes={n_paths - len(arrows) - 1}; "
          f"colors={sum(v['n_colors'] for v in vstats.values())}")


if __name__ == "__main__":
    build()
