# img2pptx MCP server (Antigravity / Claude / Cursor / 任意 MCP 客户端)

把 img2pptx skill 的确定性核心步骤暴露为 MCP 工具：渲染、对比、打包、审计。
语义分析、绘制与决策仍由 Agent 按 SKILL.md 协议完成。

## 工具列表

| 工具 | 作用 |
| --- | --- |
| `check_environment` | 检查 pillow / numpy / python-pptx / resvg-py / 字体 |
| `skill_info` | 返回 15 步协议摘要 + 交付物 + 硬性规则 |
| `normalize_image` | 任意输入图 → 直立 RGB PNG（不改原件） |
| `render_svg` | resvg 渲染 SVG → PNG（白底，度量兼容字体回退） |
| `compare_images` | MAE、缺墨/多墨比例、网格热图、overlay + diff 图 |
| `embed_svg_pptx` | full.svg + 预览 PNG → 单页 PPTX（SVG 主表示 + PNG 回退）并审计 |
| `audit_pptx` | 校验 PPTX 包：svgBlip、rels、Content-Types、哈希、单页 |

## 安装

```bash
pip install -r mcp/img2pptx_mcp/requirements.txt
```

## Antigravity 配置

方式一（推荐，自动生成绝对路径）：

```bash
python3 scripts/sync_antigravity.py           # 工作区（.agents/mcp_config.json + .agent/skills/）
python3 scripts/sync_antigravity.py --global  # 同时装到全局（~/.gemini/...）
```

方式二（手写配置）：workspace 级 `.agents/mcp_config.json`，或全局
`~/.gemini/config/mcp_config.json`：

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

> 注意：Antigravity 2.x 全局配置在 `~/.gemini/config/mcp_config.json`（IDE、
> agy CLI、SDK 共用）；旧版本/CLI 变体可能使用 `~/.gemini/antigravity-cli/mcp_config.json`，
> 在 IDE 的 MCP 面板点 "View raw config" 可确认实际生效路径。远程服务器请用
> `serverUrl` 而不是 `url`。

在 Antigravity 中输入 `/mcp` 应能看到 `img2pptx` 及其工具。

## 其他客户端

<details>
<summary>Claude Desktop / Cursor 配置</summary>

`claude_desktop_config.json`（macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "img2pptx": {
      "command": "python3",
      "args": ["/absolute/path/to/img2pptx/mcp/img2pptx_mcp/server.py"]
    }
  }
}
```

Cursor: `~/.cursor/mcp.json` 使用相同的 `mcpServers` 结构。

</details>

## 字体（可选，提升渲染保真）

服务器会自动在以下位置寻找 `.ttf`（按序）：
环境变量 `IMG2PPTX_FONTS_DIR` → 仓库 `task/fonts/` → `mcp/img2pptx_mcp/fonts/`
→ `~/.local/share/img2pptx/fonts/`。推荐放置 Cambria/Calibri 的度量兼容
字体（Caladea、Carlito），参考 `task/` 内的下载方式或从 google/fonts 获取。

## 冒烟测试

```bash
python3 - <<'EOF'
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command="python3",
        args=["mcp/img2pptx_mcp/server.py"])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print([t.name for t in tools.tools])
            out = await s.call_tool("check_environment", {})
            print(out.content[0].text)

asyncio.run(main())
EOF
```
