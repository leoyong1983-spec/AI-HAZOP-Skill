# AI HAZOP Expert Review Playbook

## Method Anchor

Use HAZOP as a systematic, guideword-based questioning method. AIChE/CCPS describes HAZOP as a qualitative technique that applies guidewords to discover deviations from design intent, their causes, and consequences. IEC 61882:2016 is the international application guide for HAZOP studies and covers definition, preparation, examination sessions, documentation, and follow-up. OSHA and EPA PHA rules are useful public checklists for expert questioning because they explicitly call out previous incidents, engineering and administrative controls, consequences of control failure, facility siting, human factors, natural hazards, power loss, and finding resolution. For LNG projects, PHMSA 49 CFR Part 193 and NFPA 59A are useful public anchors for LNG siting, impoundment, control, emergency shutdown, fire protection, operation, and maintenance themes, but the controlling standard set depends on project jurisdiction and contract basis.

Source links:

- AIChE/CCPS glossary: https://www.aiche.org/ccps/resources/glossary/process-safety-glossary/hazard-and-operability-study-hazop
- IEC 61882:2016 product page: https://webstore.iec.ch/en/publication/24321
- OSHA 29 CFR 1910.119: https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.119
- EPA 40 CFR 68.67: https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-68/subpart-D/section-68.67
- PHMSA 49 CFR Part 193: https://www.ecfr.gov/current/title-49/subtitle-B/chapter-I/subchapter-D/part-193
- NFPA 59A standard-development page: https://www.nfpa.org/codes-and-standards/nfpa-59a-standard-development/59a
- SIGTTO publications entry point: https://www.sigtto.org/
- preHAZOP open-source project: https://github.com/TUDoAD/preHAZOP
- Safety Science LLM HAZOP evaluation: https://www.sciencedirect.com/science/article/pii/S0925753525002644
- Local human expert patterns: `references/human_expert_patterns.md`

## Participating Expert Scope

Focus on questions and evidence gaps:

- Is the design intent clear enough for the node?
- Are deviations, causes, consequences, safeguards, and actions supported by drawings or calculations?
- Are assumptions from process, instrumentation, layout, electrical, fire protection, operation, and vendor packages consistent?
- Which documents must be brought into the meeting before the chair can close the discussion?

Avoid chair responsibilities:

- Do not declare action closure.
- Do not assign final risk ranking unless the meeting method explicitly asks the expert to propose one.
- Do not approve or reject the design.
- Do not rewrite the official HAZOP worksheet as if the meeting has occurred.

## Strong Evidence Types

- PFD and process description for design intent and normal operating envelope.
- P&ID for node boundary, isolation, vents, drains, relief devices, instrumentation, trips, and manual valves.
- Line list and equipment list for design pressure, design temperature, material, insulation, phase, and fluid service.
- Instrument index, alarm/trip list, control philosophy, and cause-and-effect matrix for safeguards and action sequencing.
- Relief/flare or vent study for blocked-in, fire, thermal expansion, compressor trip, and control-valve failure cases.
- Hazardous-area classification, F&G layout, firewater, passive fire protection, drainage/impoundment, and plot plan for release consequence controls.
- Vendor datasheets and operating procedures for packaged systems and startup/shutdown/maintenance deviations.
- Previous incidents, near misses, lessons learned, and same-service operating experience.
- MOC/PSSR, temporary bypass, commissioning, and tie-in packages for brownfield expansion.
- Human-factor evidence: alarm philosophy, bypass management, staffing, operator response time, training, and drills.
- Natural-hazard, external-event, facility-siting, building-risk, and public receptor studies.
- Emergency response, fire protection, evacuation, communications, and mutual-aid interfaces.

## Borrowed Practice Additions

Apply these extra challenge lines during expert review:

- Previous incidents: ask whether same-service incidents and near misses have been converted into node-level deviations, causes, consequences, or safeguards.
- Human factors: challenge any safeguard that depends on rapid manual action, alarm response, field access, verbal communication, or memory.
- Facility siting: ask whether occupied buildings, control rooms, temporary buildings, public receptors, escape routes, and neighboring units are exposed in major scenarios.
- Natural hazards: treat typhoon, storm surge, flood, earthquake, lightning, external fire, ship collision, and total power loss as possible common-cause failures.
- MOC/PSSR: for expansion and tie-in work, review temporary states, incomplete actions, software changes, bypasses, blinds, and startup assumptions separately from steady-state operation.
- Emergency response: test the detection-isolation-firefighting-evacuation chain under night shift, bad weather, power loss, road blockage, and communication failure.
- Action quality: when draft actions appear, ask whether they are specific, evidence-backed, closeable, and oriented first toward elimination, engineering controls, or verified protection rather than vague management wording.
- AI review: every AI-generated issue must be traceable to a source excerpt or a declared information gap; run a red-team pass to delete non-applicable or contradicted questions, and challenge safeguards that rely only on procedures or operator attention when engineering controls are possible.
- Human-report emulation: when source packages include HAZOP worksheets, SIL records, C&E matrices, review comments, or recommendation tables, use `human_expert_patterns.md` to check node structure, high-risk summaries, HAZOP-to-SIL traceability, review-comment closure, and action quality.

## LNG/Cryogenic Themes

Raise questions on:

- Low-temperature embrittlement, insulation damage, cold spill drainage, impoundment, and brittle fracture exposure.
- Blocked-in LNG/cryogenic liquid thermal expansion and relief path confirmation.
- LNG tank overfill, high-high level actions, pressure/vacuum protection, rollover/stratification, and BOG handling.
- Ship-shore or truck unloading ESD sequence, emergency release coupling, transfer arm isolation, and return-gas coordination.
- BOG compressor trip/recycle/flare interactions and downstream pressure excursions.
- Vaporizer low-temperature gas export, high pressure, tube leak, seawater/glycol/hot-water utility loss, and hydrate/freezing scenarios.
- Gas detection, flame detection, hazardous-area boundary consistency, ventilation, and ignition-source control.
- Brownfield expansion tie-ins, simultaneous operations, temporary bypasses, isolation blinds, and changeover procedures.
