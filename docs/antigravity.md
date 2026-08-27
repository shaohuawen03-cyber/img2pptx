# 在 Google Antigravity（反重力）中使用 img2pptx

本文覆盖两部分：**Agent Skills**（协议层）与 **MCP 服务器**（确定性工具层）。

## 一键同步

```bash
pip install -r mcp/img2pptx_mcp/requirements.txt
python3 scripts/sync_antigravity.py            # 工作区安装
python3 scripts/sync_antigravity.py --global   # 需要跨项目时再加装全局
```

同步脚本做四件事（幂等，可重复执行）：

1. 把规范源 `skills/img2pptx/` 复制到 Antigravity 工作区技能目录
   `.agent/skills/img2pptx/`（入口 `SKILL.md` = 精简 frontmatter + 指针，
   完整协议在同目录 `PROTOCOL.md`，`references/` 链接保持有效）；
2. `--global` 时再装到 `~/.gemini/antigravity/skills/img2pptx/`；
3. 生成/刷新工作区 MCP 配置 `.agents/mcp_config.json`（绝对路径）；
4. 校验所有被写出的 `SKILL.md` frontmatter（name/description）。

## Skills 机制速览

| 作用域 | 路径 | 说明 |
| --- | --- | --- |
| 工作区 | `.agent/skills/<name>/SKILL.md` | 随仓库提交，团队共享 |
| 全局 | `~/.gemini/antigravity/skills/<name>/SKILL.md` | 个人跨项目工具 |

- 采用开放 Agent Skills 标准（与 Claude Code / Codex / Cursor 同一 SKILL.md
  格式，YAML frontmatter：`name` + `description`，可选 `version`）；
- 渐进式披露：Antigravity 只在对话开始时加载 name/description（约 100
  tokens），任务相关时才读全文；`PROTOCOL.md` 与 `references/` 按需加载；
- 目录约定：`scripts/`（辅助脚本）、`examples/`、`resources/` 与
  `references/`、`assets/` 互相兼容。

## MCP 机制速览

| 作用域 | 路径 |
| --- | --- |
| 工作区 | `.agents/mcp_config.json` |
| 全局 | `~/.gemini/config/mcp_config.json`（Antigravity 2.x：IDE/agy CLI/SDK 共用） |

手动配置示例（stdio 本地服务器）：

```json
{
  "mcpServers": {
    "img2pptx": {
      "command": "/usr/bin/python3",
      "args": ["/absolute/path/to/img2pptx/mcp/img2pptx_mcp/server.py"]
    }
  }
}
```

- 在 Antigravity 里输入 `/mcp` 查看已连接服务器与工具；
- 远程 MCP 必须用 `serverUrl`（不是 `url`/`httpUrl`）；
- 旧版 CLI 变体的全局路径可能是 `~/.gemini/antigravity-cli/mcp_config.json`，
  以 IDE 内 MCP 面板 "View raw config" 显示的路径为准。

## 分工：Skill 负责"想"，MCP 负责"算"

```
Agent（Gemini/Claude/…）
 ├── SKILL.md/PROTOCOL.md   语义分解、约束抽取、绘制、纠错循环（协议）
 └── img2pptx MCP
      ├── check_environment / skill_info
      ├── normalize_image    任意图 → 规范化 PNG
      ├── render_svg         SVG → PNG（resvg + 度量兼容字体）
      ├── compare_images     MAE / 缺墨 / 网格热图 / overlay+diff
      ├── embed_svg_pptx     单页 PPTX（SVG 主表示 + PNG 回退）
      └── audit_pptx         包完整性审计
```

## 使用示例

同步完成后，在 Antigravity 对话框中：

```text
使用 img2pptx 技能，把 methodv3.pdf 导出的 method.png 重建为单页可编辑 PPTX。
渲染、对比、打包请调用 img2pptx MCP 的工具，语义审计按 PROTOCOL.md 执行。
```

## 常见问题

- **`/mcp` 看不到服务器**：重启工作区；确认 `.agents/mcp_config.json` 中
  `command` 是绝对路径且 `python3` 可用；
- **工具报缺少依赖**：`pip install -r mcp/img2pptx_mcp/requirements.txt`；
- **渲染字形与源图不一致**：放置 Caladea/Carlito 到
  `IMG2PPTX_FONTS_DIR` 指向目录（详见 `mcp/img2pptx_mcp/README.md`）；
- **只想更新技能不改 MCP**：`python3 scripts/sync_antigravity.py --check`
  先预览，脚本按文件粒度覆盖 skill 目录，MCP 配置仅在缺失/变更时重写。
