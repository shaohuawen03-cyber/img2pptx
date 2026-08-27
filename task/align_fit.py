#!/usr/bin/env python3
"""Find optimal affine map (recon coords -> holmes px) by MAE search.

Renders the previous reconstruction natively, then searches scale/offset.
"""
import json
import numpy as np
from PIL import Image
import resvg_py
import io

RECON_SVG = "/home/user/img2pptx/docs/assets/methodv3-reconstructed.svg"
SRC = "holmes.png"

# native render of recon (7860x3643)
png = resvg_py.svg_to_bytes(open(RECON_SVG).read(), background="#ffffff")
rec = np.asarray(Image.open(io.BytesIO(png)).convert("L"), float)
print("native render:", rec.shape)
mask = rec < 245
ys, xs = np.where(mask)
rb = [xs.min(), ys.min(), xs.max(), ys.max()]
print("recon content bbox:", rb)

src_im = Image.open(SRC).convert("L")
src = np.asarray(src_im, float)
sm = src < 245
ys, xs = np.where(sm)
sb = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
print("src content bbox:", sb)


def render_map(scale_fit="content"):
    if scale_fit == "content":
        sx = (sb[2] - sb[0]) / (rb[2] - rb[0])
        sy = (sb[3] - sb[1]) / (rb[3] - rb[1])
        tx = sb[0] - rb[0] * sx
        ty = sb[1] - rb[1] * sy
    else:  # uniform by width
        sx = sy = (sb[2] - sb[0]) / (rb[2] - rb[0])
        tx, ty = sb[0] - rb[0] * sx, sb[1] - rb[1] * sy
    return sx, sy, tx, ty


def remap_render(sx, sy, tx, ty, out_w=2472, out_h=1164):
    """Warp native recon render into src space by inverse mapping."""
    H, W = rec.shape
    # For each src pixel, source coord in recon space
    yy, xx = np.mgrid[0:out_h, 0:out_w].astype(np.float32)
    rx = (xx - tx) / sx
    ry = (yy - ty) / sy
    img = Image.fromarray(rec.astype(np.uint8))
    # PIL transform: inverse map coeffs (src->dst we need dst->src)
    # Image.transform AFFINE maps output (x,y) -> (a x + b y + c, d x + e y + f)
    a = 1 / sx
    e = 1 / sy
    c = -tx / sx
    f = -ty / sy
    return np.asarray(img.transform((out_w, out_h), Image.AFFINE,
                                    (a, 0, c, 0, e, f), Image.BILINEAR), float)


best = None
for fit in ("content", "uniform"):
    sx, sy, tx, ty = render_map(fit)
    r = remap_render(sx, sy, tx, ty)
    mae = np.abs(src - r).mean()
    print(f"fit={fit}: sx={sx:.5f} sy={sy:.5f} tx={tx:.1f} ty={ty:.1f} MAE={mae:.2f}")
    if best is None or mae < best[0]:
        best = (mae, sx, sy, tx, ty, fit)

# local refinement around best
mae0, sx, sy, tx, ty, fit = best
for it in range(3):
    improved = False
    for dsx in (-0.002, -0.001, 0, 0.001, 0.002):
        for dsy in (-0.002, -0.001, 0, 0.001, 0.002):
            for dtx in (-6, -3, 0, 3, 6):
                for dty in (-6, -3, 0, 3, 6):
                    c = (sx * (1 + dsx), sy * (1 + dsy), tx + dtx, ty + dty)
                    r = remap_render(*c)
                    m = np.abs(src - r).mean()
                    if m < best[0] - 0.01:
                        best = (m, *c, fit)
                        improved = True
    mae0, sx, sy, tx, ty, fit = best
    print(f"iter{it}: MAE={mae0:.2f} sx={sx:.5f} sy={sy:.5f} tx={tx:.1f} ty={ty:.1f}")
    if not improved:
        break

json.dump({"sx": best[1], "sy": best[2], "tx": best[3], "ty": best[4],
           "fit": best[5], "mae": best[0],
           "recon_content_bbox": rb, "src_content_bbox": sb},
          open("align_map.json", "w"), indent=1)
print("saved align_map.json:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in json.load(open('align_map.json')).items() if k != 'fit'})
