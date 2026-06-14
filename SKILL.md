---
name: ai-hazop-skill
description: Review process design-file packages and produce drawing-by-drawing HAZOP participating-expert pre-review outputs. Use when Codex needs to ingest PFD/P&ID/design basis/equipment lists/line lists/instrument indexes/cause-and-effect matrices/control philosophies/HAZOP worksheets/SIL or LOPA records/review comments/human expert HAZOP-SIL reports/LNG or oil-and-gas design files, extract evidence, organize each drawing into node/design-intent/review-focus rows, and draft HAZOP expert questions, possible causes, possible consequences, safeguards to verify, and requested clarifications without acting as the HAZOP chair.
---

# AI HAZOP Skill

## Role Boundary

Act as a HAZOP participating expert, not the HAZOP chair.

- Identify missing, inconsistent, unclear, or weakly evidenced design information.
- Draft questions for the chair, process owner, designer, vendor, operation, instrumentation, electrical, fire protection, and layout disciplines.
- Point to evidence and ask for clarification, calculation basis, drawings, or safeguards.
- Do not issue final HAZOP decisions, close actions, approve design, or replace the formal study worksheet.

## Default Workflow

1. Confirm the input folder contains design deliverables or extracted text from deliverables.
2. Run the bundled script:

   ```powershell
   py scripts/hazop_expert.py --input <design-folder> --output <review-output-folder> --project-name "<project>"
   ```

3. If the package contains PDF PFD/P&ID drawings, run the topology evidence extractor:

   ```powershell
   py scripts/extract_pid_topology.py --input <design-folder> --output <review-output-folder>\topology
   ```

4. Treat PFD drawings as project-wide context only. Do not include PFD drawings in drawing-by-drawing HAZOP findings unless the user explicitly asks for a PFD review.
5. Ignore files whose path or filename contains `已建` by default; treat them as existing-facility interface background unless the user explicitly asks to review existing systems.
6. Read `topology\pid_topology_review.md` before trusting any flow-path or upstream/downstream statement. It provides vector-PDF line-component and tag-neighborhood evidence, not final topology.
7. For LNG receiving terminals, especially membrane LNG tanks, use the LNG-specific rules in `references/rule_catalog.json` before accepting generic HAZOP prompts. Prioritize tank containment/insulation-space monitoring, nitrogen inerting, rollover/LTD, in-tank pumps, BOG/recondenser pressure control, ship-shore transfer, interconnection modes, cryogenic relief/flare, ORV seawater, commissioning cooldown, and SIS/GDS interfaces.
8. Read `hazop_drawing_reviews.md` next. This is the primary human-facing output: one section per P&ID drawing, with problem/deviation, possible causes, possible consequences, safeguards to verify, expert actions, evidence excerpts, and limited cross-drawing links.
9. Use `hazop_drawing_reviews.csv` for meeting preparation filtering. Use `hazop_drawing_reviews.json` for downstream dashboards or custom processing.
10. Use `hazop_expert_opinions.md/json` only as the secondary rule-hit pool and missing-document overview, not as the main review surface.
11. Run a red-team pass drawing by drawing: delete non-applicable rows, merge duplicates inside the same drawing, and flag rows contradicted by source drawings, topology evidence, or later clarifications.
12. Treat all outputs as expert prompts for the HAZOP meeting, not as formal HAZOP worksheet conclusions.
13. If source files include scanned PDFs or images, run OCR/vectorization externally first or ask for native PDFs/Word/Excel/DEXPI exports. The bundled scripts do not perform OCR.

## Bundled Resources

- `scripts/hazop_expert.py`: offline CLI that extracts text from common design files, builds an evidence index, applies a configurable HAZOP/LNG rule catalog, and writes Markdown/JSON/CSV outputs.
- `scripts/extract_pid_topology.py`: experimental vector-PDF topology evidence extractor. It reads text coordinates and line segments with PyMuPDF, groups line segments into components, associates nearby tags, and outputs candidate tag-to-tag connections for expert review.
- `scripts/render_hazop_workbench_html.py`: primary offline HTML renderer for expert meeting preparation. It merges `hazop_expert_opinions.json` drawing reviews with optional `topology/pid_topology_index.json` and original PDF previews, so each drawing starts from the source image, overlays candidate topology boxes, then shows drawing-specific expert questions.
- `scripts/render_hazop_html.py`: legacy/offline renderer for `hazop_expert_opinions.json`; when `drawing_reviews` are present, the HTML defaults to a drawing-by-drawing review dashboard without topology merge.
- `references/rule_catalog.json`: editable rule catalog for document completeness checks, generic HAZOP deviations, and LNG receiving-terminal prompts. It includes deeper membrane tank, BOG, ship-shore, ORV, cryogenic relief, interconnection, commissioning, SIS/GDS, and project-learned YueDong LNG prompts.
- `references/review_playbook.md`: concise method notes, role boundaries, and source links for HAZOP and LNG review framing.
- `references/human_expert_patterns.md`: reusable patterns abstracted from a local human HAZOP/SIL report package; read it when reviewing HAZOP worksheets, SIL reports, C&E matrices, review comments, or action close-out tables.

## Output Structure

- `hazop_drawing_reviews.md`: primary drawing-by-drawing expert pre-review.
- `hazop_drawing_reviews.csv`: spreadsheet-friendly row list for meeting preparation.
- `hazop_drawing_reviews.json`: structured drawing review data.
- `topology/pid_topology_review.md`: experimental vector-PDF topology evidence report.
- `topology/pid_topology_connections.csv`: candidate same-line-component tag connections.
- `topology/pid_topology_index.json`: structured topology evidence with text coordinates, line components, and candidate connections.
- `hazop_expert_opinions.md/json/csv`: secondary rule-hit pool and package-level evidence gaps.
- `extracted_index.json`: extraction status, text character counts, document types, tags, and warnings.
- `review_prompt.md`: prompt for human/AI red-team review.
- Recommended expert-facing HTML dashboard:

  ```powershell
  py scripts/render_hazop_workbench_html.py --hazop-json <review-output-folder>\hazop_expert_opinions.json --topology-json <review-output-folder>\topology\pid_topology_index.json --design-root <design-folder> --output-html <review-output-folder>\hazop_workbench.html
  ```

- Optional legacy HTML dashboard:

  ```powershell
  py scripts/render_hazop_html.py --input-json <review-output-folder>\hazop_expert_opinions.json --output-html <review-output-folder>\hazop_dashboard.html
  ```

## Output Reading Rules

- `critical` means the expert should raise it early because it affects study readiness or major safeguards.
- `high` means the item is likely important for node review or action wording.
- `medium` means it is a useful expert question but may be resolved quickly by another discipline.
- `confidence` describes evidence strength, not risk ranking.
- Missing-document findings are evidence gaps; do not imply the document does not exist outside the provided package.
- AI review findings are quality-control prompts for the expert. They are not process-safety findings unless tied back to design evidence.
- A drawing row's `possible causes`, `possible consequences`, and `safeguards to verify` are draft review prompts. Do not state them as facts unless the source drawing, calculation, C&E, procedure, or meeting discussion confirms them.
- Review one drawing at a time. Describe cross-drawing relationships only when needed for interfaces, upstream/downstream effects, ESD/SIS/C&E, BOG, flare/vent, utilities, or shared safeguards.
- Review one P&ID at a time. PFD is project background, not a default drawing-by-drawing HAZOP worksheet source.
- Ignore `已建` drawings by default unless existing-facility review is explicitly in scope.
- Do not claim that PDF drawings have been truly understood unless topology evidence exists. For text-only runs, explicitly say the output is based on text extraction and expert-rule prompts.
- Treat `pid_topology_*` connections as candidate evidence: useful for finding likely paths and review targets, but still requiring human drawing review before HAZOP use.
- For HTML deliverables, put expert-usable question chains first: problem/deviation, possible causes, possible consequences, safeguards to verify, meeting questions, and evidence. Keep OCR/vector/topology internals behind the question chain instead of making them the primary reading surface.
- For HTML deliverables, show the original PFD/P&ID PDF preview beside the advice whenever possible. Overlay topology candidate boxes on the source drawing and keep garbled or low-quality text extraction hidden from the default advice view.

## Customizing

Edit `references/rule_catalog.json` for project-specific rule packs, local standards, company checklists, or discipline-specific prompts. Prefer adding narrow evidence keywords and concrete questions rather than broad generic warnings. For LNG projects, add rules from real terminal technology and local project evidence first; do not let generic text-extraction hits dominate membrane tank, BOG, ship-shore, ORV, flare, or SIS/GDS review depth.
