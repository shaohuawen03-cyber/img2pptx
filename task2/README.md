# img2pptx 任务产物：fig1_graphical_abstract.png（P. gingivalis → 阿尔茨海默病机制图文摘要）

来源：shaohuawen03-cyber/Auto-Empirical-Research-Skills（arena 分支）项目
1yzy-pg-ad-mechanism 稿件图 fig1。**盲重建**（无既有矢量资产、无视觉模型），
结构信息全部来自程序化分析：颜色聚类、连通域、Hough/中轴几何、RapidOCR。

## 交付物

| 文件 | 说明 |
| --- | --- |
| `final.pptx` | 单页可编辑 PPTX（SVG 主表示 + PNG 回退），13.33″×8.0″ |
| `full.svg` | 21 个语义分组：27 条可编辑 `<text>`、27 条矢量连线、全矢量 RMSD 图表、矢量方法区边框、17 块插图裁剪（已 inpaint 去文字） |
| `modules/*.svg` | 可独立编辑模块（图表、连线、标签层、方法区、3 张卡片） |
| `component_manifest.json` | 组件清单 + 语义约束 + 优化日志 + 待人工复核项 |
| `qa/*` | 全套审计（OCR 回读 84.2%、图表单值性/数值域、刻度完整性、区域掩码等，全部硬门通过） |

## 结构对照

- 上部机制流（细菌卡片 → 血流卡片 → BBB → 脑/斑块/tau）＝插图裁剪 + 矢量文字 + 中轴追踪连线
- 底部方法带 = 矢量深蓝边框 + 2 条分隔线（transcriptomics | molecular docking | MD simulation）
- RMSD 图 = 纯矢量（L 形轴、刻度 0.0–1.0 / 0.0–0.4、7.5px 藏青曲线逐列提取）

## 已知限制（如实记录）

- 图表 x 轴标题原图 OCR 无法确读，按上下文渲染为 "Time (μs)"（待人工确认）
- 文字层在无 Arial 环境用度量兼容 Carlito 回退；PowerPoint 中按真 Arial 渲染
- 复杂生物插画按 skill 规则保留为最小栅格裁剪（可整体移动/替换）
- 整图 MAE≈5.96，缺墨 1.27%（其余为字形替换差异）

## 复现

```bash
python3 build_fig1.py          # 分割 + 重建 + 清单（需 ocr.json）
python3 run_audits2.py         # 全部审计 -> qa/
python3 ../task/build_pptx.py  # final.pptx（SVG 主表示）
```
