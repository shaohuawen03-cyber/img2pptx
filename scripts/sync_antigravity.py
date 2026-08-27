#!/usr/bin/env python3
"""Sync the img2pptx skill + MCP server into Google Antigravity.

What it does (idempotent, safe to re-run):
  1. copies the canonical skill `skills/img2pptx` (SKILL.md + references/
     + platform/) into the Antigravity workspace skill dir `.agent/skills/`;
  2. with `--global`, also copies it to `~/.gemini/antigravity/skills/`;
  3. writes/refreshes the Antigravity MCP config with absolute paths:
       workspace: `.agents/mcp_config.json`
       global (--global): `~/.gemini/config/mcp_config.json`  (merged)
  4. validates every SKILL.md frontmatter (name/description) it touches.

Usage:
    python3 scripts/sync_antigravity.py            # workspace only
    python3 scripts/sync_antigravity.py --global   # workspace + global
    python3 scripts/sync_antigravity.py --check    # verify only, no writes
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL_SRC = REPO / "skills" / "img2pptx"
SKILL_NAME = "img2pptx"
WS_SKILLS = REPO / ".agent" / "skills" / SKILL_NAME
GLOBAL_SKILLS = Path.home() / ".gemini" / "antigravity" / "skills" / SKILL_NAME
WS_MCP = REPO / ".agents" / "mcp_config.json"
GLOBAL_MCP = Path.home() / ".gemini" / "config" / "mcp_config.json"
SERVER = REPO / "mcp" / "img2pptx_mcp" / "server.py"

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def validate_skill_md(path: Path) -> dict:
    txt = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(txt)
    if not m:
        raise SystemExit(f"[fail] {path}: missing YAML frontmatter")
    fm = m.group(1)
    name = re.search(r"^name:\s*(\S+)", fm, re.M)
    desc = re.search(r"^description:\s*(.+)", fm, re.M)
    if not name or not desc or len(desc.group(1).strip()) < 20:
        raise SystemExit(f"[fail] {path}: frontmatter needs name + a specific description")
    return {"name": name.group(1), "description_len": len(desc.group(1))}


def sync_skill(dst: Path, dry: bool = False) -> None:
    validate_skill_md(SKILL_SRC / "SKILL.md")
    if dry:
        print(f"[check] would sync skill -> {dst}")
        return
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILL_SRC, dst,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # full protocol stays available with its references/ links intact
    shutil.move(str(dst / "SKILL.md"), str(dst / "PROTOCOL.md"))
    # Antigravity entry file: frontmatter + pointer to the full protocol
    platform = (SKILL_SRC / "platform" / "antigravity.md").read_text(encoding="utf-8")
    (dst / "SKILL.md").write_text(platform, encoding="utf-8")
    validate_skill_md(dst / "SKILL.md")
    print(f"[ok] skill synced -> {dst}")


def mcp_entry() -> dict:
    py = shutil.which("python3") or shutil.which("python")
    if not py:
        raise SystemExit("[fail] python3 not found on PATH")
    if not SERVER.exists():
        raise SystemExit(f"[fail] MCP server missing: {SERVER}")
    return {
        "command": py,
        "args": [str(SERVER)],
    }


def write_mcp_config(path: Path, dry: bool = False, merge: bool = False) -> None:
    entry = mcp_entry()
    if dry:
        print(f"[check] would write MCP entry into {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    cfg = {}
    if merge and path.exists():
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"[warn] {path} unreadable ({e}); recreating")
    cfg.setdefault("mcpServers", {})["img2pptx"] = entry
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    print(f"[ok] MCP config -> {path}  (command: {entry['command']})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--global", dest="glob", action="store_true",
                    help="also install to ~/.gemini/antigravity/skills and "
                         "merge into ~/.gemini/config/mcp_config.json")
    ap.add_argument("--check", action="store_true", help="verify only, no writes")
    args = ap.parse_args()

    print(f"repo: {REPO}")
    sync_skill(WS_SKILLS, dry=args.check)
    write_mcp_config(WS_MCP, dry=args.check, merge=False)
    if args.glob:
        sync_skill(GLOBAL_SKILLS, dry=args.check)
        write_mcp_config(GLOBAL_MCP, dry=args.check, merge=True)

    if not args.check:
        print("\nNext steps in Antigravity:")
        print("  1. reopen the workspace (or run /mcp) so the server is picked up")
        print("  2. verify: /mcp should list `img2pptx` tools like render_svg")
        print("  3. try: '使用 img2pptx skill 把 figure.png 重建为可编辑 PPTX'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
