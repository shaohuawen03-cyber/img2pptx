# img2pptx 任务产物：Holmes 方法图（arXiv:2605.06083）

把论文《Revisiting Uncertainty: On Evidential Learning for Partially
Relevant Video Retrieval》(ICML 2026, Holmes) 的方法总览图重建为
**单页可编辑 PPTX**。

## 输入

- `holmes.png`（2472×1164）：取自论文官方仓库
  `lijun2005/ICML26-Holmes` 的 `figures/holmes.png`（arXiv 二进制下载在
  沙箱内被网络策略拦截，改由 GitHub API 获取）。

## 交付物

| 文件 | 说明 |
| --- | --- |
| `final.pptx` | 单页幻灯片；SVG 为主表示（svgBlip），PNG 为回退 |
| `full.svg` | 完整可编辑矢量重建：27 个嵌套分组、307 个 `<text>`、481 个矢量图元 |
| `modules/*.svg` | 20 个可独立编辑的语义模块（面板/分支/表格各自成文件） |
| `component_manifest.json` | 组件清单：层级、bbox、语义角色、约束、栅格裁剪记录、优化日志 |
| `qa/*` | 全套审计证据（布局骨架、独立完整性、包含关系、对齐、边框分层、语义约束、覆盖率、视觉相似度、PPTX 包检查） |

## 在 PowerPoint 中编辑

1. 打开 `final.pptx`，右键幻灯片中的图形 → **转换为形状**（或 repeatedly
   **取消组合**；层级较深，需要多次取消组合才能触达底层元素）。
2. 所有文字均为真实文本框，图形均为形状；语义分组（三分支、Dirichlet
   建模、校准表、FOT 面板等）会作为组合保留，可整组移动/修改。
3. 字体族列表保留了 Cambria Math / Arial / Comic Sans MS（Windows 自带）；
   无这些字体的环境会按回退链替换。
4. 4 处视频帧照片按 skill 规则以**最小栅格裁剪**嵌入（data URI）；
   “转换为形状”后个别 PowerPoint 版本可能丢弃图内位图，届时可从
   `qa/pptx_slide_preview.png` 或 `holmes.png` 对应区域重新插入。

## 复现管线（本目录脚本）

```
parse_prev_svg.py   # 资产清单（复用仓库既有的该图矢量资产）
align_fit.py        # 资产→原图的仿射对齐（MAE 搜索）
build_full.py       # 语义重组 → full.svg + modules + manifest
run_audits.py       # 全部结构/语义/视觉审计 → qa/*
build_pptx.py       # final.pptx（SVG 主表示）+ 包审计
```

渲染器为 resvg（`resvg-py`），字体回退：Caladea（Cambria 度量兼容）、
Carlito（Calibri 度量兼容）、DejaVu（希腊字母/符号）。预览 MAE 的字体
替换上限已在 manifest 的 `visual_optimization` 中如实记录。
