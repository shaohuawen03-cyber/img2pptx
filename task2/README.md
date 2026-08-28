# img2pptx 任务产物：fig1_graphical_abstract.png（P. gingivalis → 阿尔茨海默病机制图文摘要）

来源：shaohuawen03-cyber/Auto-Empirical-Research-Skills（arena 分支）项目
1yzy-pg-ad-mechanism 稿件图 fig1。**盲重建 + 全矢量**（无既有资产、无视觉模型）：
结构信息来自颜色聚类、连通域、Hough/中轴几何、OCR；插画区域经
**k-means 量化 + potrace 贝塞尔追踪**转为真 SVG 形状（0 个 `<image>`）。

## 交付物

| 文件 | 说明 |
| --- | --- |
| `final.pptx` | 单页全矢量可编辑 PPTX（SVG 主表示 + PNG 回退） |
| `full.svg` | 21 个语义分组：27 条 `<text>`、27 条连线、全矢量 RMSD 图表、矢量方法区边框、**163 个量化色块贝塞尔形状**（插画） |
| `modules/*.svg` | 可独立编辑模块 |
| `component_manifest.json` | 清单 + 约束 + 优化历史 + 复核项 |
| `qa/*` | 全套审计（含"零栅格图片"硬门、矢量形状层、OCR 回读 84.2%） |

## 矢量化方法

每个插画区域：inpaint 去文字 → 中值滤波去噪 → k-means 聚成 10–14 色 →
逐色掩码 2× 上采样 → potrace 贝塞尔 → `<path fill-rule="evenodd">`，
按面积降序叠放。单色 IoU 0.88–0.97。整图 MAE 13.65（栅格裁剪版为 5.96，
全矢量化的量化代价，已在 manifest 中如实记录）。

## 已知限制

- 图表 x 轴标题原图 OCR 无法确读，按上下文渲染为 "Time (μs)"
- 插画为量化色块的近似：轮廓忠实、细纹理被简化（渐变会色带化）
- 文字层在无 Arial 环境用度量兼容 Carlito 回退

## 复现

```bash
python3 build_fig1.py          # 分割 + 矢量化 + 清单
python3 run_audits2.py         # 全部审计 -> qa/
python3 ../task/build_pptx.py  # final.pptx
```
