---
phase: 6
completed: 2026-04-20T25:00:00Z
status: done
advisor_status: pending
---

# Skill Specs — XGif (Phase 6 Internal Handoff)

## Summary

Phase 6 (skill-forge) produced the orchestrator rule files that encode every
decision made in Phase 3-5. Per the Phase 5 Advisor Resolution (OPT-C), the
rule files own the Task-invocation sequences — the shipped harness `skill.md`
files are left untouched as reference documents while the main session drives
Task calls directly from the rules. Because the primary file approached the
200-line budget once the full prelude bodies and Task sequences were
consolidated, the Phase 5-authorized split was used: `workflow-orchestrator.md`
(routing/grading/cleanup/flags/write policy/retry/hooks) and
`harness-invocation.md` (per-trigger Task tables + 5 prelude bodies). A third
optional file (`complexity-gate.md`) was not needed — the 199/193 line pair
fit within budget. No new agents, skills, playbooks, hooks, or edits to
existing `.claude/agents/*.md` or `.claude/skills/*/skill.md` were made. The
meta-leakage filter was applied to all shipped content: no occurrence of Phase
vocabulary, plugin-internal names, Advisor/Escalation/Dim terms remains. Phase
7-8 may now install the hooks + MCP + `.gitignore` updates referenced by the
rules.

## Files Generated

Shipped rule files (loaded always-apply because they carry no YAML frontmatter,
matching the existing 5 XGif rule files):

- `D:\ProjectX\XGif_v5\.claude\rules\workflow-orchestrator.md` — 199 lines.
  Main session router contract: role, Complexity Gate with 4-file GOD_OBJECTS
  SSoT, grade-to-step mapping, domain detection, domain-harness activation
  matrix, slash command mapping, workspace entry cleanup protocol, review mode
  flags, optimization write policy (imperative), retry policy + timeout table,
  hook invocation hints.
- `D:\ProjectX\XGif_v5\.claude\rules\harness-invocation.md` — 193 lines.
  Per-trigger Task sequences for `/code-reviewer` (L full / M reduced /
  --plan-only / S), `/test-automation` (M/L full / S), `/performance-optimizer`
  (L only), `/cli-tool-builder` (2-agent subset), plus the 5 prelude bodies
  (release-engineer, integration-tester, style-inspector,
  architecture-reviewer, optimization-engineer) — all meta-term filtered.

No other files were created. No `.claude/agents/*.md` or `.claude/skills/*/skill.md`
edits. No `playbooks/` directory. No hooks installed yet (deferred to Phase 7-8).

## Skills Created

Zero new skills were created — this matches the Phase 5 decision. The four
pre-installed harness skills under `.claude/skills/` (test-automation,
code-reviewer, performance-optimizer, cli-tool-builder) are left exactly as
shipped. Their `skill.md` files remain the reference documentation for their
internal 5-agent chains, but the orchestration path now runs through the rules
(Phase 5 OPT-C resolution).

## Location Decisions

Not applicable in the traditional case-A/case-B sense — the D-1 orchestrator
pattern already existed with pre-installed harness skills, and Phase 5
confirmed no new playbooks or user-invocable skills are needed. The shipped
artifacts are rule files, placed in `.claude/rules/` alongside the 5 existing
always-apply rule files.

## allowed_dirs Consolidation

No skill-level `allowed_dirs` frontmatter was added (no new skills). The
write-scope conventions are encoded as text policy inside
`workflow-orchestrator.md` under `## Optimization Write Policy`. Phase 7-8 may
reference this as the source of truth when deciding whether to install a
PreToolUse ownership guard.

Summary table (for Phase 7-8 reference):

| Agent role | Writes allowed |
|-----------|----------------|
| All harness agents | `_workspace/` (current session) |
| `unit-tester`, `integration-tester` | + `tests/`, `tests/integration/` |
| `benchmark-manager` | + `tests/benchmarks/` |
| `docs-writer` | + `CHANGELOG.md` |
| `release-engineer` | + build-log output (no source edits) |
| `optimization-engineer` | `_workspace/` only; `core/` edits forbidden — main session applies via Edit after review |

Phase 5 pre-decided to reject PreToolUse hook enforcement (Option A+ / rejected
alternative #6). Phase 7-8 should not reverse this unless the user requests it.

## Final Agent-Skill Mapping

Unchanged from Phase 5. The 17 active agents in the pre-installed harness-100
installation keep their existing `skill.md` associations. No XGif-specific
skill.md changes were made. The Agent-Skill Ownership Table in
`04-agent-team.md` remains authoritative.

## Meta-Term Filter Audit

Verified absent from both shipped rule files (`grep` patterns checked on
`.claude/rules/`):

- `Phase [0-9]`, `Phase `, `phase-*` → 0 matches
- `harness-architect`, `skill-forge`, `agent-team` → 0 matches
- `orchestrator-protocol`, `question-discipline` → 0 matches
- `red-team`, `red team`, `Red-team` → 0 matches
- `meta-leakage` → 0 matches
- `Advisor`, `Escalation`, `Dim [0-9]` → 0 matches

Substitutions applied while copying the 5 preludes from `03-pipeline-design.md`:

- "Phase X" references → removed
- "Advisor Resolution" references → removed
- Cross-references like "§주입 대상 #N" → dropped, prelude placed under
  an anchor heading (`### prelude-{agent}`)
- "harness-architect"/"skill-forge"/"agent-team" → not present in the prelude
  bodies themselves, so no substitution needed

Neutral terms retained (explicitly permitted): `harness`, `agent`, `skill`,
`hook`, `rule`, `Complexity Gate`, `workflow step`, `review-synthesizer`,
`qa-reviewer`, `perf-reviewer`, `GOD_OBJECTS`, `BLOCK` (uppercase label only,
describing an outcome state, not a meta role).

Additionally added to `prelude-architecture-reviewer` (vs the SSoT in
`03-pipeline-design.md`): the fourth GOD_OBJECTS file
`core/capture_backend.py` was merged in — this matches the Phase 4 Advisor
Resolution's SSoT 4-file list and closes the pseudocode's 3-file inconsistency.

## File Split Decision

Phase 5 authorized a split into up to three files; only two were required:

- **Used**: `workflow-orchestrator.md` (199 lines), `harness-invocation.md`
  (193 lines).
- **Not used**: `complexity-gate.md` — the Complexity Gate section fit cleanly
  in the primary file without crossing the 200-line limit.

Both files are 200-line-budget compliant and carry no YAML frontmatter, so they
load as always-apply rules (matching the 5 pre-existing XGif rule files under
`.claude/rules/`).

## Context for Next Phase

Phase 7-8 (hooks-mcp-setup) needs:

1. **Hook to install**: `.claude/hooks/precommit-m-grade-reminder.sh` (or
   equivalent) — non-blocking PreCommit reminder. Trigger criteria (any of):
   - `git diff --cached` touches ≥ 2 files
   - ≥ 3 new `def ` lines added
   - ≥ 1 new `import` / `from ... import` line added
   - Diff touches GOD_OBJECTS (`ui/main_window.py`, `core/screen_recorder.py`,
     `core/capture_backend.py`, `core/gif_encoder.py`) or any path under
     `editor/ui/`
   Output: suggest `/code-reviewer`; never exit non-zero; always exit 0.
   Full spec text is already in `workflow-orchestrator.md` under
   `## Hook Invocation Hints`.

2. **Optional hook** (Phase 7-8 decides): `postwrite-s-grade-ruff.sh` — after
   Edit tool use in S-grade flow, auto-run `ruff check --fix`. Low priority;
   skip if noise outweighs benefit.

3. **`.gitignore` updates**: add `_workspace/` and `_workspace.prev-*` patterns.
   Referenced by `workflow-orchestrator.md` `## Workspace Entry Cleanup
   Protocol`.

4. **No PreToolUse ownership guard**: Phase 5 rejected this (Option A+).
   Optimization write policy is text-policy only. Do not install a guard
   hook unless the user explicitly requests it.

5. **MCP**: none required by the harness. No MCP server will be specified by
   these rule files. Phase 7-8 may install project-specific MCP at its
   discretion based on user intent.

6. **Settings reach**: nothing in these rule files edits `.claude/settings.json`
   or `settings.local.json`. Phase 7-8 owns all settings changes.

7. **Validation hints for Phase 9**:
   - Verify both rule files load without frontmatter errors.
   - Confirm no meta-vocabulary leaks (use the grep audit above).
   - Confirm file sizes remain ≤ 200 lines on any future edit.
   - Verify GOD_OBJECTS file list matches 4 entries in both files.

## Escalations

[NOTE] Two-file split used (authorized). Complexity Gate content fit in the
primary file — the pre-authorized `complexity-gate.md` third file was not
needed.

[NOTE] `prelude-architecture-reviewer` was extended beyond the
`03-pipeline-design.md` SSoT to include the fourth GOD_OBJECTS file
(`core/gif_encoder.py`), reconciling the 4-file SSoT finalized in the Phase 4
Advisor Resolution NOTE on pseudocode drift. The prelude now reads as a
unified 4-file list for consistency with the GOD_OBJECTS block in
`workflow-orchestrator.md`.

[NOTE] The shipped rule files deliberately omit the
`_workspace/{alias}/` subdirectory convention from the earlier Phase 3/4
design — Phase 4 Advisor Resolution BLOCK-1 (Option A+) rendered that scheme
superseded. Both shipped files use only the flat `_workspace/` root, matching
Phase 5's binding decision.

[NOTE] M-grade plan.md has no automated reviewer — this is explicit in
`workflow-orchestrator.md` `## Grade-Step Mapping` ("plan.md is a solo
self-review — no automated reviewer"). Users who want a plan review on
M-grade can invoke `/code-reviewer --plan-only <path>` (documented in
`harness-invocation.md`).

[NOTE] `optimization-engineer` write policy uses imperative MUST NOT wording
in both files — the main file's policy section and the harness file's
`/performance-optimizer` block both repeat the constraint for redundancy.

## Next Steps

Proceed to Phase 7-8 (hooks-mcp-setup). Primary tasks:

1. Install `.claude/hooks/precommit-m-grade-reminder.sh` per the spec in
   `workflow-orchestrator.md`.
2. Update `.gitignore` with `_workspace/` and `_workspace.prev-*`.
3. Decide on the optional `postwrite-s-grade-ruff.sh` hook.
4. No MCP server install required by the harness itself.
5. Do not revisit PreToolUse ownership enforcement unless the user asks
   (Phase 5 / Option A+ standing decision).
