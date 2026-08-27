---
name: img2pptx
description: Reconstruct raster reference images as one-slide editable, modular, auditable PPTX files containing a complete SVG. Use when the user asks to convert, reproduce, trace, vectorize, or rebuild a PNG, JPG/JPEG, WebP, TIFF, HEIC, screenshot, diagram, infographic, scientific figure, architecture figure, or workflow image into an editable PowerPoint slide.
version: 1.1.0
---

# Img2Pptx (Antigravity edition)

This is the Google Antigravity entry file for the skill. The full execution
protocol lives in `PROTOCOL.md` (same folder); its `references/*.md` links are
preserved. Two differences from other runtimes:

1. Skills are auto-discovered from `.agent/skills/` (workspace) or
   `~/.gemini/antigravity/skills/` (global); keep this folder in sync with the
   canonical `skills/img2pptx/` via `scripts/sync_antigravity.py`.
2. Deterministic helpers ship as an MCP server (`img2pptx`). Prefer MCP tools
   over ad-hoc scripts when the server is connected (check with `/mcp`):

| MCP tool | Use for |
| --- | --- |
| `check_environment` | verify render/compare/pptx dependencies before starting |
| `skill_info` | pipeline digest (15 steps, deliverables, hard rules) |
| `normalize_image` | any input → upright RGB PNG (original untouched) |
| `render_svg` | SVG → PNG via resvg with metric-compatible font fallbacks |
| `compare_images` | MAE, missing/extra ink, grid heatmap, overlay + diff PNGs |
| `embed_svg_pptx` | full.svg + preview PNG → one-slide PPTX (SVG primary, PNG fallback) |
| `audit_pptx` | package audit: svgBlip wiring, rels, content types, hashes |

Suggested Antigravity flow: follow `SKILL.md` for semantics, drawing, and
QA; call the MCP tools for every deterministic step (render / compare /
package / audit). Keep task work in the current task directory so results
stay reproducible.
