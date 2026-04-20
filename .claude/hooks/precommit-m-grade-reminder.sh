#!/usr/bin/env bash
# .claude/hooks/precommit-m-grade-reminder.sh
# PreToolUse hook — fires when Claude invokes a Bash tool whose command
# matches ^git commit.  Non-blocking: always exits 0.
# Purpose: remind the developer to run /code-reviewer when the staged diff
# meets M-grade criteria.

set -uo pipefail

# ── Bail fast if not a git commit invocation ──────────────────────────────
TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"
CMD=$(printf '%s' "$TOOL_INPUT" | grep -o '"command":"[^"]*"' | head -1 | sed 's/"command":"//;s/"//')
case "$CMD" in
  git\ commit*) : ;;   # expected path — continue
  *)            exit 0 ;;  # not a commit — no-op
esac

# ── Gather staged diff ────────────────────────────────────────────────────
STAGED_DIFF=$(git diff --cached 2>/dev/null) || exit 0
if [ -z "$STAGED_DIFF" ]; then
  exit 0
fi

TRIGGERED=0
REASON=""

# 1) Count staged files
FILE_COUNT=$(git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
if [ "${FILE_COUNT:-0}" -ge 2 ]; then
  TRIGGERED=1
  REASON="${REASON}staged files >= 2 (${FILE_COUNT}); "
fi

# 2) New def lines (lines starting with +, containing "def ")
if [ "$TRIGGERED" -eq 0 ]; then
  DEF_COUNT=$(printf '%s\n' "$STAGED_DIFF" | grep -c '^+.*\bdef ' 2>/dev/null || true)
  if [ "${DEF_COUNT:-0}" -ge 3 ]; then
    TRIGGERED=1
    REASON="${REASON}new def lines >= 3 (${DEF_COUNT}); "
  fi
fi

# 3) New import lines
if [ "$TRIGGERED" -eq 0 ]; then
  IMPORT_COUNT=$(printf '%s\n' "$STAGED_DIFF" | grep -c '^+.*\b\(import \|from .* import\)' 2>/dev/null || true)
  if [ "${IMPORT_COUNT:-0}" -ge 1 ]; then
    TRIGGERED=1
    REASON="${REASON}new import line(s) (${IMPORT_COUNT}); "
  fi
fi

# 4) Touches GOD_OBJECTS or editor/ui/
if [ "$TRIGGERED" -eq 0 ]; then
  STAGED_FILES=$(git diff --cached --name-only 2>/dev/null)
  GOD_MATCH=$(printf '%s\n' "$STAGED_FILES" | grep -E \
    '^(ui/main_window\.py|core/screen_recorder\.py|core/capture_backend\.py|core/gif_encoder\.py|editor/ui/)' \
    2>/dev/null || true)
  if [ -n "$GOD_MATCH" ]; then
    TRIGGERED=1
    REASON="${REASON}touches GOD_OBJECTS/CRITICAL_DIRS ($(printf '%s' "$GOD_MATCH" | head -1 | tr -d '\n')...); "
  fi
fi

# ── Emit reminder if triggered ────────────────────────────────────────────
if [ "$TRIGGERED" -eq 1 ]; then
  echo "M-grade change detected. Consider running \`/code-reviewer\` before finalizing this commit." >&2
  echo "  Reason: ${REASON%%; }" >&2
fi

exit 0
