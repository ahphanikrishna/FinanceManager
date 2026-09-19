# FinanceManager Handoff Package

## Executive summary
FinanceManager is a Flask-based personal finance application intended for incremental feature development by Copilot and PI Harness agents. The project already contains a working app structure with Flask blueprints, SQLAlchemy models, repository/service layers, templates, and parser utilities for financial data imports.

The objective of this handoff is to guide future development work toward a clean, modular, low-risk implementation plan. The team should prioritize app stability first, then user experience, then intelligence features such as monthly insights and category suggestions, and finally integrations like XLSX/PDF imports and Gmail-based transaction sync.

## Short project brief
This project will evolve into a modern personal finance manager with:
- a polished, user-friendly dashboard and transaction experience
- month-by-month spend analysis and actionable financial insights
- category and subcategory suggestions derived from historical transaction patterns
- a guided onboarding flow for new users
- three transaction input paths: manual entry, file import, and Gmail sync

The implementation should be delivered incrementally, with each phase validated before the next phase begins.

---

## Repository context
- `run.py` starts the app and selects the environment.
- `api/` contains API-blueprint endpoints.
- `views/` contains UI route blueprints.
- `app/` contains models, database, repository, and services.
- `templates/` and `static/` contain the front-end UI.
- `data/` contains seed and import data.
- `test_run.py` provides the initial smoke tests.

## Architecture expectations
- Keep API route logic in `api/`.
- Keep page handlers in `views/`.
- Keep models in `app/models.py`.
- Keep data access in `app/repository.py` and `app/database.py`.
- Keep business logic in `app/services/`.
- Keep templates and static assets separate.
- Preserve blueprint-based app structure and environment handling.

## Product goals
The app should support the following core product improvements:

1. User-friendly and elegant UI
   - better dashboard readability
   - cleaner transaction workflow
   - improved layout, visual hierarchy, spacing, and responsiveness

2. Monthly spend analysis dashboard
   - total spend by month
   - category and subcategory summaries
   - month-over-month comparisons
   - spend trend insights and anomaly detection
   - plain-language financial summaries

3. ML-assisted categorization
   - use historical transaction data to suggest categories and subcategories
   - provide confidence scores and allow override
   - apply to manual and imported transactions

4. First-run onboarding
   - guided setup for new users
   - profile, account, category, and budget setup
   - clear progress tracking and completion state

5. Three input methods
   - manual entry
   - XLSX/PDF import
   - Gmail sync integration

---

## Operating principles
1. Work in modular phases.
2. Prefer small, verified changes over large refactors.
3. Keep the code aligned with the current Flask blueprint architecture.
4. Validate each phase with the smallest relevant smoke test or behavior check.
5. Keep the output concise and implementation-focused.

## Mandatory execution approach
Do not attempt to complete the entire roadmap in one large change.

This repository must be developed in phased, low-risk increments. Agents must not dump the full roadmap into a single patch or run.

### Required phase model
#### Phase 1: Foundation and structure
- confirm app startup remains stable
- inspect relevant routes and models
- establish the minimal data model and service interface needed
- keep work isolated to the correct layer

#### Phase 2: User-facing improvement
- improve the dashboard and transaction flow experience
- optimize layout, readability, and interaction flow
- validate basic page rendering and navigation

#### Phase 3: Insights and analytics
- add monthly spend analysis summary cards and trend views
- create spending insights logic and relevant backend APIs
- validate output with realistic sample data

#### Phase 4: ML-assisted categorization
- implement historical transaction-based category suggestion logic
- add confidence scoring and override flow
- integrate suggestions into import and manual transaction entry

#### Phase 5: First-run onboarding
- create the onboarding wizard for new users
- add step-by-step guidance and progress tracking
- ensure the flow is accessible and clear

#### Phase 6: Input integrations
- add manual entry flow
- add XLSX/PDF import parser integration
- add Gmail sync flow with clearly scoped API/service integration

#### Phase 7: Final consolidation
- connect all modules together
- ensure consistency across dashboard, onboarding, imports, and suggestions
- run final validation and summarize the outcome

### Required task completion pattern
Every work item must follow this checklist:
1. inspect the relevant files
2. identify the exact layer to change
3. implement the minimum viable version
4. validate the behavior with the smallest relevant smoke check
5. summarize the result and define the next small step

If a work item spans multiple domains, split it into multiple sub-tasks instead of shipping one large patch.

## Token efficiency rules
To prevent overload and reduce context issues:
- implement one feature cluster at a time
- keep each patch small and focused
- prefer one domain at a time: UI, analytics, ML, onboarding, or sync
- do not produce a giant multi-feature patch in a single response
- when a task spans multiple domains, split it into sequential work items
- provide milestone updates after each phase
- avoid broad, speculative refactors when a narrow fix is sufficient
- keep output concise and implementation-focused instead of documenting the entire roadmap repeatedly

## Strict working constraints
- No large end-to-end feature dump in a single pass.
- No broad refactor unless required for correctness.
- No hidden assumptions about data or environment.
- No completion claim without a relevant validation result.
- No change to auth or startup flow without a direct smoke test.
- Do not bypass the repository/service architecture.

## Suggested work package pattern
For every task, follow this pattern:
1. inspect the relevant files
2. identify the exact layer to change
3. implement the minimum viable version
4. validate the behavior
5. summarize results and define the next small step

## Quality requirements
- Keep code readable and maintainable.
- Protect authentication and startup flow.
- Prefer real behavior checks over mock-only validation.
- Add or extend tests when a fix affects critical behavior.
- Keep the UI experience consistent and user-focused.

## Feature priorities
Priority order for implementation:
1. app stability and correctness
2. onboarding and user setup flow
3. UI polish and usability
4. monthly spend insights dashboard
5. category auto-classification from historical data
6. XLSX/PDF import integration
7. Gmail sync integration

## Output style for agents
- Keep the implementation concise and practical.
- State what was changed, where it was changed, and how it was validated.
- Do not claim completion without evidence from a relevant check.
- If a feature requires more than one phase, explicitly call out the next phase.

## Do / Don't
### Do
- Keep changes scoped to the correct module and domain.
- Use the repository/service layers for persistence and business logic.
- Validate with real app behavior and smoke checks.
- Keep the onboarding and transaction flow intuitive.
- Preserve route names, template usage, and startup environment behavior.

### Don't
- Do not bypass the app architecture with ad hoc DB access in views.
- Do not create broad refactors without a clear need.
- Do not treat mock-only validation as proof of correctness.
- Do not change authentication flow or startup logic without verification.
- Do not dump the complete roadmap into one patch.

## PI Harness intake format
Use this format for incoming work items:

```text
Task Title:
<short, descriptive title>

Objective:
<what the task is trying to achieve>

Scope:
- files likely involved:
- expected behavior:
- constraints or edge cases:

Acceptance Criteria:
- <observable behavior 1>
- <observable behavior 2>
- <verification command or validation step>

Risk Areas:
- auth/session impact
- database/repository impact
- UI rendering impact
- environment-specific behavior
```

## Known issues / next steps
### Current known areas to monitor
- startup and environment selection in `run.py` should remain stable across dev/qa/prod flows
- repository and database flows should be checked whenever models change
- parser and import flows may need validation against real statement files
- route stability should be preserved as new templates or APIs are added

### Suggested next steps
1. Add stronger automated tests around repository and transaction flows.
2. Validate parser behavior for real bank statements.
3. Review auth/security patterns for production readiness.
4. Improve data validation around CSV import and balance calculations.
5. Document remaining feature gaps before broader refactors.

## Acceptance checklist for completed work
A task is considered done only if all of the following are true:
- the relevant feature or bug fix is implemented in the correct layer
- the application still starts successfully
- the affected route or workflow behaves correctly
- the relevant tests or smoke checks pass
- the final result is reported with actual verification evidence

## Final instruction
Complete the work in small, sensible chunks. Favor modular delivery, low-risk changes, and clear verification. Do not dump the entire roadmap into one implementation pass.
