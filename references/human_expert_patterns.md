# Human Expert HAZOP/SIL Report Patterns

Derived on 2026-06-09 from the local RuDong LNG HAZOP/SIL package supplied by the user. This file stores reusable patterns only; do not copy project report text into generic outputs.

## Report Architecture

Human expert packages separate the work into:

- HAZOP narrative report: project scope, method, participants, node basis, system descriptions, and attachments.
- HAZOP worksheet: one sheet per node, with node description, design intent, drawing number, meeting date, chair/recorder, participants, and row-level deviations.
- High-risk and complex scenario summary: extracted from the worksheet for focused review.
- SIL report: starts from HAZOP scenarios and performs LOPA/SIF allocation.
- C&E/SIS matrix: trigger causes, interlock IDs, action targets, reset behavior, ESD/SIL levels, and P&ID references.
- Review-comment register: page/comment/revision-response style closure of missing analyses.
- Report-conclusion summary: risk-count summary, SIL-count summary, and recommendation close-out table.

## HAZOP Worksheet Fields To Emulate

For each node, prefer this schema:

- node id
- node description
- design intent
- drawing number
- meeting date
- chair/recorder/participants
- parameter
- guideword
- analysis object
- cause
- consequence
- inherent severity/likelihood/risk rank
- existing safeguards
- residual severity/likelihood/risk rank
- recommendation
- discussion/rationale
- responsible party

When AI drafts expert questions, map every question to at least one of these fields. If a field is missing from source evidence, frame it as a question for the chair/designer.

## Human Expert Patterns Learned

- Do not review only the narrative report. Check worksheet attachments, high-risk summaries, C&E matrices, SIL records, and review-comment registers.
- Treat high-risk and complex scenarios as a separate expert-review surface. Ask whether all III/IV inherent-risk or multi-system consequence scenarios are summarized.
- Check that every important SIS/C&E cause and action has a matching HAZOP scenario and, where appropriate, SIL/LOPA treatment.
- For new or late-added critical ESD/XV/SDV valves, ask whether HAZOP and SIL screening were updated.
- For shared LNG transfer facilities, ask whether third-party package accidents and interface failures can affect the current project.
- In LNG unloading, check reverse flow through check-valve bypasses, manual bypass opening, high-point vapor pockets, and liquid hammer on restart.
- Challenge any LNG/cryogenic pre-cooling plan involving nitrogen or temporary connections; confirm the actual pre-cooling medium and isolation basis.
- In maintenance/tie-in tasks, ask for blind/spool replacement, nitrogen purge, gas testing, isolation, and reinstatement evidence.
- For vapor return and drain-pot modes, check mutually exclusive valve paths and whether a pair of valves can bypass pressure/temperature control.
- Confirm valve fail-safe positions are shown consistently on P&IDs, valve lists, and C&E matrices, especially for loss of instrument air.
- Recommendations should include cause, consequence, existing safeguards, recommendation text, recommendation type, technical basis, close-out opinion, planned date, and responsible party.

## Expert Role Reminder

Use these patterns to ask sharper questions. Do not assert final HAZOP conclusions, close recommendations, or approve SIL classifications unless the formal chair/workgroup has done so.
