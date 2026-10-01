# abs-tester — desktop QA tester agent

A human-like QA tester that tests desktop applications through their
user-facing interface only, keeps durable evidence, and produces reports,
findings, runbooks, and knowledge in plain Open Knowledge Format (OKF v0.2)
Markdown — no database, no front-end, files a human can read anywhere.

This folder is the project's paper trail: transcripts in `transcript/`,
`Notes.md`, the design contract (`document-contracts.md`), the implementation
plan, and the collected OpenClaw setup (`openclaw-tester-setup/`).

**Status as of 2026-09-02 — parked for the day.** This README records where
the system stands and where it is going.

---

## Current state (working)

- **Deployed and exercised on `abs-bot-01`** as an OpenClaw agent (`tester`),
  workspace at `~/.openclaw/workspace/tester`, with an approved-wrapper exec
  allowlist as the tool boundary and the `cua-computer` provider for desktop
  control.
- **Store implemented** (`tester-tools.py`, 18 commands, pure Python stdlib):
  project-scoped runs (append-only JSONL + generated OKF reports), findings
  (fingerprint-merged recurrence), project + global knowledge, runbooks
  (freeze → execute), history search, and a `validate` that also enforces OKF
  conformance. Machine records inside (JSONL), human documents outside (MD).
- **Documents in OKF v0.2**: every concept file carries frontmatter (`type`,
  title, description, tags, generated-provenance); `index.md` files are plain
  listings; links are relationships (finding ↔ run, runbook ↔ run).
- **Evidence pipeline**: screenshots on a disposable 1280×720 Xvfb display
  with the cursor overlaid, capped at 1280px; run reports embed evidence
  inline (multiple images render 4-per-table); findings TOC has working
  anchors and descriptions.
- **Launching works for anything**: supplied binaries and system-installed
  apps (`tester-launch mypaint` resolves via PATH; extra args pass through,
  e.g. Godot `--resolution 1280x720`). Verified with a real MyPaint launch.
- **OpenClaw dashboard** usable locally without login (loopback, auth none).
- All prior gd-math exploration, findings, and the POC runbook flow have been
  validated end-to-end on real sessions.

## Known limitation (top open item)

- **Drag gestures do not work.** The tester cannot currently perform
  press-move-release drags against the virtual display, so drag-driven
  scenarios (e.g. the GD-Math answer-card interaction) can only be observed,
  not exercised. Fixing reliable drag support (press–move–release with
  calibrated window-relative coordinates on Xvfb) is the first item to resume.

## Future direction

1. **Become part of the `abs-seed` package**, deployed to the shared store so
   that **all harnesses and agents can utilise it just like a simple tool** —
   not a bespoke OpenClaw agent but a portable capability.
2. **Workflow**: the user asks any agent to work on a certain project; the
   agent uses the tester tool *inside that project*, and everything is
   stored and recorded there (project-scoped runs, findings, evidence,
   runbooks — the store already enforces this).
3. **Global KB lives in the shared store**, editable by everyone / all
   instances of the tool — standing decisions and cross-project knowledge
   shared across agents and machines, while per-project knowledge stays
   project-local.
4. **Harness-agnostic**: OpenClaw, Pi, or any other agent harness should be
   able to use the tool and its testing instructions as-is (the tester
   persona and rules travel with the package — e.g. as an Agent Skill — and
   the store is plain files any agent can drive).

### What that implies next (not started)

- Extract the tester into a self-contained, harness-neutral package (store
  script + persona/instructions + capture driver) deployable from the shared
  store; per-harness glue reduced to a thin adapter.
- Data-location split for package deployment: scripts travel with the
  package, the store and the global KB live in the shared store.
- Resolve the drag-gesture limitation, then re-verify the GD-Math drag
  finding (needs calibrated reproduction).
- Later: builder-agent hand-off (tasks derived from findings) — deferred by
  design until the builder's shape is known.

## Where things live

| What | Where |
|---|---|
| Design contracts (5 documents, OKF, runbook flow) | `document-contracts.md` |
| Implementation plan and status | `implementation-plan.md` |
| Collected OpenClaw setup (workspace, wrappers, service, config) | `openclaw-tester-setup/` |
| Working deployment | `abs-bot-01:~/.openclaw/workspace/tester/` |
| Session transcripts (design history) | `transcript/*.vtt` |