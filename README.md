# abs-tester — desktop QA tester agent

A human-like QA tester that tests desktop applications through their
user-facing interface only, keeps durable evidence, and produces reports,
findings, runbooks, and knowledge in plain Open Knowledge Format (OKF v0.2)
Markdown — no database, no front-end, files a human can read anywhere.

This folder is the project's paper trail and the Pi-agent tester setup:
transcripts, `Notes.md`, the design contract (`architecture.md`), the
implementation plan, project instructions (`AGENTS.md`), Pi-agent execution
instructions, and the portable store/desktop wrappers.

**Status — Pi-agent setup available.** The repository can now be opened as a
Pi-agent project and used without a global agent workspace or installation.

## Quick start

```bash
cd /home/abs-bot-01/dev/abs-tester-data
bin/pi-tester-tool project-list
bin/pi-tester-tool project-create --name <project>
# Edit tester-data/projects/<project>/setup.md with the supplied app details.
bin/pi-tester-tool validate
```

For a desktop session, use `bin/pi-tester-display`, launch only the supplied
application with `bin/pi-tester-launch`, and follow `AGENTS.md` before creating
a run. Required host tools are Python 3, Xvfb, `xdpyinfo`, ImageMagick
(`import`, `convert`, `mogrify`), and `xdotool`.

---

## Current state (working)

- **Pi-agent project entry point**: `AGENTS.md` and
  `pi-agent/TESTING_INSTRUCTIONS.md` define the tester's workflow, safety
  boundary, evidence contract, and conversational behavior.
- **Portable store implemented** (`tester-tools.py`, pure Python stdlib):
  project-scoped runs (append-only JSONL + generated OKF reports), findings
  (fingerprint-merged recurrence), project + global knowledge, runbooks
  (freeze → execute), history search, and OKF validation.
- **Local wrappers included** under `bin/`: `pi-tester-tool`,
  `pi-tester-display`, `pi-tester-launch`, `pi-tester-capture`, and
  `pi-tester-stop`.
- **Documents in OKF v0.2**: every concept file carries frontmatter (`type`,
  title, description, tags, generated-provenance); `index.md` files are plain
  listings; links are relationships (finding ↔ run, runbook ↔ run).
- **Evidence pipeline**: screenshots on a disposable 1280×720 Xvfb display
  with the cursor overlaid, capped at 1280px; run reports embed evidence
  inline (multiple images render 4-per-table).
- **Launching works for supplied binaries and PATH commands** through the
  local Pi-agent launcher; extra arguments pass through to the application.

## Known limitation (top open item)

- **Drag gestures need validation.** The local Pi-agent wrappers provide the
  disposable display and evidence path, but reliable press-move-release drag
  behavior has not yet been validated on this setup. Verify calibrated
  window-relative coordinates on Xvfb before claiming drag coverage.

## Future direction

1. **Keep the tester portable** so Pi-agent and future harnesses can use the
   same local store, instructions, and desktop wrappers.
2. **Project-local workflow**: the user asks Pi-agent to work on a project; the
   agent uses the tester tool inside that project, and all runs, findings,
   evidence, and runbooks remain project-scoped.
3. **Global KB remains explicit**: cross-project facts live in the tester
   bundle, while project knowledge stays with its project.
4. **Prove the end-to-end loop** on a real non-production application before
   adding abstractions or a front-end.

### What that implies next (not started)

- Validate the Pi-agent wrappers against a real disposable desktop session.
- Resolve the drag-gesture limitation, then re-verify the GD-Math drag
  finding (needs calibrated reproduction).
- Later: builder-agent hand-off (tasks derived from findings) — deferred by
  design until the builder's shape is known.

## Where things live

| What | Where |
|---|---|
| Design contracts (OKF, runbook flow) | `architecture.md` |
| Implementation plan and status | `implementation-plan.md` |
| Pi-agent instructions and entry point | `AGENTS.md`, `pi-agent/TESTING_INSTRUCTIONS.md` |
| Portable store and wrappers | `tester-tools.py`, `bin/` |
| Project-scoped test data | `tester-data/projects/<project>/` |
| Session transcript (design history) | `open-knowledge-format-and-embedded-evidence-009.vtt` |