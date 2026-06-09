---
name: ai-hazop-skill
description: Review process design-file packages and produce HAZOP participating-expert opinions. Use when Codex needs to ingest PFD/P&ID/design basis/equipment lists/line lists/instrument indexes/cause-and-effect matrices/control philosophies/HAZOP worksheets/SIL or LOPA records/review comments/human expert HAZOP-SIL reports/LNG or oil-and-gas design files, extract evidence, identify missing information, and draft HAZOP expert questions, concerns, and requested clarifications without acting as the HAZOP chair.
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
   python scripts/hazop_expert.py --input <design-folder> --output <review-output-folder> --project-name "<project>"
   ```

3. Read `hazop_expert_opinions.md` first. Use `hazop_expert_opinions.json` when structured issue data is needed.
4. Run a red-team pass on the AI issue pool: delete non-applicable questions, merge duplicates, and flag questions contradicted by source drawings or later clarifications.
5. Treat the remaining output as expert prompts for the HAZOP meeting, not as formal HAZOP worksheet conclusions.
6. If source files include scanned PDFs or images, run OCR externally first or ask for native PDFs/Word/Excel exports. The script does not perform OCR.

## Bundled Resources

- `scripts/hazop_expert.py`: offline CLI that extracts text from common design files, builds an evidence index, applies a configurable HAZOP/LNG rule catalog, and writes Markdown/JSON/CSV outputs.
- `references/rule_catalog.json`: editable rule catalog for document completeness checks, generic HAZOP deviations, and LNG/cryogenic prompts.
- `references/review_playbook.md`: concise method notes, role boundaries, and source links for HAZOP and LNG review framing.
- `references/human_expert_patterns.md`: reusable patterns abstracted from a local human HAZOP/SIL report package; read it when reviewing HAZOP worksheets, SIL reports, C&E matrices, review comments, or action close-out tables.

## Output Reading Rules

- `critical` means the expert should raise it early because it affects study readiness or major safeguards.
- `high` means the item is likely important for node review or action wording.
- `medium` means it is a useful expert question but may be resolved quickly by another discipline.
- `confidence` describes evidence strength, not risk ranking.
- Missing-document findings are evidence gaps; do not imply the document does not exist outside the provided package.
- AI review findings are quality-control prompts for the expert. They are not process-safety findings unless tied back to design evidence.

## Customizing

Edit `references/rule_catalog.json` for project-specific rule packs, local standards, company checklists, or discipline-specific prompts. Prefer adding narrow evidence keywords and concrete questions rather than broad generic warnings.
