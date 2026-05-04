---
phase: Audit Fix Application
source: docs/xgif-setup/09-audit-findings.md
completed: 2026-04-21
status: applied-uncommitted
applied_by: main-session (Opus)
track: audit-and-improve
---

# Audit Fix 적용 결과 — XGif Harness (2026-04-21)

> Maintenance note (2026-04-22): 이 문서는 2026-04-21 audit fix 적용 스냅샷을 보존한다.
> 이후 dead-code cleanup으로 `tests/unit/core/test_encoder_presets.py`가 제거됐고,
> 코드 LOC도 일부 다시 변했다(`core/capture_backend.py` 748, `core/gif_encoder.py`
> 1333). 최신 상태는 `README.md`와 `docs/TODO.md`를 우선 기준으로 본다.

## Executive Summary

2026-04-21 harness-audit (phase-setup, Opus) → red-team-advisor (Opus) → 사용자 결정
수집(AskUserQuestion 4건) 파이프라인을 거쳐 **09-audit-findings.md** 의 권고안을 메인
세션이 Edit으로 적용했다. 커밋은 수행하지 않았으며, 사용자가 깨어난 뒤 `git diff`를
검토하고 직접 커밋 여부를 결정하도록 남겨둔다.

## 사용자 결정 (AskUserQuestion)

| 항목 | 선택 |
|------|------|
| ASK-01 (`/cli-tool-builder` 모순 override 위치) | 옵션 A — `skill.md` 상단 override 노트 |
| ASK-02 (CLAUDE.md AskUserQuestion 규약 ↔ 서브에이전트 금지) | 옵션 A — CLAUDE.md에 "메인 세션 한정" 단서 추가 |
| BLOCK 적용 범위 | 전부 일괄 (BLOCK-01~06) |
| NOTE / NEW 포함 항목 | NOTE-01 (meta-leakage 2줄) + NOTE-03 (testing-standards tests/unit 반영) + NEW-01 (파사드 패턴 강조) |

## 적용된 수정 사항

### BLOCK-01 — Pre-commit hook GOD_OBJECTS 패턴 동기화

**파일**: `D:/ProjectX/XGif_v5/.claude/hooks/precommit-m-grade-reminder.sh`

- grep 패턴에 `core/capture_worker.py` 추가 (CRITICAL_FILES 누락 보강)
- `core/screen_recorder.py`는 CRITICAL_FILES 분류로 계속 포함
- 라벨을 `GOD_OBJECTS/CRITICAL_DIRS` → `GOD_OBJECTS/CRITICAL_FILES/CRITICAL_DIRS` 로 확장

### BLOCK-02 ∼ BLOCK-05 — LOC 수치 재동기화

**파일**: `.claude/rules/workflow-orchestrator.md`, `.claude/rules/harness-invocation.md`

| 파일 | 이전 문서 | 실측 (wc -l) | 적용 |
|------|----------|-------------|------|
| `ui/main_window.py` | 1,983 | 1,957 | ✓ (workflow-orchestrator.md:35, harness-invocation.md:180) |
| `core/capture_backend.py` | ~733 | 780 | ✓ (+47, warm-up 흡수) — `(~780 LOC, 2026-04-21)` |
| `core/gif_encoder.py` | 미기재 | 1,323 | ✓ (신규 기재) + `GPU fallback` 수식어 추가 |
| `core/screen_recorder.py` | 680 | 688 | ✓ `~688 LOC` 파사드 |
| `core/capture_worker.py` | ~450 | 452 | ✓ `(~452 LOC)` |

### BLOCK-06 — XGif.spec 동적 생성 명시

**파일**: `.claude/rules/harness-invocation.md` (prelude-release-engineer 블록, line 131~133)

- 기존: `PyInstaller spec: \`XGif.spec\` / Inno Setup 스크립트: ...`
- 변경: `build_optimized.py`가 런타임에 spec을 동적 생성하며 별도 커밋된 spec 파일이
  없음을 명시. Inno Setup 스크립트는 커밋됨을 분리 서술.
- 효과: release-engineer 에이전트가 `XGif.spec` 부재를 탐색 실패로 오인하지 않음.

### ASK-01 — `cli-tool-builder` override 명시

**파일**: `.claude/skills/cli-tool-builder/skill.md` (frontmatter 직하단)

- 상단 blockquote로 XGif override 노트 삽입: 2-agent subset(release-engineer + docs-writer)
  만 활성, 나머지 3명 소환 금지, STEP 6 release / BootStrapper 도메인 전용.
- 동시에 `CLAUDE.md` 도메인 하네스 테이블의 `cli-tool-builder` 행에도 인라인 주석 추가.

### ASK-02 — AskUserQuestion 메인 세션 한정 단서

**파일**: `CLAUDE.md` (협업 규약 섹션)

- 기존: `결정이 모호하면 AskUserQuestion으로 확인한다`.
- 변경: **메인 세션에 한해** 허용, 서브에이전트는 `Escalations` 섹션에 `[ASK]`/`[BLOCK]`/
  `[NOTE]` 태그로 기록하여 오케스트레이터에 반환.

### NOTE-01 — CLAUDE.md meta-leakage 잔재 제거

**파일**: `CLAUDE.md`

- 헤더: `## 설치된 에이전트 하네스 (from harness-100)` → `## 설치된 에이전트 하네스`
- 본문: `하네스 에이전트는 범용 도메인 지식을 가지므로, ...` → `각 에이전트는 범용 도메인 지식을 가지므로, ...`

### NOTE-03 — testing-standards 테스트 파일 목록 확장

**파일**: `.claude/rules/testing-standards.md`

- 위치 섹션에 `tests/unit/{cli,core,editor}/` 서브디렉터리 명시
- 테이블을 "루트(`tests/`) / 서브(`tests/unit/`)" 2-레벨로 재구성
- 신규 추가된 테스트 6건 기재:
  - `tests/unit/cli/test_arg_parsing.py`
  - `tests/unit/core/test_encoder_presets.py` (removed in 2026-04-22 dead-code cleanup)
  - `tests/unit/core/test_events.py`
  - `tests/unit/core/test_overlay_pipeline.py`
  - `tests/unit/core/test_settings.py`
  - `tests/unit/editor/test_undo_manager.py`

### NEW-01 (Advisor 추가 발견) — prelude-architecture-reviewer 파사드 패턴 강조

**파일**: `.claude/rules/harness-invocation.md` (prelude-architecture-reviewer 블록)

- 기존: `screen_recorder.py`를 단순히 "680 LOC 파사드로 축소"라고 1회 언급.
- 변경: **파사드인 이 파일은 책임을 직접 추가하기보다 이미 분리된 collaborator(capture_worker,
  gif_encoder, capture_backend 등)로 위임해야 한다** — 파사드의 역할을 과도하게 확장하는
  리팩토링 제안은 반려.
- 효과: 서브에이전트가 파사드 패턴을 인지하고 내부 로직을 재집중하지 않도록 유도.

## 적용 제외 (의도적 스킵)

| 항목 | 사유 |
|------|------|
| NOTE-02 (`.venv/` 부재) | 사용자 로컬 환경 문제 — 하네스 수정 범위 외. 사용자가 깨어난 뒤 venv 재생성으로 해결 가능. |
| NOTE-04 (비활성 에이전트 3명 유지) | 현 정책이 올바름을 audit/advisor 모두 확인. 변경 불필요. |
| NOTE-05 (`_workspace/` 잔재) | 다음 `/code-reviewer`·`/test-automation` 호출 시 자동 archive. 수동 개입 불필요. |

## Verification Checklist 결과

09-audit-findings.md 의 Verification Checklist 자동 수행 결과:

| 항목 | 명령 | 기대 | 실제 | 결과 |
|------|------|------|------|------|
| BLOCK-01 (hook capture_worker 추가) | `grep -c capture_worker .claude/hooks/precommit-m-grade-reminder.sh` | 1 | 1 | ✓ |
| BLOCK-02/04 LOC 실측 | `wc -l ui/main_window.py core/screen_recorder.py core/capture_worker.py` | 1957 / 688 / 452 | 1957 / 688 / 452 | ✓ |
| BLOCK-03 LOC 실측 | `wc -l core/capture_backend.py` | 780 | 780 | ✓ |
| BLOCK-05 gif_encoder LOC 기재 | `grep -E "gif_encoder.py.*[0-9,]+ LOC" 규칙 2개` | 2 matches | 2 matches | ✓ |
| BLOCK-06 XGif.spec 동적 생성 | `grep "동적 생성" harness-invocation.md` | ≥ 1 | 1 match (line 132) | ✓ |
| ASK-01 override 노트 | `grep "XGif override" skill.md` | ≥ 1 | 1 match (line 6) | ✓ |
| ASK-02 메인 세션 한정 | `grep "메인 세션에 한해" CLAUDE.md` | ≥ 1 | 1 match (line 59) | ✓ |
| NOTE-01 meta-leakage 제거 | `grep "(from harness-100)" CLAUDE.md` | 0 | 0 | ✓ |
| NOTE-03 tests/unit 반영 | `grep "tests/unit" testing-standards.md` | ≥ 5 | 8 matches | ✓ |
| 구버전 LOC 잔존 여부 | `grep "1,983\|~733 LOC\|680 LOC\|~450 LOC" 규칙 2개` | 0 | 0 | ✓ |

전 항목 PASS.

## 변경된 파일 목록

1. `D:/ProjectX/XGif_v5/CLAUDE.md`
2. `D:/ProjectX/XGif_v5/.claude/rules/workflow-orchestrator.md`
3. `D:/ProjectX/XGif_v5/.claude/rules/harness-invocation.md`
4. `D:/ProjectX/XGif_v5/.claude/rules/testing-standards.md`
5. `D:/ProjectX/XGif_v5/.claude/hooks/precommit-m-grade-reminder.sh`
6. `D:/ProjectX/XGif_v5/.claude/skills/cli-tool-builder/skill.md`
7. `D:/ProjectX/XGif_v5/docs/xgif-setup/00-target-path.md` (재실행 트랙 기록 갱신)
8. `D:/ProjectX/XGif_v5/docs/xgif-setup/10-audit-fix-applied.md` (본 파일, 신규)

09-audit-findings.md 는 보존 (수정하지 않음).

## 커밋 상태

**미커밋**. 사용자가 깨어난 뒤 `git status` / `git diff` 로 변경을 검토하고 직접 커밋
또는 discard 결정하도록 남겨둠. 제안 커밋 메시지 예:

```
docs(harness): 2026-04-21 Audit drift 전량 수정 (LOC/hook/meta-leakage/override)

- hook GOD_OBJECTS 패턴 capture_worker 추가 + 라벨 CRITICAL_FILES 확장
- LOC 재동기화 (1957/780/1323/688/452 실측)
- XGif.spec 동적 생성 명시
- cli-tool-builder 2-agent subset override 노트 + CLAUDE.md 각주
- CLAUDE.md AskUserQuestion 메인 세션 한정 단서
- meta-leakage 2줄 (CLAUDE.md 헤더·본문) 정리
- testing-standards tests/unit 서브디렉터리 반영
- prelude-architecture-reviewer 파사드 패턴 강조
```

## 후속 권고

1. **커밋 검토**: `git diff .claude/ CLAUDE.md docs/xgif-setup/` 로 변경 범위 확인 후 커밋.
2. **`.venv/` 복구** (NOTE-02): `python -m venv .venv` 후 requirements 재설치 — 하네스
   실행 규약 (`.venv/Scripts/python.exe`) 회복.
3. **`/harness-architect:ops-audit` 실행 검토**: 본 audit은 **구성 중심** 진단. 런타임/운영
   부채(세션 연속성, 재시도 종료, 이중 관리 drift 등)는 별도 플레이북.
4. **다음 하네스 실행 시점**: `_workspace/` 자동 archive는 다음 `/code-reviewer`·
   `/test-automation`·`/performance-optimizer`·`/cli-tool-builder` 호출에서 처리됨.
