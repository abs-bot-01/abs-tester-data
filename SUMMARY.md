# Simple English Summary of `abs-tester-docs`

## What this project is

`abs-tester-docs` describes an AI-powered desktop QA tester called **Tester**.

Tester behaves like a careful human tester:

- Opens applications through their normal user interface.
- Clicks, types, and interacts with them.
- Records what it does.
- Takes screenshots as evidence.
- Reports bugs, unusual behavior, and blocked actions.
- Remembers important facts for future testing.
- Can repeat tests later as regression tests.

It is designed to test applications without reading their source code.

## How testing works

Each testing session belongs to one **project**, usually one application.

There are three testing modes:

1. **Explore** — freely investigate the application.
2. **Continue** — read the previous session and continue from where it stopped.
3. **Runbook** — follow a fixed list of repeatable tests.

Every real test session creates a **run record**. Creating a runbook does not create a run record.

### Runtime flow of a test

1. Application setup or mounting happens first; it is a prerequisite, not a test interaction.
2. The human starts a run with its purpose and safe boundary.
3. The tester opens the application, observes loading and the initial state, then explores or executes the selected flow.
4. Every meaningful action **and application event** is recorded locally. This includes loading, waiting, crashes, popups, screen changes, and tester actions.
5. Only important events and state/context changes are selected for the Markdown flow/report. Routine moves stay in local event storage. Evidence is sampled at meaningful boundaries rather than captured for every move.
6. Findings are recorded live when a deviation, anomaly, doubt, or blocker appears. Bug reproduction is the exception and gets all steps and evidence needed to recreate it.
7. The tester continues safe independent flows when one flow is blocked; otherwise it performs one bounded recovery or asks the human. The human can monitor status and inspect evidence during or after the run without approving every step.
8. At completion, the tester generates the selected flow/report, findings document, and chat summary. Human triage determines whether findings are retested, treated as bugs, corrected with context, or promoted to knowledge.

## What gets stored

The system keeps seven project-scoped document/configuration types, plus the global knowledge document.

### 1. Runs

A run is the complete history of one test session.

It stores:

- Every important action and application event.
- What was expected.
- What actually happened.
- Whether the action passed, failed, was blocked, or was skipped.
- Screenshots and other evidence.
- A generated human-readable report.

The raw events are stored as local JSONL. The durable selected flow is stored in `flow.md`; `report.md` is retained as a compatibility copy.

### 2. Findings

Findings are the important things a human should review, such as:

- Bugs.
- Anomalies.
- Doubts.
- Blocked flows.
- Possible misunderstandings about the application.

Findings are recorded during testing, not only at the end.

If the same problem appears again, the system updates the existing finding instead of creating a duplicate. It keeps a recurrence count and history.

A finding can be marked as:

- New
- Needs retest
- Confirmed
- Not a bug
- Suppressed
- Fixed

The human decides the final status.

`findings.md` is the intake and review index. Every new tester finding is added there first with category `finding`.

The human then reviews it and classifies it with `finding-status`:

- Confirmed bug → category `bug`, rendered in `bugs/index.md`.
- Doubt, anomaly, or blocker → category `issue`, rendered in `issues/index.md`.

For example:

```bash
bin/pi-tester-tool finding-status --project <project> \
  --finding-id <finding-id> --status confirmed --category bug \
  --reason "Confirmed application defect"
```

The status command regenerates the documents, so the reviewed finding is
removed from `findings.md` and appears in its separate category document.

### 3. Knowledge base

The knowledge base contains facts that should affect future testing.

There are two levels:

- **Project knowledge** — facts about one application.
- **Global knowledge** — facts that apply to all applications.

Examples:

- A known application rule.
- A known non-bug.
- An environment limitation.
- Something the tester should always check.
- Something it should stop reporting.

The tester can suggest knowledge, but the human must explicitly approve it before it becomes permanent.

### 4. Runbooks

A runbook is a repeatable test plan.

It contains:

- Test names and IDs.
- Steps to perform.
- Expected results.
- Required evidence.
- A version and lifecycle status.

A useful exploration can be “frozen” into a runbook and replayed later. This turns exploratory testing into a regression test.

### 5. Project data

Each project has a `data.json` file containing only `context_paths`. These are
folder-relative paths to existing, approved context directories. The tester
validates them before context retrieval and before starting a run. The file
contains no absolute paths, event history, or human-facing document content.

### 6. Bugs

`bugs/index.md` is the categorized document containing confirmed or suspected application bugs. It is generated from findings whose category is `bug`.

### 7. Issues

`issues/index.md` is the categorized document containing anomalies, doubts, blockers, and other non-bug findings. It is generated from findings whose category is `issue`.

## Evidence and reports

Screenshots are taken on a disposable **1280×720 virtual display**.

The screenshots include the mouse cursor, which makes pointer actions easier to understand.

Evidence is stored inside the relevant run folder and embedded into:

- Run flows/reports.
- Finding reports.

The final human-facing documents use plain Markdown and the Open Knowledge Format, so they can be read without a special database or web application.

## Safety rules

Tester should:

- Use only the application’s user-facing interface.
- Avoid source-code access.
- Use safe test accounts and non-production environments.
- Ask before destructive or irreversible actions.
- Never send messages, make purchases, delete data, or change production systems without confirmation.
- Never bypass authentication or security controls.
- Clearly separate facts from guesses.

## Current implementation

The repository now contains a portable **Pi-agent tester** setup.

The implementation includes:

- A Python tool called `tester-tools.py`.
- Project-scoped storage.
- Append-only JSONL run logs.
- Generated Markdown flows/reports.
- Screenshot capture.
- Finding recurrence tracking.
- Project and global knowledge.
- Runbook creation and validation.
- History search.
- Data validation.
- Local disposable Xvfb desktop support using the repository's native X11
  helper (`xdotool` input and ImageMagick `import` screenshots).
- Local wrappers for launching apps, stopping apps, and taking screenshots.
- Project `data.json` validation and separate human-classified bug/issue
  documents.
- Pi-agent instructions in `AGENTS.md` and `pi-agent/testing-instructions.md`.

The setup is local to this repository and does not require a gateway, global
agent profile, or system-wide skill installation.

## Main known limitation

The most important current limitation is:

> Drag-and-drop actions do not work reliably on the virtual display.

Because of this, the tester can observe drag-related problems but cannot always reproduce them itself. Fixing reliable press–move–release dragging is the next major technical task.

## Planned future work

The longer-term direction is to keep this as a reusable package that can work
with Pi-agent and other agent systems.

The package should provide:

- The tester instructions.
- The storage tools.
- Screenshot and desktop control support.
- Project-local test data.
- Shared global knowledge.

Tasks for a future “builder” agent are intentionally postponed until the builder’s interface is defined.

## Overall idea

The project is built around this simple cycle:

1. **Explore** an application.
2. **Record** every meaningful action and screenshot.
3. **Identify** important bugs and uncertainties.
4. **Discuss** them with the human.
5. **Save approved knowledge** for later.
6. **Create runbooks** for repeatable regression testing.
7. **Run the tests again** and track whether problems return.

In short, it is an evidence-first QA tester that learns from human decisions while keeping all testing history in readable files.
