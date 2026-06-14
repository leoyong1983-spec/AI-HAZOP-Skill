# AI-HAZOP-Skill

## 中文说明

AI-HAZOP-Skill 是一个面向工程设计文件包的 HAZOP 参会专家预审技能。它不替代 HAZOP 主席，不输出正式 HAZOP 结论，而是帮助专家在会前逐张 P&ID 发现问题、提出问题，并准备需要设计方、业主、运行、仪表、电气、消防、总图和厂家回答的证据清单。

当前版本重点强化了 LNG 接收站和 LNG 薄膜罐场景，包含薄膜罐主膜/次屏障/绝热空间、氮气惰化、LTD/翻滚、罐内泵、BOG/再冷凝、装船/卸船/返气、一期二期互联互通、低温泄放/火炬、ORV海水、投产预冷和 SIS/GDS/FAS 接口等专家问题库。

### 主要能力

- 读取设计文件包中的 PDF、Word、Excel、文本和表格资料。
- 默认将 PFD 作为项目整体理解基础，不参与逐张 HAZOP 问题行分析。
- 默认忽略文件名或路径包含“已建”的图纸，将其作为既有装置接口背景。
- 逐张 P&ID 输出问题/偏差、可能原因、可能后果、已有保护层待核查、专家行动和证据摘录。
- 从矢量 PDF 中抽取候选拓扑证据，用于辅助专家看图确认管线、位号和上下游关系。
- 生成 HTML 工作台，在左侧显示原始 PDF 缩略图和拓扑候选框，右侧显示本图纸专家问题。

### 快速使用

```powershell
py scripts/hazop_expert.py --input <design-folder> --output <review-output-folder> --project-name "<project>"
py scripts/extract_pid_topology.py --input <design-folder> --output <review-output-folder>\topology
py scripts/render_hazop_workbench_html.py --hazop-json <review-output-folder>\hazop_expert_opinions.json --topology-json <review-output-folder>\topology\pid_topology_index.json --design-root <design-folder> --output-html <review-output-folder>\hazop_workbench.html
```

### 主要输出

- `hazop_workbench.html`：推荐打开的专家预审工作台。
- `hazop_drawing_reviews.md`：逐张 P&ID 专家预审表。
- `hazop_drawing_reviews.csv`：会议准备和筛选用表格。
- `hazop_drawing_reviews.json`：结构化逐图纸问题数据。
- `topology/pid_topology_review.md`：候选拓扑证据报告。
- `hazop_expert_opinions.md/json/csv`：包级问题池和资料缺口。

### 使用边界

本工具输出的是专家问题池，不是正式 HAZOP worksheet、风险评级、设计批准意见或行动项关闭意见。扫描图、CAD 原图、厂家包、C&E、SIL/LOPA、操作程序和会议澄清仍需人工核查。拓扑抽取结果只是候选证据，必须由专家回到原图确认。

### 许可证

本项目采用 MIT License 开源。

## English Description

AI-HAZOP-Skill is a HAZOP participating-expert pre-review skill for engineering design packages. It does not replace the HAZOP chair and does not produce formal HAZOP conclusions. Its purpose is to help experts review P&IDs drawing by drawing, identify issues, ask sharper questions, and prepare evidence requests for the designer, owner, operation, instrumentation, electrical, fire protection, layout, and vendor teams.

The current version is strengthened for LNG receiving terminals and LNG membrane tanks. It includes expert prompts for membrane tank primary membrane / secondary barrier / insulation space, nitrogen inerting, LTD and rollover, in-tank pumps, BOG and recondenser pressure control, loading / unloading / vapor return, brownfield interconnection, cryogenic relief and flare, ORV seawater systems, commissioning cooldown, and SIS/GDS/FAS interfaces.

### Key Capabilities

- Reads design-package materials such as PDFs, Word documents, Excel files, text files, and tables.
- Treats PFDs as project-wide process context by default, not as drawing-by-drawing HAZOP rows.
- Ignores drawings whose path or filename contains `已建` by default, treating them as existing-facility interface background.
- Produces drawing-by-drawing P&ID findings with problem/deviation, possible causes, possible consequences, safeguards to verify, expert actions, and evidence excerpts.
- Extracts candidate topology evidence from vector PDFs to help experts verify lines, tags, and upstream/downstream relationships.
- Renders an HTML workbench with the source PDF preview and topology overlays on the left, and drawing-specific expert questions on the right.

### Quick Start

```powershell
py scripts/hazop_expert.py --input <design-folder> --output <review-output-folder> --project-name "<project>"
py scripts/extract_pid_topology.py --input <design-folder> --output <review-output-folder>\topology
py scripts/render_hazop_workbench_html.py --hazop-json <review-output-folder>\hazop_expert_opinions.json --topology-json <review-output-folder>\topology\pid_topology_index.json --design-root <design-folder> --output-html <review-output-folder>\hazop_workbench.html
```

### Main Outputs

- `hazop_workbench.html`: recommended expert-facing review workbench.
- `hazop_drawing_reviews.md`: drawing-by-drawing P&ID pre-review.
- `hazop_drawing_reviews.csv`: spreadsheet-friendly meeting preparation table.
- `hazop_drawing_reviews.json`: structured drawing-review data.
- `topology/pid_topology_review.md`: candidate topology evidence report.
- `hazop_expert_opinions.md/json/csv`: package-level issue pool and information gaps.

### Boundaries

The tool produces an expert question pool, not a formal HAZOP worksheet, risk ranking, design approval, or action close-out record. Scanned drawings, native CAD files, vendor packages, C&E matrices, SIL/LOPA records, operating procedures, and meeting clarifications still require human verification. Topology extraction is candidate evidence only and must be checked against the original drawings.

### License

This project is open sourced under the MIT License.
