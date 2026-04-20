---
phase: 7-8
completed: 2026-04-21
status: done
---

# Hooks & MCP Setup — XGif

## Summary

Phase 7-8 installed one non-blocking PreToolUse hook
(`precommit-m-grade-reminder.sh`) that fires when Claude invokes a Bash tool
with a `git commit` command. It inspects the staged diff and prints a reminder
to run `/code-reviewer` when any M-grade indicator is present (2+ staged files,
3+ new `def` lines, any new import line, or a touch of GOD_OBJECTS /
`editor/ui/`). The hook always exits 0 and never blocks the commit. The
`.gitignore` received two new patterns (`_workspace/` and `_workspace.prev-*/`)
required by the workspace cleanup protocol. No MCP servers were installed — the
project's tooling needs are fully met by the existing `get-api-docs` skill and
local Python/ruff toolchain. The optional `postwrite-s-grade-ruff.sh` hook was
skipped (see rationale below).

## Hooks Installed

| Hook file | Event | Matcher | Purpose |
|-----------|-------|---------|---------|
| `.claude/hooks/precommit-m-grade-reminder.sh` | PreToolUse | `Bash` | Detects M-grade commit patterns and prints a non-blocking reminder to run `/code-reviewer` |

Trigger criteria (any one sufficient):
- Staged file count >= 2
- New `def ` lines in staged diff >= 3
- New `import` / `from ... import` lines in staged diff >= 1
- Staged files touch `ui/main_window.py`, `core/screen_recorder.py`,
  `core/capture_backend.py`, `core/gif_encoder.py`, or any path under
  `editor/ui/`

## Hooks Skipped

| Candidate | Decision | Rationale |
|-----------|----------|-----------|
| `postwrite-s-grade-ruff.sh` | SKIP | Solo developer with ruff already in `settings.json` allow-list; S-grade tasks are already defined to run `ruff check` directly in the main session. Adding a PostToolUse hook on every Edit would fire on `.md`, `.json`, and `.sh` files where ruff is a no-op, generating noise without value. |
| `ownership-guard.sh` (PreToolUse Write\|Edit) | SKIP | Explicitly rejected in Phase 5 (Option A+). Text-policy enforcement only. Do not reinstall unless the user requests it. |

## MCP Servers

None installed.

Rationale by candidate:

| Candidate | Decision | Rationale |
|-----------|----------|-----------|
| `chrome-devtools-mcp` | SKIP | XGif has no web UI. Not applicable. |
| `context7` | SKIP | Python/wxPython docs lookups are already handled by the `get-api-docs` skill (global CLAUDE.md). Adding a second lookup mechanism for the same purpose creates redundancy. Revisit only if `get-api-docs` proves insufficient for wxPython 4.2 specifics. |
| `firecrawl` / `exa` | SKIP | No web-crawling requirement in the XGif workflow. |
| `@anthropic/mcp-server-github` | SKIP | Solo developer, no PR review workflow, no CI integration. |
| `mcp-server-sqlite` / `-postgres` | SKIP | XGif uses `config.ini`, not a database. |

## Settings.json Changes

Added `hooks` section (top-level key, before `permissions`):

```json
"hooks": {
  "PreToolUse": [
    {
      "matcher": "Bash",
      "hooks": [
        {
          "type": "command",
          "command": "bash .claude/hooks/precommit-m-grade-reminder.sh"
        }
      ]
    }
  ]
}
```

No permissions were added or removed. The existing `Bash(git commit*)` allow
entry already covers the commit command; the hook runs as a side-channel
observer and does not require a new permission entry.

## .gitignore Changes

Added under `# Project specific` block:

```
# Harness workspace (transient agent output — never commit)
_workspace/
_workspace.prev-*/
```

## Verification Targets

Phase 9 (final-validate) should confirm:

| File | Check |
|------|-------|
| `.claude/hooks/precommit-m-grade-reminder.sh` | File exists, is executable (`-x`), shebang is `#!/usr/bin/env bash`, exits 0 on all code paths |
| `.claude/settings.json` | Valid JSON; `hooks.PreToolUse[0].matcher == "Bash"`; `hooks.PreToolUse[0].hooks[0].command` points to the correct script path; `permissions` block unchanged |
| `.gitignore` | Contains `_workspace/` and `_workspace.prev-*/` |
| `.claude/rules/workflow-orchestrator.md` | `## Hook Invocation Hints` section references `precommit-m-grade-reminder` — confirm hook behaviour matches spec |
| `.claude/rules/workflow-orchestrator.md` | `## Workspace Entry Cleanup Protocol` references `_workspace/` and `_workspace.prev-*` — confirm `.gitignore` patterns match exactly |

Full harness verification targets (carry-over from Phase 6):

- `.claude/rules/workflow-orchestrator.md` — no meta-vocabulary leaks, ≤ 200 lines
- `.claude/rules/harness-invocation.md` — no meta-vocabulary leaks, ≤ 200 lines
- Both rule files load without YAML frontmatter errors (no `---` block at top)
- GOD_OBJECTS list is 4 files in both rule files and in the hook script

## Context for Next Phase

Phase 9 (final-validate) needs:

1. **Hook file**: `D:/ProjectX/XGif_v5/.claude/hooks/precommit-m-grade-reminder.sh`
   — execute permission set (`chmod +x` applied). Verify with `test -x`.
2. **settings.json**: `D:/ProjectX/XGif_v5/.claude/settings.json`
   — `hooks` key present, JSON valid.
3. **.gitignore**: `D:/ProjectX/XGif_v5/.gitignore`
   — `_workspace/` and `_workspace.prev-*/` present.
4. **No MCP servers installed** — no `mcpServers` key in settings.json.
5. **No `postwrite-s-grade-ruff.sh`** — intentionally omitted; do not flag as missing.
6. **No ownership-guard.sh** — intentionally omitted (Phase 5 decision); do not flag as missing.
7. Carry-over rule files to re-verify: `workflow-orchestrator.md` (199 lines),
   `harness-invocation.md` (193 lines).

## Files Generated

- `D:/ProjectX/XGif_v5/.claude/hooks/precommit-m-grade-reminder.sh`
- `D:/ProjectX/XGif_v5/docs/xgif-setup/06-hooks-mcp.md`

## Files Modified

- `D:/ProjectX/XGif_v5/.claude/settings.json` — `hooks` section added
- `D:/ProjectX/XGif_v5/.gitignore` — `_workspace/` and `_workspace.prev-*/` added

## Escalations

[NOTE] The PreToolUse hook fires on every Bash tool invocation and does a fast
early-exit (`^git commit` check via grep on `$CLAUDE_TOOL_INPUT`). For all
non-commit Bash calls the script exits in under 1ms. No performance concern.

[NOTE] `postwrite-s-grade-ruff.sh` skipped per Phase 6 handoff default
recommendation and confirmed by project context: ruff is already in the
allow-list and run by the main session in the S-grade step. Installing a
PostToolUse hook would fire noisily on every Edit regardless of file type.

[NOTE] No MCP servers installed. The `get-api-docs` skill (global CLAUDE.md)
covers the only plausible MCP use-case (Python/wxPython docs). Re-evaluate if
the user later expresses a need for persistent web search or GitHub integration.

[NOTE] The `Bash(git commit*)` permission already exists in the allow-list;
the new hook registration does not require any permission change.

## Next Steps

Proceed to Phase 9: invoke the `phase-validate` agent to run the full harness
consistency and simulation check against all shipped artifacts.
