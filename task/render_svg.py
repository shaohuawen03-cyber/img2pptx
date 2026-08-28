#!/usr/bin/env python3
"""Render an SVG with resvg_py (white bg) + metric-compatible fonts."""
import io
import os
import sys

import resvg_py
from PIL import Image

FONT_DIRS = [
    os.environ.get("IMG2PPTX_FONTS_DIR", "/nonexistent"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts"),
    "/usr/share/fonts/truetype/dejavu",
]


def font_files():
    out = []
    for d in FONT_DIRS:
        if os.path.isdir(d):
            out += [os.path.join(d, f) for f in sorted(os.listdir(d))
                    if f.endswith(".ttf")]
    return out


def render(svg_path: str, out_png: str, width: int | None = None) -> Image.Image:
    kw = {"background": "#ffffff"}
    ff = font_files()
    if ff:
        kw.update(font_files=ff, serif_family="Caladea",
                  sans_serif_family="Carlito")
    if width is not None:
        kw["width"] = width
    with open(svg_path) as f:
        png = resvg_py.svg_to_bytes(f.read(), **kw)
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if width is not None and im.width != width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(out_png)
    return im


if __name__ == "__main__":
    svg_path, out_png = sys.argv[1], sys.argv[2]
    width = int(sys.argv[3]) if len(sys.argv) > 3 else None
    im = render(svg_path, out_png, width)
    print(f"rendered {svg_path} -> {out_png} {im.size} (fonts: {len(font_files())})")
