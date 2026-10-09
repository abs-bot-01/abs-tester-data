# Tester System — Implementation Plan

*Status: The original phases 0–4 and phase 5 tooling were implemented on `abs-bot-01` (2026-09-01). This repository now provides the portable Pi-agent entry point, local store, and desktop wrappers. Remaining: real-run validation of runbook execution and project-lifecycle prompts.*

*Basis: `architecture.md` (Design Document). This plan turns the design into ordered, concrete work. Each phase lists its goal, the tasks, the files touched, and the acceptance criteria. When this plan is done, the tester system matches the design.*

---

## 1. Starting point

A working POC already runs on `abs-bot-01`:

| Component | State today |
|-----------|-------------|
| Pi-agent tester with local desktop wrappers | Working locally; disposable Xvfb display `:1042`; launch/stop/capture/tool wrappers are in `bin/` |
| `tester-tools.py` | Working store with project, run, finding, knowledge, runbook, history, and validation commands; no POI command |
| Storage | `/home/abs-bot-01/dev/gd-math-config/testing/projects/<project>/` with `setup.md`, `data.json`, run folders, findings/category documents, knowledge, and runbooks |
| Agent instructions | `AGENTS.md` and `pi-agent/testing-instructions.md` with workflow, safety, finding policy, and storage rules |
| Existing data | Historical GD-Math data is the migration source; new projects are created with the complete layout |

The POC's concepts survive; the work below restructures storage, adds the missing documents, and changes the agent's workflow instructions to match the design.

### Explicitly out of scope

- **Tasks and the builder** — deferred until the builder agent's interface exists (design section 10).
- **Front-end** — permanently out of scope by design.
- **Store location** — project folders stay under `/home/abs-bot-01/dev/gd-math-config/testing/projects/`, outside this tester repository.
- **Global-KB internals** — the global KB exists as tester instructions/memory; only its minimal read/write path is built here.

---

## 2. Gap analysis

| Design item | Today | Work needed |
|-------------|-------|-------------|
| Project concept (§2) | Historical POC had no projects; one flat store tree | New project folders, project-create tooling, data migration |
| Project `index.md` (§2.2) | Nothing | New: launch/setup metadata maintained by tester |
| Run folder layout (§3.1) | Historical POC used separate journal, artifact, and report locations | One folder containing `run.jsonl`, `flow.md`, `report.md`, and `artifacts/` |
| Events (§3.2) | Historical records were action-only | Retain an append-only event stream with project/run identity and event-bound artifacts |
| Run report (§3.3) | Historical reports were written separately | `run-report` consolidates selected events into canonical `flow.md` and compatibility `report.md` |
| Transient result (§3.4) | Historical reports persisted the outcome as a separate concept | Communicate the overall result in chat; keep selected evidence and summary in the flow |
| Findings (§4) | Historical POC had POIs and one findings record | Findings are the only observation concept; human classification renders `bugs.md` or `issues.md` |
| Findings MD (§4.2) | JSONL only | `findings.md` with TOC, sections, captioned images, references, `proposed_for_kb` |
| Evidence policy (§4.4) | Evidence expected on findings | Make optional-but-encouraged in the machine record and the agent instructions |
| Project KB (§5.2) | Single `knowledge.md` | `knowledge/` folder with `index.md` + topic docs |
| Global KB (§5.1) | Mixed into workspace `knowledge.md` | Split out to tester-level memory file; minimal read path |
| Runbook (§6) | Nothing | Storage, format, validation, execution mode, freeze-from-exploration |
| Project data (§7) | No durable `data.json` contract | Store only existing, project-relative context directories in `context_paths`; validate before context retrieval and runs |
| Modes (§1.3) | `open-ended`/`fixed`/`reproduction` | Rename to `explore`/`continue`/`runbook`; wire continue and runbook behaviour |
| Project lifecycle (§2.3) | Not present | Agent asks "which project?", self-serves project creation |

---

## 3. Phases

Order matters: every later phase stores data inside a project, so projects come first. Each phase ends with the system usable end-to-end at that stage's scope.

### Phase 0 — Project scaffolding and data migration

**Goal:** every document lives inside `/home/abs-bot-01/dev/gd-math-config/testing/projects/<project>/`; the POC's historical data moves there intact.

Tasks:
1. Create the layout from design §2.1 for the existing GD-Math work as project `gd-math`.
2. Write `projects/gd-math/index.md`: executable path, launch command, Xvfb environment note, pointers to runbooks and KB index.
3. Create `data.json` with only a `context_paths` array; each entry is an existing directory path relative to the project directory (never a context file or absolute path). Validate paths against the tester data-root boundary.
4. Migrate runs: `journals/<run-id>/run.jsonl` → `projects/gd-math/runs/<run-id>/run.jsonl`; move that run's artifacts alongside as `artifacts/`; retire `artifacts/` and `reports/` top-level folders.
5. Rewrite artifact paths inside migrated `run.jsonl` files so evidence still resolves.
6. Merge `pois.jsonl` into `findings.jsonl` (map POI ids to findings via existing `poi_id` links; drop POI records).
7. Split `knowledge.md`: project-specific entries → `projects/gd-math/knowledge/…`; cross-project entries (tooling, environment behaviour, standing workflow decisions) → the tester-level global memory file. Create both `knowledge/index.md` files.
8. Delete the `poi` subcommand; keep historical ids only as references inside findings.

Files touched: `tester-tools.py` (paths, validate), `/home/abs-bot-01/dev/gd-math-config/testing/*` (migration script or one-off commands), workspace `TOOLS.md`.

Acceptance:
- `validate` passes against the new tree.
- Every evidence link in every migrated run resolves to a file inside its run folder.
- `pois.jsonl` no longer exists; the drag finding retains its history and references.

### Phase 1 — Run restructure

**Goal:** runs match design §3 exactly.

Tasks:
1. `run-start`: add required `--project`; write `project` into the header event; change `--mode` choices to `explore|continue|runbook`; create the run folder as `projects/<project>/runs/<run-id>/` with `artifacts/` inside it.
2. `action`: add `"event":"action"` field; treat `--evidence` paths as event-bound artifacts (store paths relative to the run folder; copy/rename captures into the run's `artifacts/`); keep `seq` semantics unchanged.
3. `run-complete`: unchanged semantics, but it must no longer write a separate file.
4. New `run-report`: consolidates `run.jsonl` into the selected `flow.md` and generated compatibility `report.md` per design §3.3 (header block, coverage narrative in sequence order, artifact references inline, footer). Regeneration is idempotent.
5. Update `bin/pi-tester-capture` so screenshots land directly in the active run's `artifacts/` and are returned with the path for event binding.
6. `validate` gains run checks: first/last event kinds, increasing `seq`, artifact paths resolving, exactly one header/footer.
7. Findings' run anchors switch to the new path form (`runs/<run-id>/run.jsonl#seq=N`).

Files touched: `tester-tools.py`, `bin/pi-tester-capture`, `AGENTS.md`, and `pi-agent/testing-instructions.md`.

Acceptance: a new run produces one folder with `run.jsonl`, `artifacts/`, and after `run-report` a `flow.md` plus compatibility `report.md`; the flow reads as a narrative with inline artifact references; validation passes.

### Phase 2 — Findings v2

**Goal:** one findings machine record, one findings intake index, and human-classified bug and issue documents.

Tasks:
1. Remove `poi-id` from the finding record; drop the POI vocabulary everywhere (instructions, TOOLS.md, reports).
2. `finding`: make `--images` accept `path|caption` pairs (each image carries a caption per design §4.2); add `--references` (run anchors etc.); add `--proposed-for-kb` flag storing the candidate text; evidence fields (`images`, `references`) become optional, with the record still storing whatever exists.
3. New `findings-report`: regenerates `projects/<project>/findings.md` plus the separate `bugs.md` and `issues.md` documents from `findings.jsonl` per design §4.2 — new findings remain in the intake document until human classification, then are removed from it and rendered in the appropriate category document with the description, steps, expected/observed, captioned images, references, recurrence line, and any `proposed_for_kb` block. Regeneration is idempotent.
4. New `finding-status`: human-triage status and category updates (`new|needs-retest|confirmed|not-a-bug|suppressed|fixed` plus `bug|issue`) are recorded with a reason, never deleting anything.
5. Findings files live in the project folder; each tester observation starts as `finding`, then the human classifies it as `bug` or `issue`. Per-project fingerprints keep the same app finding as one record within a project.
6. The run flow emits findings during the run — no "after run completes" step in the workflow instructions.

Files touched: `tester-tools.py`, `AGENTS.md` (finding policy section rewrite: evidence optional but encouraged, proposals allowed), `TOOLS.md`.

Acceptance: new observations first appear in `findings.md`; human classification as `bug` or `issue` moves the rendered detail to `bugs.md` or `issues.md`; each category document renders a TOC with clickable sections; the migrated drag anomaly appears with its captioned image and run anchor; a status and category change is visible in both JSONL and Markdown without deleting history.

### Phase 3 — Knowledge Base restructure

**Goal:** project KB as folder + index; global KB separated; findings can propose.

Tasks:
1. Migrate `knowledge.md` per design §5: project facts → `projects/gd-math/knowledge/<topic>.md`; cross-project entries → tester-level global knowledge file (in the tester's standing memory/instructions area).
2. `kb-add` becomes project-scoped by default: writes into the project's `knowledge/` folder, appends the topic document to that project's `knowledge/index.md`, and enforces the source + review-date pattern on every entry. `--global` is explicit for cross-project knowledge.
3. New `kb-propose --finding-id …`: marks a finding's `proposed_for_kb` (already stored by Phase 2) as pending.
4. New `kb-accept --finding-id …` / `kb-reject --finding-id …`: converts (or drops) a proposal into a KB entry **only on the human's explicit instruction** — the command is only ever invoked after the human confirms in chat; acceptance records source = the human.
5. `history`/query covers the new locations.

Files touched: `tester-tools.py`, `AGENTS.md`, `IDENTITY.md`/`memory` (global KB home), `TOOLS.md`.

Acceptance: project KB loads via index at session start; a proposed KB candidate from the drag finding can be accepted into `known-non-issues.md` with source and review date; global and project entries never mix.

### Phase 4 — Runbook

**Goal:** runbooks stored, validated, executed, and creatable from an exploration.

Tasks:
1. `runbook-create --project --runbook-id --file` (or from a `--source-run` to freeze an exploration): writes `projects/<project>/runbooks/<runbook-id>.md` in the design §6.2 format (bold keys, numbered tests, mandatory `expected`, no target field).
2. `runbook-validate`: checks structure — test ids unique and ordered, every test has objective/steps/expected, `status` present; only `active` runbooks are executable.
3. `run-start` with `--mode runbook --runbook-id <id>`: the run header records the runbook id; the tester executes test-by-test, emitting one `action` event per step; `validate` may cross-check that a runbook-mode run covered each test id.
4. Version rule: editing steps bumps `version`; `retired` runbooks remain readable but unexecutable.
5. `runbook-freeze --run-id --tests T1,T2…`: generates a draft runbook from a completed run's events, for human editing — this is the "freeze this exploration" capability; per the exception rule, creating a runbook produces no run record.
6. Report results test-by-test in chat; the run `flow.md` groups selected events by test id when runbook metadata is available.

Files touched: `tester-tools.py`, `bin/tester-tool` (no change needed — same wrapper), `AGENTS.md` (runbook workflow, exception rule, collaboration flow), `TOOLS.md`.

Acceptance: the drag anomaly can become regression test T2 in a `gd-math-core` runbook; a runbook-mode run produces a run document with per-test pass/fail; freezing the existing GD-Math POC run yields a valid draft runbook.

### Phase 5 — Project lifecycle behaviours

**Goal:** conversations are project-first (design §2.3).

Tasks:
1. `project-create --name` scaffolds the full folder set and a starter `index.md`; `project-list` lists projects; `validate` is project-aware.
2. Agent instructions updated: every session starts by establishing project context; with no context the tester asks "existing project or new one?"; when handed a bare binary, the tester creates the project first, records launch details in `setup.md`, then proceeds.
3. `run-start` refuses to run without a project; the runbook resolves its target from the project's `setup.md` at execution time.
4. The "which project?" prompt is part of the conversational instructions so it is rehearsed, not improvised.

Files touched: `tester-tools.py`, `AGENTS.md`, and `pi-agent/testing-instructions.md`.

Acceptance: starting a session without project context produces the project question; handing over a new binary produces a new project with a populated `index.md`; every document created afterwards lands inside that project.

---

## 4. Cross-cutting work

- **`tester-tools.py`** is the single store implementation; all phases touch it. Current subcommands: `project-create`, `project-list`, `run-start`, `action`, `run-complete`, `run-report`, `finding`, `finding-status`, `findings-report`, `kb-add`, `kb-propose`, `kb-accept`, `kb-reject`, `runbook-create`, `runbook-freeze`, `runbook-validate`, `history`, and `validate`. The POI and separate-report paths are removed.
- **Agent instructions** (`AGENTS.md`, `TOOLS.md`, `RUNBOOK.md`) are updated in the same phase as the tooling they describe — the tester must never be instructed to use a command that no longer exists, and vice versa.
- **Migration is one-way and scripted.** A single migration step (Phase 0) moves all existing data; no dual-format period. The pre-migration tree is archived, not deleted.
- **Naming decision:** run folders are `runs/<run-id>/` with the selected flow as `flow.md` and a generated compatibility copy as `report.md`.
- **Media delivery:** screenshots continue to be surfaced inline in chat via the existing allowed-roots mechanism; artifact copies inside project runs do not change that path.

---

## 5. Verification checklist (end of implementation)

Run end-to-end after all phases:

1. Ask for a test without project context → tester asks for a project or offers to create one.
2. Hand over a new binary → tester creates a project, fills `setup.md`, then runs an explore-mode session.
3. During the run: events appear in `run.jsonl` with screenshots inside the run's `artifacts/`; findings are emitted during (not after) the run.
4. After the run: chat shows the outcome and the tester links exactly two primary documents — `runs/<run-id>/flow.md` and `findings.md`. `report.md` remains a compatibility copy.
5. `findings.md` shows a TOC, and each finding carries description, steps, expected/observed, captioned images, and run references.
6. Tell the tester a fact → it lands in the project KB (or global KB, if the human says it applies everywhere) with source and review date; a finding-proposed candidate can be accepted or rejected explicitly.
7. Ask to freeze the exploration → a draft runbook appears; the authoring produced no run document.
8. Run the runbook → one event per test step, pass/fail per test, results only in the run document.
9. Say "continue" → the tester reads the latest run, replicates its last steps, and resumes.
10. `validate` passes; every evidence link in every run and finding resolves; no POI records or legacy separate-report paths remain.
11. Deferred items remain untouched: no task storage, no builder coupling, no front-end, no repo migration.

---

## 6. Deferred decisions (recorded, not built)

| Item | Where it returns |
|------|------------------|
| Task document and builder coupling | When the builder agent's interface is defined |
| Global-KB richer tooling (beyond a memory file) | Interface discussion, post-POC validation |
| Repository layout for project folders | When projects are version-controlled |
| Runner/creator agent split | If one-agent runbook authoring proves awkward |