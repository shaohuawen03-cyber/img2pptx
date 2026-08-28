#!/usr/bin/env python3
"""QA suite for the fig1 graphical abstract reconstruction (task2)."""
import json
import os
import re
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw, ImageFont

os.makedirs("qa", exist_ok=True)
os.makedirs("qa/semantic_masks", exist_ok=True)

W, H = 1619, 971
manifest = json.load(open("component_manifest.json"))
src = np.asarray(Image.open("fig1.png").convert("RGB"), float)
report = {}

NS = "{http://www.w3.org/2000/svg}"
tree = ET.parse("full.svg")
root = tree.getroot()
groups = {g.get("id"): g for g in root.iter(NS + "g")}
texts_all = [t for g in groups.values() for t in g.iter(NS + "text")]

# ============================================================ 1 skeleton
sk = {"checks": [], "passed": True}
FRAME = {"x0": 15, "y0": 687, "x1": 1605, "y1": 941, "dividers": [451, 840]}
frame_rects = [r for r in groups.get("methods_strip_frame", [])
               if r.tag == NS + "rect"]
ok = bool(frame_rects)
if ok:
    r = frame_rects[0]
    ok = (abs(float(r.get("x")) - FRAME["x0"]) < 2 and
          abs(float(r.get("y")) - FRAME["y0"]) < 2 and
          abs(float(r.get("width")) - (FRAME["x1"] - FRAME["x0"])) < 3 and
          abs(float(r.get("height")) - (FRAME["y1"] - FRAME["y0"])) < 3)
sk["checks"].append({"check": "methods_frame_geometry", "passed": bool(ok)})
sk["passed"] &= bool(ok)
lines = [l for l in groups.get("methods_strip_frame", []) if l.tag == NS + "line"]
divs = sorted(float(l.get("x1")) for l in lines if l.get("x1") == l.get("x2"))
ok = len(divs) == 2 and abs(divs[0] - 451) < 3 and abs(divs[1] - 840) < 3
sk["checks"].append({"check": "three_method_cells_dividers", "dividers": divs,
                     "passed": bool(ok)})
sk["passed"] &= bool(ok)
ch = groups.get("chart_rmsd")
ch_lines = [l for l in ch if l.tag == NS + "line"]
ax_x = [l for l in ch_lines if abs(float(l.get("x1")) - float(l.get("x2"))) < 0.5]
ax_y = [l for l in ch_lines if abs(float(l.get("y1")) - float(l.get("y2"))) < 0.5]
ok = any(abs(float(l.get("x1")) - 1056) < 2 for l in ax_x) and \
     any(abs(float(l.get("y1")) - 879.5) < 2 for l in ax_y)
sk["checks"].append({"check": "chart_axes_at_detected_pixel_positions",
                     "passed": bool(ok)})
sk["passed"] &= bool(ok)
json.dump(sk, open("qa/layout_skeleton_audit.json", "w"), indent=1)
report["layout_skeleton"] = sk["passed"]

# ============================================================ 2 modules
import sys
sys.path.insert(0, "../task")
from render_svg import render  # noqa: E402

os.makedirs("modules", exist_ok=True)
cz = (985, 745, 1340, 948)   # chart pure-vector zone (axis box + titles)
MODZONES = {
    "chart_rmsd": cz,
    "methods_strip_frame": (10, 682, 1610, 946),
    "labels": (0, 0, W, H),
}
# flow_connectors zone derived from its traced paths (ink bbox + pad)
_fc = [p for p in groups.get("flow_connectors", []) if p.tag == NS + "path"]
if _fc:
    _xs, _ys = [], []
    for p in _fc:
        for _a, _b in re.findall(r"(-?[\d.]+) (-?[\d.]+)", p.get("d")):
            _xs.append(float(_a)); _ys.append(float(_b))
    if _xs:
        MODZONES["flow_connectors"] = (max(0, min(_xs) - 8), max(0, min(_ys) - 8),
                                       min(W, max(_xs) + 8), min(H, max(_ys) + 8))
sa = {"modules": [], "passed": True}
for gid, (x0, y0, x1, y1) in MODZONES.items():
    if gid not in groups:
        sa["modules"].append({"id": gid, "passed": False, "issue": "missing"})
        sa["passed"] = False
        continue
    m = ET.Element(NS + "svg", {
        "width": str(x1 - x0), "height": str(y1 - y0),
        "viewBox": f"{x0} {y0} {x1-x0} {y1-y0}"})
    ET.SubElement(m, NS + "rect", {"x": str(x0), "y": str(y0),
                                   "width": str(x1 - x0), "height": str(y1 - y0),
                                   "fill": "#FFFFFF", "id": "module_background"})
    m.append(groups[gid])
    f = f"modules/{gid}.svg"
    open(f, "w").write('<?xml version="1.0"?>\n' + ET.tostring(m, encoding="unicode"))
    im = render(f, f.replace(".svg", ".png"))
    a = np.asarray(im.convert("L"))
    ink = (a < 242)
    ys_, xs_ = np.where(ink)
    if not ink.any():
        print(f"[debug] module {gid} rendered EMPTY; svg head:",
              open(f).read()[:200].replace("\n", " "))
        margin = -1
    else:
        margin = min(xs_.min(), ys_.min(), im.width - xs_.max(), im.height - ys_.max())
    ok = ink.any() and margin >= 2
    sa["modules"].append({"id": gid, "margin_px": int(margin), "passed": bool(ok)})
    sa["passed"] &= bool(ok)
cards = [c for c in manifest["raster_crops"] if c["id"].startswith("card_")]
for c in cards:
    x, y, w, h = c["bbox"]
    m = ET.Element(NS + "svg", {"width": str(w), "height": str(h),
                                "viewBox": f"{x} {y} {w} {h}"})
    ET.SubElement(m, NS + "rect", {"x": str(x), "y": str(y), "width": str(w),
                                   "height": str(h), "fill": "#FFFFFF"})
    m.append(groups[c["id"]])
    f = f"modules/{c['id']}.svg"
    open(f, "w").write('<?xml version="1.0"?>\n' + ET.tostring(m, encoding="unicode"))
    im = render(f, f.replace(".svg", ".png"))
    ok = im.size == (w, h)
    sa["modules"].append({"id": c["id"], "size": list(im.size), "passed": bool(ok)})
    sa["passed"] &= bool(ok)
json.dump(sa, open("qa/standalone_integrity_audit.json", "w"), indent=1)
report["standalone_integrity"] = sa["passed"]

# ============================================================ 3 containment
ca = {"checks": [], "passed": True}
ok = True
for c in manifest["raster_crops"]:
    x, y, w, h = c["bbox"]
    ok &= x >= -4 and y >= -4 and x + w <= W + 4 and y + h <= H + 4
ca["checks"].append({"check": "crops_inside_canvas", "passed": bool(ok)})
ca["passed"] &= bool(ok)
rects = [c["bbox"] for c in manifest["raster_crops"] if c["id"].startswith("card_")]
ov = []
for i, a_ in enumerate(rects):
    for b_ in rects[i + 1:]:
        x_o = max(0, min(a_[0] + a_[2], b_[0] + b_[2]) - max(a_[0], b_[0]))
        y_o = max(0, min(a_[1] + a_[3], b_[1] + b_[3]) - max(a_[1], b_[1]))
        if x_o > 4 and y_o > 4:
            ov.append([a_, b_])
ok = not ov
ca["checks"].append({"check": "cards_mutually_exclusive", "violations": ov,
                     "passed": bool(ok)})
ca["passed"] &= bool(ok)
bad = []
for c in manifest["raster_crops"]:
    x, y, w, h = c["bbox"]
    if not (x + w < cz[0] or y + h < cz[1] or x > cz[2] or y > cz[3]):
        bad.append(c["id"])
ok = not bad
ca["checks"].append({"check": "chart_zone_pure_vector", "violations": bad,
                     "passed": bool(ok)})
ca["passed"] &= bool(ok)
json.dump(ca, open("qa/containment_audit.json", "w"), indent=1)
report["containment"] = ca["passed"]

# ============================================================ 4 alignment
al = {"checks": [], "passed": True}
bad = []
for t in texts_all:
    x = float(t.get("x"))
    y = float(t.get("y"))
    for dx in FRAME["dividers"]:
        if abs(x - dx) < 4 and FRAME["y0"] + 8 < y < FRAME["y1"] - 8:
            bad.append((t.text, "divider", dx))
ok = not bad
al["checks"].append({"check": "no_text_on_divider_lines", "violations": bad[:5],
                     "passed": bool(ok)})
al["passed"] &= bool(ok)
xt = sorted([float(t.get("x")) for t in texts_all
             if t.text in ("0.0", "0.2", "0.4", "0.6", "0.8", "1.0")
             and float(t.get("y", 0)) > 890])
gaps = [round(b - a, 1) for a, b in zip(xt, xt[1:])]
ok = len(xt) == 6 and max(gaps) - min(gaps) < 2.5
al["checks"].append({"check": "chart_x_ticks_evenly_spaced", "gaps": gaps,
                     "passed": bool(ok)})
al["passed"] &= bool(ok)
yt = sorted([float(t.get("y")) for t in texts_all
             if t.text in ("0.0", "0.1", "0.2", "0.3", "0.4")
             and float(t.get("x", 999)) < 1056], reverse=True)
ygaps = [round(a - b, 1) for a, b in zip(yt, yt[1:])]
ok = len(yt) == 5 and max(ygaps) - min(ygaps) < 2.5
al["checks"].append({"check": "chart_y_ticks_evenly_spaced", "gaps": ygaps,
                     "passed": bool(ok)})
al["passed"] &= bool(ok)
json.dump(al, open("qa/alignment_audit.json", "w"), indent=1)
report["alignment_spacing"] = al["passed"]

# ============================================================ 5 border layering
bl = {"containers": [], "passed": True}
fr = groups.get("methods_strip_frame")
rects_f = [r for r in fr if r.tag == NS + "rect"]
ok = len(rects_f) == 1 and rects_f[0].get("fill") == "none" and \
    rects_f[0].get("stroke") not in (None, "none")
bl["containers"].append({"id": "methods_strip_frame",
                         "fill_none_outline_only": bool(ok),
                         "stroke_width": rects_f[0].get("stroke-width"),
                         "is_only_rect": True, "passed": bool(ok)})
bl["passed"] &= bool(ok)
json.dump(bl, open("qa/border_layering_audit.json", "w"), indent=1)
report["border_layering"] = bl["passed"]

# ============================================================ 6 semantic
sc = {"constraints": [], "passed": True}


def add(cid, desc, ok, evidence, severity="hard"):
    sc["constraints"].append({"id": cid, "description": desc,
                              "passed": bool(ok), "severity": severity,
                              "evidence": evidence})
    if severity == "hard":
        sc["passed"] &= bool(ok)


from rapidocr_onnxruntime import RapidOCR  # noqa: E402
ocr_engine = RapidOCR()
res, _ = ocr_engine("full_render.png")
render_texts = set()
if res:
    for _, txt, conf in res:
        norm = re.sub(r"[^a-z0-9]", "", txt.lower())
        if norm:
            render_texts.add(norm)
src_norm = []
for t in json.load(open("ocr.json")):
    norm = re.sub(r"[^a-z0-9]", "", t["text"].lower())
    if norm:
        src_norm.append(norm)
hits = sum(1 for n in src_norm if n in render_texts)
rate = hits / max(1, len(src_norm))
add("ocr_roundtrip", "OCR of the render re-detects >=70% of source strings "
    "(font substitution tolerance)", rate >= 0.70,
    {"hits": hits, "total": len(src_norm), "rate": round(rate, 3)})

curve = [p for p in groups["chart_rmsd"] if p.tag == NS + "path"][-1]
d = curve.get("d")
pts = [(float(a), float(b)) for a, b in re.findall(r"(-?[\d.]+) (-?[\d.]+)", d)]
xs = [p[0] for p in pts]
ys = [p[1] for p in pts]
ok = all(b > a for a, b in zip(xs, xs[1:])) and min(ys) >= 760 and max(ys) <= 880
add("curve_single_valued_inside_axes",
    "RMSD curve is single-valued in x and stays within the y-axis box",
    ok, {"n_pts": len(pts), "y_range": [min(ys), max(ys)],
         "x_range": [min(xs), max(xs)]})
data_y = [(879.5 - y) / 271.25 for y in ys]
ok = min(data_y) >= -0.02 and max(data_y) <= 0.46
add("curve_values_within_plotted_range",
    "Curve values within [0, 0.45] nm", ok,
    {"min_nm": round(min(data_y), 3), "max_nm": round(max(data_y), 3)})
ok = curve.get("stroke", "").upper() == "#003078"
add("curve_navy_color", "Curve uses the source navy color", ok,
    {"stroke": curve.get("stroke")})
tick_texts = [t.text for t in texts_all]
ok = all(v in tick_texts for v in ("0.0", "0.2", "0.4", "0.6", "0.8", "1.0",
                                   "0.1", "0.3"))
add("chart_tick_labels_complete",
    "Tick labels 0.0-1.0 (x, step .2) and 0.0-0.4 (y, step .1) all present",
    ok, {"found": sorted(set(t for t in tick_texts if re.fullmatch(r"0\.\d", t)))})

ok = rects_f[0].get("stroke", "").upper() == "#1C4065"
add("frame_navy_stroke", "Methods frame uses detected navy stroke", ok,
    {"stroke": rects_f[0].get("stroke")})
paths = [p for p in groups["flow_connectors"] if p.tag == NS + "path"]
ok = len(paths) >= 20 and all(p.get("stroke") not in (None, "none") for p in paths)
add("flow_connectors_traced",
    "At least 20 connector strokes traced from residual ink", ok,
    {"n_paths": len(paths)})

pg = [t for t in texts_all if t.text and "gingivalis" in t.text]
ok = bool(pg) and pg[0].get("font-style") == "italic"
add("species_name_italic", "P. gingivalis rendered in italic (nomenclature)",
    ok, {"style": pg[0].get("font-style") if pg else None})

ok = len(texts_all) >= 27
add("text_layer_present", "Editable text layer with >=27 labels", ok,
    {"n_texts": len(texts_all)})

imgs = [i for i in root.iter(NS + "image")]
ok = all((i.get("href") or "").startswith("data:image/png;base64,") for i in imgs)
add("crops_self_contained", "All raster crops are inline data URIs", ok,
    {"n_images": len(imgs)})


def save_mask(name, boxes):
    im_ = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(im_)
    for b in boxes:
        dr.rectangle(list(b), fill=255)
    im_.save(f"qa/semantic_masks/{name}.png")


save_mask("chart", [cz])
save_mask("methods_strip", [[FRAME["x0"], FRAME["y0"], FRAME["x1"], FRAME["y1"]]])
save_mask("flow_column", [[595, 158, 887, 660]])
save_mask("bacterium_card", [[14, 58, 350, 702]])

coverage = {"hard_constraints": [
    {"constraint": c["id"], "audit_executed": True, "passed": c["passed"],
     "evidence": c["evidence"]} for c in sc["constraints"]],
    "passed": all(c["passed"] for c in sc["constraints"] if c["severity"] == "hard")}
sc["human_review"] = [
    {"item": "chart x-axis title (OCR garbled; rendered as 'Time (μs)')",
     "status": "needs-human-review"},
    {"item": "illustration content of raster cards (cannot verify blind)",
     "status": "needs-human-review"},
]
json.dump(sc, open("qa/semantic_constraint_audit.json", "w"), indent=1)
json.dump(coverage, open("qa/constraint_coverage_audit.json", "w"), indent=1)
report["semantic_constraints"] = sc["passed"]
report["constraint_coverage"] = coverage["passed"]

# ============================================================ 7 visual
full_im = render("full.svg", "full_render.png", width=W)
rec = np.asarray(full_im, float)
d_all = np.abs(src - rec).mean(axis=2)
vs = {"whole_image_mae": round(float(d_all.mean()), 2),
      "components": [], "note": "MAE dominated by font substitution in the "
      "text layer; PowerPoint renders real Arial from the same family list"}
Image.blend(Image.fromarray(src.astype("uint8")), full_im, 0.5).save(
    "qa/full_overlay_diff.png")
Image.fromarray((np.clip(d_all * 3, 0, 255)).astype("uint8")).save(
    "qa/amplified_diff.png")
zones = {"chart": cz, "methods_strip": (10, 682, 1610, 946),
         "bacterium_card": (14, 58, 350, 702),
         "bloodstream_card": (595, 158, 887, 660),
         "ab_card": (1258, 370, 1606, 672)}
for n, (x0, y0, x1, y1) in zones.items():
    vs["components"].append({"id": n, "bbox": [x0, y0, x1, y1],
                             "mae": round(float(d_all[y0:y1, x0:x1].mean()), 2)})
json.dump(vs, open("qa/visual_similarity_audit.json", "w"), indent=1)
report["visual_similarity"] = {"whole_image_mae": vs["whole_image_mae"],
                               "components": vs["components"]}

sheet = Image.new("RGB", (1400, 900), "white")
dr = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
except Exception:
    font = ImageFont.load_default()
tiles = [("source", Image.open("fig1.png")), ("render", full_im),
         ("overlay 50/50", Image.open("qa/full_overlay_diff.png")),
         ("diff x3", Image.open("qa/amplified_diff.png"))]
for i, (name, im_) in enumerate(tiles):
    im_.thumbnail((680, 420))
    x_, y_ = 10 + (i % 2) * 690, 10 + (i // 2) * 440
    dr.text((x_, y_), name, fill="black", font=font)
    sheet.paste(im_, (x_, y_ + 28))
sheet.save("qa/semantic_review_sheet.png")

json.dump(report, open("qa/aggregate_report.json", "w"), indent=1)
print(json.dumps(report, indent=1, default=str))
