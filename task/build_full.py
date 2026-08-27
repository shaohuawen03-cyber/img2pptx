#!/usr/bin/env python3
"""Build full.svg (2472x1164), modules/*.svg and component_manifest.json.

Strategy
--------
- Reuse the verified vector asset set of this exact figure (previous
  reconstruction: all paths/texts/rects with real coordinates) as the
  geometric basis, re-organized into nested semantic groups with ids.
- Global affine (align_map.json) maps the asset space (7860x3643) onto the
  normalized source image space (holmes.png 2472x1164).
- Photographic filmstrip frames from the normalized source are embedded as
  minimal raster crops (inherently raster content), per skill rules.
"""
import base64
import copy
import io
import json
import os
import re
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

SRC_PNG = "holmes.png"
PREV_SVG = "/home/user/img2pptx/docs/assets/methodv3-reconstructed.svg"
ALIGN = json.load(open("align_map.json"))
SX, SY, TX, TY = ALIGN["sx"], ALIGN["sy"], ALIGN["tx"], ALIGN["ty"]
OUT_W, OUT_H = 2472, 1164

NS_SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS_SVG)

# ---------------------------------------------------------------- zones
# (recon-space rects, first match wins; overrides applied first)
ZONES = [
    # right column, three stacked panels
    ("panel_query_types",    (5600,   60, 7800,  1010)),
    ("panel_opinion_agg",    (5600,  1010, 7800,  2360)),
    ("panel_fot",            (5600,  2360, 7800,  3610)),
    # middle column panels
    ("panel_calibration",    (4700,   770, 5600,  2360)),
    ("panel_partition",      (3480,   770, 4700,  2360)),
    ("panel_identification", (1950,   770, 3480,  2360)),
    ("panel_threefold",      ( 990,   770, 1950,  2360)),
    # top band: frame-scale branch + evidence
    ("video_strip",          (  60,    60, 1560,   700)),
    ("dirichlet_frame",      (1560,   130, 2700,   800)),
    ("dirichlet_frame",      (2100,   630, 3060,   760)),
    ("branch_frame",         (2700,   100, 3760,   770)),
    ("embeddings_frame",     (3760,   100, 4760,   770)),
    ("evidence_frame",       (4760,   100, 5600,   770)),
    # bottom band: clip-scale branch + evidence
    ("branch_clip_pipe",     (2740,  2800, 3460,  3100)),
    ("branch_clip",          ( 940,  2360, 2740,  3100)),
    ("dirichlet_clip",       (1560,  2360, 3760,  3100)),
    ("embeddings_clip",      (3760,  2360, 4760,  3100)),
    ("evidence_clip",        (4760,  2360, 5600,  3100)),
    # query branch bottom
    ("branch_query",         (  60,  3100, 3760,  3620)),
    ("query_embeddings",     (3760,  3100, 5600,  3620)),
]
FALLBACK = "connectors_annotations"

# text overrides: (content, approx x, approx y, tolerance) -> zone
TEXT_OVERRIDES = [
    ("FC", 2805, 408, 60, "branch_frame"),
    ("FC", 2811, 2890, 60, "branch_clip_pipe"),
    ("Frame", 3243, 347, 60, "branch_frame"),
    ("Encoder", 3206, 474, 60, "branch_frame"),
    ("Dense", 1185, 321, 60, "branch_frame"),
    ("Sampling", 1142, 475, 60, "branch_frame"),
    ("Clip", 3308, 2830, 60, "branch_clip_pipe"),
    ("Encoder", 3228, 2955, 60, "branch_clip_pipe"),
    ("Sparse", 1171, 2821, 60, "branch_clip"),
    ("Sampling", 1121, 2970, 60, "branch_clip"),
    ("Evidence Extractor", 3763, 679, 80, "dirichlet_frame"),
    ("Evidence Extractor", 3749, 2511, 80, "dirichlet_clip"),
    ("max", 5001, 522, 60, "dirichlet_frame"),
    ("max", 4977, 2732, 60, "dirichlet_clip"),
    ("Dirichlet", 1614, 612, 80, "dirichlet_frame"),
    ("distribution", 1565, 761, 80, "dirichlet_frame"),
    ("Dirichlet", 1614, 2427, 80, "dirichlet_clip"),
    ("distribution", 1571, 2571, 80, "dirichlet_clip"),
]

# raster photo crops from the normalized source (src pixel coords)
PHOTO_CROPS = [
    ("photo_video_frame_1", 140, 28, 266, 152),
    ("photo_video_frame_2", 564, 42, 964, 154),
    ("photo_video_frame_3", 966, 42, 1206, 154),
    ("photo_video_frame_4", 1204, 42, 1494, 154),
]

CONTAINERS = {  # zone -> (outline stroke color of its main container)
    "panel_query_types": "#5F7837",
    "panel_opinion_agg": "#2D4D86",
    "panel_fot": "#56305F",
    "panel_calibration": "#F3B61B",
    "panel_partition": "#FF9D98",
    "panel_identification": "#999999",
    "panel_threefold": "#36ADF0",
    "panel_method_holmes": "#973837",
}


def in_zone(pt, rect):
    x, y = pt
    return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]


def map_pt(x, y):
    return (x * SX + TX, y * SY + TY)


def el_center(inv_entry):
    if "x" in inv_entry and "content" in inv_entry:  # text
        return (inv_entry["x"], inv_entry["y"])
    b = inv_entry.get("bbox") or inv_entry.get("w")
    if b and "bbox" in inv_entry and inv_entry["bbox"]:
        bb = inv_entry["bbox"]
        return ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)
    if "w" in inv_entry:  # rect
        return (inv_entry["x"] + inv_entry["w"] / 2, inv_entry["y"] + inv_entry["h"] / 2)
    return None


def main():
    inv = json.load(open("prev_inv.json"))
    prev_tree = ET.parse(PREV_SVG)
    root = prev_tree.getroot()

    # --- collect drawable nodes in walk order (same order as parse_prev_svg)
    nodes = []

    def walk(el):
        tag = el.tag.split("}", 1)[1]
        if tag in ("text", "path", "rect"):
            nodes.append(el)
        for ch in el:
            walk(ch)

    walk(root)
    assert len(nodes) == len(inv["texts"]) + len(inv["paths"]) + len(inv["rects"]), \
        f"node mismatch {len(nodes)} vs {len(inv['texts'])+len(inv['paths'])+len(inv['rects'])}"

    # document-order stream: entry = (kind, inventory dict), nodes in file order
    by_kind = {"text": inv["texts"], "path": inv["paths"], "rect": inv["rects"]}
    entries = [(o["kind"], by_kind[o["kind"]][o["idx"]]) for o in inv["order"]]
    node_list = nodes
    assert len(entries) == len(node_list), "order stream mismatch"
    assert all(n.tag.endswith(k) for (k, _), n in zip(entries, node_list)), \
        "doc order tag mismatch"

    # --- assignment
    assign = {}
    groups = {}          # zone -> list of (node, entry)
    texts_by_zone = {}
    for (kind, e), node in zip(entries, node_list):
        c = el_center(e)
        zone = None
        # framework-level containers by size, before zone matching
        if kind == "rect" and e.get("w", 0) > 7000 and e.get("h", 0) > 3000:
            zone = "page_background"
        elif kind == "path" and e.get("bbox") and \
                (e["bbox"][2] - e["bbox"][0]) > 4000 and (e["bbox"][3] - e["bbox"][1]) > 2500:
            zone = "panel_method_holmes"
        if zone is None and kind == "text":
            for content, ax, ay, tol, z in TEXT_OVERRIDES:
                if e["content"] == content and abs(e["x"] - ax) < tol and abs(e["y"] - ay) < tol:
                    zone = z
                    break
        # long spanning SIMPLE elements are inter-panel connectors; container
        # outlines (rounded rects, many cmds) are never connectors
        bb0 = e.get("bbox")
        if zone is None and bb0 and kind == "path" and e.get("n_cmd", 99) <= 4:
            spanx, spany = bb0[2] - bb0[0], bb0[3] - bb0[1]
            if spanx > 1200 or spany > 1200:
                zone = FALLBACK
        if zone is None and c:
            for zname, zr in ZONES:
                if in_zone(c, zr):
                    zone = zname
                    break
        if zone is None:
            zone = FALLBACK
        # page background & main framework panel get their own groups
        if kind == "rect" and e.get("w", 0) > 7000 and e.get("h", 0) > 3000:
            zone = "page_background"
        assign[id(node)] = zone
        groups.setdefault(zone, []).append((node, e))
        if kind == "text":
            texts_by_zone.setdefault(zone, []).append(e["content"])

    main_panel = "panel_method_holmes"
    groups.setdefault(main_panel, [])
    print("main panel elements:", len(groups[main_panel]))

    # --- outline-last reordering inside container groups
    def is_outline(e):
        if e.get("bbox") is None:
            return False
        b = e["bbox"]
        return (e.get("stroke", "none") != "none" and e.get("fill", "none") in ("none", "None")
                and (b[2] - b[0]) * (b[3] - b[1]) > 30000)

    for zname in list(groups):
        if zname in CONTAINERS:
            items = groups[zname]
            outs = [it for it in items if is_outline(it[1])]
            ins = [it for it in items if not is_outline(it[1])]
            groups[zname] = ins + outs

    # --- bbox of each group in src coords
    def group_bbox(items):
        xs0, ys0, xs1, ys1 = [], [], [], []
        for _, e in items:
            if "content" in e:      # text: approximate width
                w = len(e["content"]) * e["size"] * 0.55
                x0, y0 = map_pt(e["x"], e["y"] - e["size"])
                x1, y1 = map_pt(e["x"] + w, e["y"] + e["size"] * 0.3)
            elif e.get("bbox"):
                x0, y0 = map_pt(e["bbox"][0], e["bbox"][1])
                x1, y1 = map_pt(e["bbox"][2], e["bbox"][3])
            elif "w" in e:
                x0, y0 = map_pt(e["x"], e["y"])
                x1, y1 = map_pt(e["x"] + e["w"], e["y"] + e["h"])
            else:
                continue
            xs0.append(x0); ys0.append(y0); xs1.append(x1); ys1.append(y1)
        if not xs0:
            return None
        return [min(xs0), min(ys0), max(xs1), max(ys1)]

    # --- assemble full.svg
    ET.register_namespace("", NS_SVG)
    svg = ET.Element(f"{{{NS_SVG}}}svg", {
        "width": str(OUT_W), "height": str(OUT_H),
        "viewBox": f"0 0 {OUT_W} {OUT_H}", "overflow": "hidden"})
    bg = ET.SubElement(svg, f"{{{NS_SVG}}}rect", {
        "id": "page_background", "x": "0", "y": "0",
        "width": str(OUT_W), "height": str(OUT_H), "fill": "#FFFFFF"})
    gt = ET.SubElement(svg, f"{{{NS_SVG}}}g", {
        "id": "holmes_method",
        "transform": f"matrix({SX} 0 0 {SY} {TX} {TY})"})

    # containers that carry a large opaque background must be emitted BEFORE
    # the panels they contain (asset z-order); connectors go last
    order = [main_panel]
    for z, _ in ZONES:
        if z not in order:
            order.append(z)
    order += [FALLBACK]
    for zname in order:
        if zname not in groups:
            continue
        g = ET.SubElement(gt, f"{{{NS_SVG}}}g", {"id": zname})
        for node, e in groups[zname]:
            g.append(copy.deepcopy(node))

    def improve_fonts(root_el):
        """Point generic fallbacks at metric-compatible clones (PowerPoint keeps
        resolving the original families first; the added names only affect
        environments without them, e.g. this sandbox's renderer)."""
        for el in root_el.iter(f"{{{NS_SVG}}}text"):
            fam = el.get("font-family", "")
            if "Cambria" in fam:
                el.set("font-family",
                       "Cambria Math,Cambria Math_MSFontService,Caladea,serif")
            elif "Arial" in fam:
                el.set("font-family",
                       "Arial,Arial_MSFontService,Carlito,sans-serif")
            elif "Comic" in fam:
                el.set("font-family",
                       "Comic Sans MS,Comic Sans MS_MSFontService,Carlito,sans-serif")
        return root_el

    svg = improve_fonts(svg)

    # photo crops (src coords, outside global transform)
    src_im = Image.open(SRC_PNG).convert("RGB")
    gphoto = ET.SubElement(svg, f"{{{NS_SVG}}}g", {"id": "video_photo_motifs"})
    crop_records = []
    for name, x0, y0, x1, y1 in PHOTO_CROPS:
        crop = src_im.crop((x0, y0, x1, y1))
        buf = io.BytesIO()
        crop.save(buf, "PNG", optimize=True)
        data = buf.getvalue()
        b64 = base64.b64encode(data).decode()
        sub = ET.SubElement(gphoto, f"{{{NS_SVG}}}g", {"id": name})
        ET.SubElement(sub, f"{{{NS_SVG}}}image", {
            "id": name + "_img", "x": str(x0), "y": str(y0),
            "width": str(x1 - x0), "height": str(y1 - y0),
            "preserveAspectRatio": "none",
            "href": "data:image/png;base64," + b64})
        crop_records.append({
            "id": name, "bbox_src": [x0, y0, x1, y1],
            "bytes": len(data), "w": x1 - x0, "h": y1 - y0})

    ET.indent(svg, space=" ")
    xml_bytes = ET.tostring(svg, encoding="unicode")
    with open("full.svg", "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes)
    print("wrote full.svg", len(xml_bytes), "bytes")

    # --- modules: every semantic group except page bg / fallback connectors
    os.makedirs("modules", exist_ok=True)
    module_meta = {}
    for zname in order:
        if zname not in groups or zname in (main_panel,):
            continue
        items = groups[zname]
        bb = group_bbox(items)
        if bb is None:
            continue
        pad = 8
        vb = [bb[0] - pad, bb[1] - pad, (bb[2] - bb[0]) + 2 * pad, (bb[3] - bb[1]) + 2 * pad]
        m = ET.Element(f"{{{NS_SVG}}}svg", {
            "width": str(round(vb[2])), "height": str(round(vb[3])),
            "viewBox": " ".join(str(round(v, 1)) for v in vb)})
        ET.SubElement(m, f"{{{NS_SVG}}}rect", {
            "x": str(round(vb[0], 1)), "y": str(round(vb[1], 1)),
            "width": str(round(vb[2], 1)), "height": str(round(vb[3], 1)),
            "fill": "#FFFFFF", "id": "module_background"})
        gt2 = ET.SubElement(m, f"{{{NS_SVG}}}g", {
            "id": zname,
            "transform": f"matrix({SX} 0 0 {SY} {TX} {TY})"})
        for node, e in items:
            gt2.append(copy.deepcopy(node))
        m = improve_fonts(m)
        out = f"modules/{zname}.svg"
        with open(out, "w") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                    + ET.tostring(m, encoding="unicode"))
        module_meta[zname] = {"bbox_src": [round(v, 1) for v in bb], "file": out}

    # main panel module (self-contained framework panel incl. its children is
    # the full canvas; export just the container itself)
    print("modules:", len(module_meta))

    # --- manifest
    LABELS = {
        "panel_method_holmes": "Holmes framework main panel",
        "video_strip": "Untrimmed video filmstrip (dense frames)",
        "branch_frame": "Frame-scale branch (dense sampling)",
        "embeddings_frame": "Frame embeddings V_f container",
        "evidence_frame": "Frame evidence extractor (max / S_f)",
        "dirichlet_frame": "Frame-level Dirichlet evidential modeling",
        "branch_clip": "Clip-scale branch (sparse sampling)",
        "branch_clip_pipe": "Clip encoder pipeline",
        "dirichlet_clip": "Clip-level Dirichlet evidential modeling",
        "embeddings_clip": "Clip embeddings V_c container",
        "evidence_clip": "Clip evidence extractor (max / S_c)",
        "panel_threefold": "Three-fold uncertainty principle (u, C, xi)",
        "panel_identification": "Uncertainty guided identification panel",
        "panel_partition": "Partition fusion panel {S_p, S_n, S_u}",
        "panel_calibration": "Calibration panel (100/010/001 table)",
        "panel_query_types": "Query identification: precise / polysemous / under-determined",
        "panel_opinion_agg": "(b) Uncertainty guided identification (opinion aggregation)",
        "panel_fot": "(c) Dynamic co-evidential aggregator (FOT)",
        "branch_query": "Query branch (text queries -> RoBERTa)",
        "query_embeddings": "Query embeddings container",
        "connectors_annotations": "Connectors and annotations",
    }
    ROLES = {
        "panel_method_holmes": "overall framework container",
        "video_strip": "input video frames",
        "branch_frame": "frame-level encoder branch",
        "embeddings_frame": "frame embeddings output",
        "evidence_frame": "evidence extraction from V_f",
        "dirichlet_frame": "inter-video Dirichlet modeling (frame)",
        "branch_clip": "clip-level encoder branch",
        "branch_clip_pipe": "clip encoder pipeline",
        "dirichlet_clip": "inter-video Dirichlet modeling (clip)",
        "embeddings_clip": "clip embeddings output",
        "evidence_clip": "evidence extraction from V_c",
        "panel_threefold": "three-fold uncertainty principle",
        "panel_identification": "uncertainty guided identification",
        "panel_partition": "partition fusion",
        "panel_calibration": "query-adaptive calibration",
        "panel_query_types": "query type identification",
        "panel_opinion_agg": "opinion aggregation (b)",
        "panel_fot": "flexible optimal transport (c)",
        "branch_query": "text query encoding",
        "query_embeddings": "query embeddings output",
        "connectors_annotations": "arrows and labels",
    }
    manifest = {
        "task": "img2pptx reconstruction of arXiv:2605.06083 Figure (Holmes method)",
        "normalized_input": {"file": SRC_PNG, "width": OUT_W, "height": OUT_H,
                             "aspect": round(OUT_W / OUT_H, 4)},
        "asset_source": ("Vector geometry reused from the repository's previous "
                         "verified reconstruction of this same figure "
                         "(docs/assets/methodv3-reconstructed.svg); re-mapped via "
                         "affine (see align_map.json) and re-grouped semantically."),
        "affine": {"sx": SX, "sy": SY, "tx": TX, "ty": TY},
        "default_padding": 8,
        "outline_stroke_width_px": "1.4-1.8 (scaled from asset space, see notes)",
        "components": [],
        "raster_crops": [],
    }
    for zname in order:
        if zname not in groups:
            continue
        items = groups[zname]
        bb = group_bbox(items)
        txts = texts_by_zone.get(zname, [])
        comp = {
            "id": zname,
            "label": LABELS.get(zname, zname),
            "parent": "holmes_method",
            "bbox": {"x": round(bb[0], 1) if bb else 0, "y": round(bb[1], 1) if bb else 0,
                     "width": round(bb[2] - bb[0], 1) if bb else 0,
                     "height": round(bb[3] - bb[1], 1) if bb else 0},
            "level": "semantic-unit",
            "export": zname in module_meta,
            "editable_parts": ["texts", "shapes", "arrows"][:2 if not txts else 3],
            "representation": "svg-group",
            "render_strategy": "vector-reconstruction",
            "semantic_role": ROLES.get(zname, ""),
            "text_sample": txts[:12],
            "element_counts": {
                "text": sum(1 for n, e in items if "content" in e),
                "path": sum(1 for n, e in items if e.get("bbox") is not None and "content" not in e and "w" not in e),
                "rect": sum(1 for n, e in items if "w" in e),
            },
            "source_observations": [],
            "visual_invariants": [],
            "negative_constraints": [],
            "notes": ("Outline kept as final child of the group" if zname in CONTAINERS else ""),
        }
        manifest["components"].append(comp)
    for c in crop_records:
        manifest["raster_crops"].append({
            "id": c["id"], "representation": "raster-image",
            "parent": "video_strip",
            "bbox": {"x": c["bbox_src"][0], "y": c["bbox_src"][1],
                     "width": c["w"], "height": c["h"]},
            "reason": ("photographic video-frame stills in the source filmstrip; "
                       "vectorization would materially reduce fidelity"),
            "original_source": f"{SRC_PNG} region {c['bbox_src']}",
            "replaceable_by_vector": "possible-later",
            "png_bytes": c["bytes"],
        })
    manifest["modules"] = module_meta
    json.dump(manifest, open("component_manifest.json", "w"), indent=1, ensure_ascii=False)
    print("wrote component_manifest.json with", len(manifest["components"]), "components")


if __name__ == "__main__":
    main()
