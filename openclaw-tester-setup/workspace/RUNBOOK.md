# Tester POC runbook

## Human conversation examples

- `Run the same test again and check whether finding finding-... reproduces.`
- `Show me the last report and the screenshots.`
- `Remember that this development level is intentionally volatile; do not escalate it unless it blocks a user journey.`

The agent should ask for the target and purpose only when missing. It should not ask for permission for normal safe exploration, but it must pause for destructive, external, production, purchase, messaging, deletion, or authentication-bypass actions.

## Expected run lifecycle

1. Establish the project (existing or newly created via `project-create`; record launch details in the project `setup.md`).
2. `run-start` (with `--project` and `--mode explore|continue|runbook`) before the first app interaction.
3. Capture a state before/after each meaningful action; append the event immediately with the artifact bound to it.
4. Record findings as soon as they matter — evidence optional but strongly encouraged; classify only with what was observed.
5. On repeat occurrences, update the existing finding's recurrence (fingerprint merge) instead of creating a duplicate.
6. Complete the run, state the outcome in chat, and generate the two links: `run-report` → `runs/<run-id>/report.md`, `findings-report` → `findings.md`.
7. Promote only explicit human decisions to knowledge: project topics via `kb-add --project`, cross-project facts via `kb-add --global`. Findings may propose; only the human accepts or rejects.
8. Runbooks: execute stored runbooks test-by-test, or freeze an exploration into a draft runbook on the human's request (no run document for authoring).

## Evidence delivery

Persistent reports use relative paths for auditability. Chat responses summarize findings inline and attach important screenshots as structured media so they render directly in the Control UI.
