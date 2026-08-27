#!/usr/bin/env python3
"""Parse previous reconstruction SVG with proper affine accumulation -> JSON inventory."""
import json
import re
import sys
import xml.etree.ElementTree as ET

NUM = r"-?\d+(?:\.\d+)?"


def parse_numbers(s):
    return [float(x) for x in re.findall(NUM, s)]


def mul(a, b):
    """a,b as (a,b,c,d,e,f); result = a then b (a*b)."""
    a1, b1, c1, d1, e1, f1 = a
    a2, b2, c2, d2, e2, f2 = b
    return (a1 * a2 + c1 * b2,
            b1 * a2 + d1 * b2,
            a1 * c2 + c1 * d2,
            b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1,
            b1 * e2 + d1 * f2 + f1)


IDENT = (1, 0, 0, 1, 0, 0)


def parse_transform(t):
    m = IDENT
    if not t:
        return m
    for name, args in re.findall(rf"(matrix|translate|scale|rotate)\s*\(([^)]*)\)", t):
        v = parse_numbers(args)
        if name == "matrix" and len(v) == 6:
            mm = tuple(v)
        elif name == "translate":
            mm = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            sx = v[0]
            sy = v[1] if len(v) > 1 else v[0]
            mm = (sx, 0, 0, sy, 0, 0)
        elif name == "rotate":
            import math
            ang = math.radians(v[0])
            cx = v[1] if len(v) > 2 else 0
            cy = v[2] if len(v) > 2 else 0
            r = (math.cos(ang), math.sin(ang), -math.sin(ang), math.cos(ang), 0, 0)
            t1 = (1, 0, 0, 1, cx, cy)
            t2 = (1, 0, 0, 1, -cx, -cy)
            mm = mul(mul(t1, r), t2)
        else:
            mm = IDENT
        m = mul(m, mm)
    return m


def apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def path_bbox(d):
    nums = parse_numbers(d)
    if len(nums) < 2:
        return None
    pts = []
    # absolute commands set position; approximate by consuming pairs
    xs, ys = nums[0::2], nums[1::2]
    return [min(xs), min(ys), max(xs), max(ys)]


def main(svg_path, out_json):
    tree = ET.parse(svg_path)
    root = tree.getroot()
    vb = parse_numbers(root.get("viewBox", "")) or [0, 0, 0, 0]
    W = vb[2] or float(root.get("width", 0))
    H = vb[3] or float(root.get("height", 0))
    inv = {"canvas": {"width": W, "height": H}, "texts": [], "paths": [],
           "rects": [], "images": [], "uses": [], "order": []}

    def walk(el, m):
        tag = el.tag.split("}", 1)[1]
        m = mul(m, parse_transform(el.get("transform", "")))
        if tag == "text":
            x0, y0 = apply(m, float(el.get("x", 0)), float(el.get("y", 0)))
            inv["order"].append({"kind": "text", "idx": len(inv["texts"])})
            inv["texts"].append({
                "x": round(x0, 2), "y": round(y0, 2),
                "size": round(float(el.get("font-size", 16)) * m[0], 2),
                "family": el.get("font-family", ""),
                "fill": el.get("fill", "#000"),
                "weight": el.get("font-weight", "normal"),
                "anchor": el.get("text-anchor", "start"),
                "content": (el.text or "").strip(),
            })
        elif tag == "path":
            d = el.get("d", "")
            inv["order"].append({"kind": "path", "idx": len(inv["paths"])})
            bb = path_bbox(d)
            if bb:
                p1 = apply(m, bb[0], bb[1])
                p2 = apply(m, bb[2], bb[3])
                bb = [round(min(p1[0], p2[0]), 1), round(min(p1[1], p2[1]), 1),
                      round(max(p1[0], p2[0]), 1), round(max(p1[1], p2[1]), 1)]
            inv["paths"].append({
                "bbox": bb, "fill": el.get("fill", "none"),
                "stroke": el.get("stroke", "none"),
                "stroke_width": el.get("stroke-width"),
                "opacity": el.get("fill-opacity", el.get("opacity")),
                "n_cmd": len(re.findall(r"[A-Za-z]", d)),
                "d": d if len(d) < 300 else None,
            })
        elif tag == "rect":
            inv["order"].append({"kind": "rect", "idx": len(inv["rects"])})
            x, y = apply(m, float(el.get("x", 0)), float(el.get("y", 0)))
            w = float(el.get("width", 0)) * m[0]
            h = float(el.get("height", 0)) * m[3]
            inv["rects"].append({"x": round(x, 1), "y": round(y, 1),
                                 "w": round(w, 1), "h": round(h, 1),
                                 "fill": el.get("fill", "none"),
                                 "stroke": el.get("stroke", "none")})
        elif tag == "image":
            x, y = apply(m, float(el.get("x", 0)), float(el.get("y", 0)))
            inv["images"].append({
                "x": round(x, 1), "y": round(y, 1),
                "w": round(float(el.get("width", 0)) * m[0], 1),
                "h": round(float(el.get("height", 0)) * m[3], 1),
                "href_len": len(el.get("{http://www.w3.org/1999/xlink}href", "")
                                or el.get("href", ""))})
        for ch in el:
            walk(ch, m)

    walk(root, IDENT)
    with open(out_json, "w") as f:
        json.dump(inv, f, indent=1)
    print(f"canvas {W}x{H}  texts={len(inv['texts'])} paths={len(inv['paths'])} "
          f"rects={len(inv['rects'])} images={len(inv['images'])}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
