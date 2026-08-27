#!/usr/bin/env python3
"""Render an SVG with resvg_py and save PNG at a target width (or native size)."""
import sys
import resvg_py
from PIL import Image
import io


def render(svg_path: str, out_png: str, width: int | None = None) -> Image.Image:
    with open(svg_path, "rb") as f:
        data = f.read()
    # resvg_py returns PNG bytes; render at native size first, white background
    png = resvg_py.svg_to_bytes(data.decode("utf-8", "replace"), background="#ffffff")
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if width is not None and im.width != width:
        h = round(im.height * width / im.width)
        im = im.resize((width, h), Image.LANCZOS)
    im.save(out_png)
    return im


if __name__ == "__main__":
    svg_path, out_png = sys.argv[1], sys.argv[2]
    width = int(sys.argv[3]) if len(sys.argv) > 3 else None
    im = render(svg_path, out_png, width)
    print(f"rendered {svg_path} -> {out_png} {im.size}")
