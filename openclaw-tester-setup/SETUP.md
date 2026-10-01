# OpenClaw tester setup — collected files

Everything needed to configure an OpenClaw instance to act as the desktop QA
tester, collected from the working deployment on `abs-bot-01` (2026-09-01).
What to do with this folder is deliberately undecided; this is the inventory.

## What each file is

| File | Where it lives on the deployed host | Purpose |
|---|---|---|
| `workspace/AGENTS.md` | `~/.openclaw/workspace/tester/AGENTS.md` | Agent instructions: workflow, run/finding/KB rules, runbook modes |
| `workspace/TOOLS.md` | `~/.openclaw/workspace/tester/TOOLS.md` | Tool reference: store layout, capture rules, OKF conventions |
| `workspace/RUNBOOK.md` | `~/.openclaw/workspace/tester/RUNBOOK.md` | Example interaction runbook (how a session flows) |
| `workspace/IDENTITY.md` | same | Agent identity (name, emoji, theme) |
| `workspace/SOUL.md` | same | Standing persona rules |
| `workspace/USER.md` | same | Who the human is (context for the agent) |
| `workspace/HEARTBEAT.md` | same | Heartbeat behaviour |
| `workspace/tester-tools.py` | same | The store + contract enforcer: 18 commands, pure Python stdlib. Owns `tester-data/` next to itself |
| `workspace/bin/tester-tool` | `workspace/bin/` | Approved exec wrapper → `tester-tools.py` (allowlist mode) |
| `workspace/bin/tester-launch` | `workspace/bin/` | Restricted launcher for test binaries (Downloads/test-apps only) |
| `workspace/bin/tester-stop` | `workspace/bin/` | Stops an app launched by `tester-launch` |
| `workspace/bin/tester-capture` | `workspace/bin/` | Screenshot + cursor overlay into the active run's `artifacts/` |
| `workspace/bin/tester-node-display` | `workspace/bin/` | Starts the disposable 1280×720 Xvfb display (`:1042.0`) and runs the desktop node |
| `systemd/openclaw-node.service` | `~/.config/systemd/user/openclaw-node.service` | User service: Xvfb + desktop node via dbus-run-session |
| `config/openclaw.config.excerpt.json` | `~/.openclaw/openclaw.json` (subset) | The exact config that turns an OpenClaw agent into the tester |

## The config that makes it a tester (`config/openclaw.config.excerpt.json`)

Three pieces, copied verbatim from the deployed `openclaw.json`:

1. **`agents.entries.tester`** — the agent entry: workspace path, model
   (OpenRouter preset `abs-medium` with `abs-small` fallback), tool profile
   `minimal` + `alsoAllow`, **filesystem locked to the workspace**
   (`tools.fs.workspaceOnly`), and **exec in allowlist mode** whose PATH is
   prepended with the workspace `bin/` — this is the security boundary: the
   agent can only run the approved wrappers.
2. **`gateway`** — local mode, loopback bind, auth `none` (dashboard usable
   locally without login).
3. **`plugins.entries.cua-computer`** — the computer-use provider for
   desktop control, enabled.

## Install order (for reference; not executed here)

1. Create the user (`abs-bot-01`) and copy `workspace/` to
   `~/.openclaw/workspace/tester/`.
2. Install `systemd/openclaw-node.service` into
   `~/.config/systemd/user/` and `systemctl --user enable --now openclaw-node.service`.
3. Merge the config excerpt into `~/.openclaw/openclaw.json`
   (the excerpt is JSON — OpenClaw also accepts JSON5).
4. Install host packages: `Xvfb`, `xdotool`, ImageMagick (`import`,
   `convert`, `mogrify`), `xdpyinfo` (x11-utils), `dbus-run-session`.
5. Register the desktop node in OpenClaw and approve the `cua-computer`
   provider and the exec wrappers.

## Notes collected along the way

- `agents.entries.tester.memory.search.extraPaths` still references
  `tester-data/knowledge.md` — a leftover from the pre-v2 layout (knowledge
  now lives at `tester-data/knowledge/index.md`). Harmless (file missing =
  ignored) but worth fixing in whichever deployment this folder becomes.
- The workspace moved once to `/home/abs-bot-01/.openclaw/workspace/tester`
  (inside the allowed media roots); a compatibility symlink
  `~/.openclaw/tester-workspace` → that path still exists and is referenced
  by `exec.pathPrepend`.
- `tester-data/` (the actual test data) is deliberately **not** collected
  here — this folder is setup-only. A live copy exists on `abs-bot-01`
  (`~/.openclaw/workspace/tester/tester-data/`).