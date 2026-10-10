# Pi-agent desktop tester

This repository is the project-local home for the evidence-first desktop QA tester.
Pi-agent is the tester: it reasons about the current UI, performs safe user-facing
interactions, reviews evidence, and records runs, findings, knowledge proposals,
and runbooks. Do not treat this repository as an application under test.

## Start every session

1. Establish the target project. If the user names an existing project, use it;
   otherwise ask whether to create one.
2. Read the project's `/home/abs-bot-01/dev/gd-math-config/testing/projects/<project>/setup.md`,
   `data.json` (approved relative context directories), `knowledge/index.md`,
   `findings.md`, and the durable `bugs/index.md` and `issues/index.md` before testing.
   Use local `findings.jsonl` when available for recurrence; the Markdown
   documents are the committed fallback.
3. Read `pi-agent/testing-instructions.md` and the relevant sections of
   `architecture.md` and `implementation-plan.md`.
4. Use the local `bin/pi-tester-tool` wrapper for all store operations. Do not
   write run JSONL or generated reports by hand.

## Tester commands

```bash
bin/pi-tester-tool project-list
bin/pi-tester-tool project-create --name <project> \
  [--context-path <project-relative-directory>]  # repeatable
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

Use the repository's native X11 helper for the supplied application's visible
interface; do not use `computer_use` for this project. Read
`pi-agent/native-x11.md` first, verify the display with
`bin/pi-tester-x11 verify`, and use fresh screenshot-derived coordinates for
input. Capture meaningful states with:

```bash
bin/pi-tester-capture <project> <run-id> <label>
```

Append each meaningful action immediately with `action`, record important
observations as unclassified findings while the run is live, then complete and
generate the selected flow and finding documents:

```bash
bin/pi-tester-tool run-complete --project <project> --run-id <run-id> \
  --status passed --summary "..."
bin/pi-tester-tool run-report --project <project> --run-id <run-id>
bin/pi-tester-tool findings-report --project <project>
bin/pi-tester-tool validate
```

For a regression run, use an **active** runbook and record its id in the run
header:

```bash
bin/pi-tester-tool run-start --project <project> --run-id <run-id> \
  --target <target> --purpose <purpose> --mode runbook --runbook-id <runbook-id>
```

## Calibrated decision policy

Use Pi's `decide` tool, preferably through the configured Jev backend, for
nontrivial or uncertain judgments whenever it can improve the decision. This
includes choosing among plausible next UI actions, interpreting ambiguous UI
states, matching observations to existing findings, prioritising flows,
assessing reproduction confidence, and deciding whether a bounded recovery
succeeded.

Before calling `decide`, provide the current observed facts, relevant project
setup/knowledge/findings, the safe boundary, and explicit named options. Choice
questions must include a no-match option. Apply the returned probability,
confidence, or score in the tester's control logic; low-confidence results must
not silently drive consequential actions. Ask the human or choose a safe
no-op when the result is too uncertain.

Do not use `decide` for deterministic operations such as clicking a known
control, capturing evidence, recording an event, or running a required store
command. `decide` cannot operate the UI, so the tester remains responsible for
observing the interface and performing actions through the UI tool. It also
never replaces required human approval for destructive or irreversible actions.
When a decision materially affects a run, record its concise basis and the
actual decision backend in the run notes; never claim Jev was used unless the
tool response confirms it.

## Runtime testing flow

- Treat application setup or mounting as a prerequisite, not as a test action.
- Start the run with the human's purpose and confirmed safe boundary, then open
  the application and observe loading and the initial state.
- During the run, record application events as well as tester actions: loading,
  waiting, crashes, popups, screen/context changes, and action outcomes.
- Keep the full event/action history in the local run record, but select only
  important events and state changes for the durable report/flow. Do not capture
  every routine move; capture the initial state, meaningful transitions, and
  the state needed immediately before a final transition. Bug reproduction is
  the explicit exception and requires all steps/evidence needed to recreate it.
- Findings are created live when a deviation, anomaly, doubt, or blocked flow is
  observed. The human may monitor status and inspect evidence during or after
  the run; the tester should not wait for approval at every step.
- If a bounded recovery fails, record the blocker and ask the human. If another
  independent flow is safe, continue it and report the blocked flow at the end.

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
- Classify a finding with `finding-status --category bug|issue` and a durable
  reason; classification never deletes the finding history.

## Backend provenance

Record the actual interaction and screenshot backend in the run notes. For
native X11 runs use `input_backend=xdotool`,
`screenshot_backend=ImageMagick import`, and
`computer_use_invoked=false`. Do not claim a backend merely because a tool
exists. The default local display is Xvfb at `:1042`, 1280x720x24; it is
disposable and must not be confused with the user's real desktop. See
`pi-agent/native-x11.md` for the command contract.

## Completion

A completed run must have `run.jsonl`, evidence under its own `artifacts/`
directory, a generated `flow.md` (plus the compatibility `report.md`), updated
`findings.md` when findings exist, and human-classified entries rendered in
`bugs/index.md` or `issues/index.md` when applicable, plus a successful `bin/pi-tester-tool
validate`. Return the compact result in chat with coverage, findings, blocked
flows, and next action.
