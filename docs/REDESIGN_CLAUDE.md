# Cartography Redesign — AI Assistant Guide

## Purpose
This branch tracks the cartography redesign plan. It is documentation-only.
Do NOT modify existing source code on this branch.

## Key Context
- Cartography is a CNCF sandbox project mapping infrastructure into Neo4j
- The redesign covers 4 quick-ROI items + 17 architectural features
- Plan lives in `docs/REDESIGN.md`
- Branch merges cleanly from master (additive-only changes)

## Rules for This Branch
1. Only add/edit files under `docs/` — never touch `cartography/` or `tests/`
2. Keep `docs/REDESIGN.md` as the single source of truth for the plan
3. When updating the plan, preserve the phase/feature numbering scheme
4. Success criteria are mandatory for every feature — don't add features without them
5. To implement a feature, create a separate feature branch off master, not off this branch

## Feature Implementation Workflow
When starting work on a feature:
1. Read the relevant section in `docs/REDESIGN.md` for context and success criteria
2. Branch off `master` (not this branch)
3. Name branch: `redesign/<feature-number>-<short-name>` (e.g., `redesign/0.1-async-ingestion`)
4. After merging the feature PR, update `docs/REDESIGN.md` on this branch to mark it done
