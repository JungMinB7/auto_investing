# Orchestrators Category Guide

## Scope

- Apply these rules to `skills/orchestrators/` and its descendants unless a deeper file overrides them.

## Purpose

- Store orchestrator skills that coordinate multiple downstream skills into a unified workflow.
- An orchestrator's job is flow control, not analysis. Heavy logic belongs in `references/`.

## Structure

- Keep the structure shallow: `skills/orchestrators/<skill-name>/SKILL.md`.
- Use lowercase hyphen-case for every orchestrator skill folder.
- Each orchestrator must include a `references/` folder with at least a pipeline and output-contract file.

## Rules

- Keep `SKILL.md` thin: it should define the persona, list the steps, and point to references.
- Do not duplicate logic that already exists in downstream skills; call them instead.
- Always document which downstream skills are called and in what order.
- Preserve anti-hallucination rules from all downstream skills in the orchestrator output.
- Define a graceful fallback for every downstream skill call that might fail.
- Keep orchestrators focused on a single domain workflow; do not create catch-all orchestrators.

## Quality Standard

- An orchestrator is judged by whether a user with only the ticker input gets a complete, consistent output.
- `references/` files must be concise and decision-oriented, not encyclopedic.
- Output contracts must specify section names, required content, and length limits.
