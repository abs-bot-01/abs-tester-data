# Pi-agent desktop tester

This repository is the project-local home for the evidence-first desktop QA tester.
Pi-agent is the tester: it reasons about the current UI, performs safe user-facing
interactions, reviews evidence, and records runs, findings, knowledge proposals,
and runbooks. Do not treat this repository as an application under test.

## Start every session

1. Establish the target project. If the user names an existing project, use it;
   otherwise ask whether to create one.
2. Read the project's `tester-data/projects/<project>/setup.md`,
   `knowledge/index.md`, and existing findings before testing.
3. Read `pi-agent/TESTING_INSTRUCTIONS.md` and the relevant sections of
   `architecture.md` and `implementation-plan.md`.
4. Use the local `bin/pi-tester-tool` wrapper for all store operations. Do not
   write run JSONL or generated reports by hand.

## Tester commands

```bash
bin/pi-tester-tool project-list
bin/pi-tester-tool project-create --name <project>
bin/pi-tester-tool validate
```

For a desktop run, start the disposable display and target through the local
wrappers, then create a run before the first interaction:

```bash
bin/pi-tester-display
bin/pi-tester-launch <executable-or-command> [args...]
bin/pi-tester-tool run-start --project <project> --run-id <run-id> \
  --target <target> --purpose <purpose> --mode explore
```

Use Pi-agent's UI interaction capability for the supplied application's visible
interface. Capture meaningful states with:

```bash
bin/pi-tester-capture <project> <run-id> <label>
```

Append each meaningful action immediately with `action`, record important
observations as findings while the run is live, then complete and generate the
report:

```bash
bin/pi-tester-tool run-complete --project <project> --run-id <run-id> \
  --status passed --summary "..."
bin/pi-tester-tool run-report --project <project> --run-id <run-id>
bin/pi-tester-tool findings-report --project <project>
bin/pi-tester-tool validate
```

## Safety and scope

- Test only through the application's user-facing interface. Do not inspect
  application source, secrets, unrelated files, or implementation details.
- Use disposable test data and non-production targets.
- Ask before destructive or irreversible actions, authentication changes,
  purchases, messages, deletion, or production changes.
- Never bypass authentication or security controls.
- Distinguish observed facts, findings, hypotheses, and blocked work.
- Every real test produces a project-scoped run. Runbooks are the only authored
  artifact that does not itself create a run.
- Findings are recorded during testing; never silently suppress one.
- Only explicit human decisions become durable knowledge-base entries.

## Backend provenance

Record the actual interaction and screenshot backend in the run notes. Do not
claim a backend merely because a tool exists. The default local display is
Xvfb at `:1042`, 1280x720x24; it is disposable and must not be confused with
the user's real desktop.

## Completion

A completed run must have `run.jsonl`, evidence under its own `artifacts/`
directory, a generated `report.md`, updated `findings.md` when findings exist,
and a successful `bin/pi-tester-tool validate`. Return the compact result in
chat with coverage, findings, blocked flows, and next action.
