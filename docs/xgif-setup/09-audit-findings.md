---
phase: 1-2 (Audit Track)
completed: 2026-04-21
status: findings-pending-user-decision
track: audit-and-improve
playbook: harness-audit
---

# Audit Findings — XGif Harness (2026-04-21)

> Maintenance note (2026-04-22): 이 문서는 2026-04-21 audit 시점의 finding snapshot이다.
> 이후 dead-code cleanup으로 `core/encoder/`와
> `tests/unit/core/test_encoder_presets.py`가 제거됐고, 현재 repo-wide `ruff`
> baseline은 `372`건이다. 아래 본문은 당시 진단 맥락을 보존하기 위해 원문을 유지한다.

## Executive Summary

XGif 하네스는 2026-04-20 초기 구축(커밋 `6b50b33` 이하 Phase 0~9) + 2026-04-21 최근
크로스 리뷰(커밋 `ba2f4a1` 등)를 거쳐 현재 상태에 도달했다. 구조적 건강성은
전반적으로 양호하나, **코드 리팩토링 속도를 하네스 문서가 완전히 따라잡지 못한
drift**가 다수 검출되었다.

가장 시급한 문제는 `core/screen_recorder.py`의 GOD_OBJECT 목록 제외 결정이 rule
파일에는 반영됐지만 **`precommit-m-grade-reminder.sh` hook 스크립트에는 반영되지
않은** 점이다 (BLOCK-01). 이 drift는 커밋 시 hook이 구버전 기준으로 경고를
발생시켜 새로운 CRITICAL_FILES(`core/capture_worker.py`)를 놓칠 위험이 있다.

총 집계:
- **BLOCK**: 6건 (hook drift 1건, LOC 수치 drift 4건, 참조 파일 부재 1건)
- **ASK**: 2건 (skill.md ↔ rule 모순 override 의도 확인, CLAUDE.md 협업 규약 vs 서브에이전트 AskUserQuestion 금지 정합성)
- **NOTE**: 5건 (meta-leakage 잔재, 실행 환경 drift, testing-standards 파일 목록 구식, 빠진 LOC 기재, `_workspace/` 예상치 못한 존재)

본 Audit은 **진단만 수행**. 모든 제안 수정은 메인 세션이 Escalations 취합 후 Edit으로
적용한다. 00~08 산출물은 보존했다.

---

## Findings

### [BLOCK-01] Pre-commit hook의 GOD_OBJECTS 패턴이 rule 파일과 동기화 안됨

**앵커**: `D:/ProjectX/XGif_v5/.claude/hooks/precommit-m-grade-reminder.sh:56`

**증상**:
```bash
GOD_MATCH=$(printf '%s\n' "$STAGED_FILES" | grep -E \
  '^(ui/main_window\.py|core/screen_recorder\.py|core/capture_backend\.py|core/gif_encoder\.py|editor/ui/)' \
  2>/dev/null || true)
```
- `core/screen_recorder.py` — **여전히 GOD_OBJECTS 취급** (rule에서 제외됐음)
- `core/capture_worker.py` — **누락** (rule에서 CRITICAL_FILES로 승격됐음)

**원인**: 2026-04-21 커밋 `ba2f4a1 "docs: GOD_OBJECTS 목록 갱신"`에서 rule 파일(
`.claude/rules/workflow-orchestrator.md`·`harness-invocation.md`)은 업데이트됐지만
hook script는 함께 수정되지 않았다. Phase 7 `07-validation-report.md:72-73`이
"GOD_OBJECTS 4-file list in hook script regex PASS"로 기록했는데, 그 시점은 정합했으나
이후 rule 파일만 업데이트되어 drift가 발생했다.

**영향도**:
- 커밋 시 `core/screen_recorder.py` 수정하면 여전히 GOD_OBJECT 트리거가 발동 → 불필요한
  M-grade 승격 경고.
- 반대로 `core/capture_worker.py`(~450 LOC, 캡처 스레드 코어)를 수정해도 hook은 경고
  안 함 → CRITICAL_FILES 탐지 실패.

**Severity**: BLOCK — 하네스 호출 시 잘못된 결정(승격 누락) 유도.

**Proposed Fix** (메인 세션이 Edit으로 적용):

```diff
  GOD_MATCH=$(printf '%s\n' "$STAGED_FILES" | grep -E \
-   '^(ui/main_window\.py|core/screen_recorder\.py|core/capture_backend\.py|core/gif_encoder\.py|editor/ui/)' \
+   '^(ui/main_window\.py|core/capture_backend\.py|core/gif_encoder\.py|core/screen_recorder\.py|core/capture_worker\.py|editor/ui/)' \
    2>/dev/null || true)
```

위 변경은:
1. GOD_OBJECTS 3파일(ui/main_window.py, core/capture_backend.py, core/gif_encoder.py)
2. CRITICAL_FILES 2파일(core/screen_recorder.py, core/capture_worker.py) — rule 파일이 "권고 ≥ M"으로 명시
3. CRITICAL_DIRS(editor/ui/)

모두 커버한다. 메시지 라벨 `"GOD_OBJECTS/CRITICAL_DIRS"`도 업데이트 권고:

```diff
-    REASON="${REASON}touches GOD_OBJECTS/CRITICAL_DIRS ($(printf '%s' "$GOD_MATCH" | head -1 | tr -d '\n')...); "
+    REASON="${REASON}touches GOD_OBJECTS/CRITICAL_FILES/CRITICAL_DIRS ($(printf '%s' "$GOD_MATCH" | head -1 | tr -d '\n')...); "
```

---

### [BLOCK-02] `ui/main_window.py` LOC 수치 drift

**앵커**:
- `D:/ProjectX/XGif_v5/.claude/rules/workflow-orchestrator.md:35` — `"ui/main_window.py",            # 1,983 LOC, UI entry point`
- `D:/ProjectX/XGif_v5/.claude/rules/harness-invocation.md:177` — `GOD_OBJECTS (3개 파일, 2026-04-21 갱신): \`ui/main_window.py\` (1,983 LOC)`

**실측**: `wc -l ui/main_window.py` → **1,957 LOC**

**차이**: 문서 1,983 vs 실제 1,957 (−26 LOC)

**원인**: 최근 커밋 `35e3ff1 refactor: cleanup_shared_cameras 파사드 추가 + UI 경계 정리 (P2-7)` 등에서 LOC가 축소됐지만 문서는 수동 갱신됨에도 실측을 반영하지 못함.

**Severity**: BLOCK — GOD_OBJECT 지정은 유지되므로 판정 오류는 없지만, 문서가 "2026-04-21 갱신"이라고 기재됐기에 신뢰도가 무너진다. 다른 값도 함께 점검.

**Proposed Fix**:

`workflow-orchestrator.md:35`:
```diff
-    "ui/main_window.py",            # 1,983 LOC, UI entry point
+    "ui/main_window.py",            # 1,957 LOC, UI entry point (2026-04-21 측정)
```

`harness-invocation.md:177`:
```diff
-GOD_OBJECTS (3개 파일, 2026-04-21 갱신): `ui/main_window.py` (1,983 LOC),
+GOD_OBJECTS (3개 파일, 2026-04-21 갱신): `ui/main_window.py` (1,957 LOC),
```

---

### [BLOCK-03] `core/capture_backend.py` LOC 수치 drift

**앵커**:
- `D:/ProjectX/XGif_v5/.claude/rules/workflow-orchestrator.md:36` — `"core/capture_backend.py",       # DXCam/FastGDI/GDI ABC + pool + fallback (~733 LOC)`
- `D:/ProjectX/XGif_v5/.claude/rules/harness-invocation.md:178` — `\`core/capture_backend.py\` (~733 LOC)`

**실측**: `wc -l core/capture_backend.py` → **780 LOC**

**차이**: 문서 ~733 vs 실제 780 (+47 LOC). `~` 접두가 붙어 근사값임을 인정하나 ~7% 증가는 작지 않음.

**원인**: 최근 커밋 `2efe3d5 refactor: CaptureBackend ABC 확장 + warm-up 흡수`, `2284ec7 fix: force_release 공유 카메라 정리 + ABC DI pass-through`가 ABC 표면을 확장. 이 변경이 문서에 반영되지 않음.

**Severity**: BLOCK — 여전히 GOD_OBJECT 분류는 유효하지만, 2026-04-21 갱신 타임스탬프가
약속하는 정확성과 실측의 간극. `(~733)` → `(~780)`로 갱신 또는 `~` 유지 폭을 명확히
반올림 단위 명시.

**Proposed Fix**:

`workflow-orchestrator.md:36`:
```diff
-    "core/capture_backend.py",       # DXCam/FastGDI/GDI ABC + pool + fallback (~733 LOC)
+    "core/capture_backend.py",       # DXCam/FastGDI/GDI ABC + pool + fallback + warm-up (~780 LOC, 2026-04-21)
```

`harness-invocation.md:178`:
```diff
-`core/capture_backend.py` (~733 LOC), `core/gif_encoder.py`. 수정 시 책임 범위 확장 여부 평가 필요.
+`core/capture_backend.py` (~780 LOC), `core/gif_encoder.py` (~1,323 LOC). 수정 시 책임 범위 확장 여부 평가 필요.
```

(BLOCK-05와 결합하여 gif_encoder LOC도 추가됨)

---

### [BLOCK-04] `core/screen_recorder.py` / `core/capture_worker.py` LOC 수치 근사

**앵커**:
- `D:/ProjectX/XGif_v5/.claude/rules/workflow-orchestrator.md:42-44` — `680 LOC 의 파사드`·`(~450 LOC)`
- `D:/ProjectX/XGif_v5/.claude/rules/harness-invocation.md:179-180` — `680 LOC 파사드로 축소`

**실측**:
- `core/screen_recorder.py` → **688 LOC** (문서 680, +8)
- `core/capture_worker.py` → **452 LOC** (문서 ~450, +2)

**차이**: `screen_recorder`는 문서가 정확한 수치를 고정(680) 명시했는데 실제 688. 8 LOC 차.
`capture_worker`는 `~450` 근사로 허용 범위 내.

**Severity**: BLOCK (`screen_recorder` 쪽은 고정값 명시이기에 drift 명백).

**원인**: 최근 `refactor: except 핸들러 디버거빌리티 개선` (3727bc0), `fix: shape mismatch 표면화` (75f55a9) 등이 screen_recorder.py에 narrower exception handler + 로깅을 추가.

**Proposed Fix**:

`workflow-orchestrator.md:42-45`:
```diff
-> `core/screen_recorder.py` 는 2026-04-21 P1 refactor (커밋 `d29aabf`) 이후
-> 680 LOC 의 파사드로 축소되었고 CaptureThread 는 `core/capture_worker.py`
-> 로 분리되었다. GOD_OBJECT 목록에서 제외. 다만 `core/capture_worker.py`
-> (~450 LOC) 와 `core/screen_recorder.py` 는 여전히 **CRITICAL_FILES** 로
+> `core/screen_recorder.py` 는 2026-04-21 P1 refactor (커밋 `d29aabf`) 이후
+> 파사드로 축소되었고 CaptureThread 는 `core/capture_worker.py`
+> 로 분리되었다. GOD_OBJECT 목록에서 제외. 다만 `core/capture_worker.py`
+> (~452 LOC) 와 `core/screen_recorder.py` (~688 LOC) 는 여전히 **CRITICAL_FILES** 로
```

`harness-invocation.md:179`:
```diff
-`core/screen_recorder.py` 는 P1 refactor 이후 680 LOC 파사드로 축소되어 GOD_OBJECT 에서 제외되었고,
+`core/screen_recorder.py` 는 P1 refactor 이후 ~688 LOC 파사드로 축소되어 GOD_OBJECT 에서 제외되었고,
```

---

### [BLOCK-05] `core/gif_encoder.py` LOC 미기재 — 1,323 LOC는 GOD_OBJECT 중 가장 큰 파일

**앵커**:
- `D:/ProjectX/XGif_v5/.claude/rules/workflow-orchestrator.md:37` — `"core/gif_encoder.py",           # FFmpeg pipe control`
- `D:/ProjectX/XGif_v5/.claude/rules/harness-invocation.md:178` — LOC 기재 없음

**실측**: `wc -l core/gif_encoder.py` → **1,323 LOC**

**차이**: 3개 GOD_OBJECTS 중 다른 2개는 LOC 명시, gif_encoder.py만 누락. 실측 1,323은
`core/capture_backend.py`(780)보다 크고 `ui/main_window.py`(1,957)와 함께 **상위 2위
스케일**. 문서가 이 크기를 인지하지 못한 상태로 작업 판정에 사용되면 복잡도 감각
왜곡.

**Severity**: BLOCK — 고정 LOC 명시 양식을 GOD_OBJECTS 전체에 적용해야 판정 일관성
확보.

**Proposed Fix**:

`workflow-orchestrator.md:37`:
```diff
-    "core/gif_encoder.py",           # FFmpeg pipe control
+    "core/gif_encoder.py",           # FFmpeg pipe control + GPU fallback (1,323 LOC, 2026-04-21)
```

BLOCK-03 fix 내 `harness-invocation.md:178`와 결합.

---

### [BLOCK-06] `XGif.spec` 파일 부재 — prelude와 discovery 산출물이 존재 가정

**앵커**:
- `D:/ProjectX/XGif_v5/.claude/rules/harness-invocation.md:131` — `PyInstaller spec: \`XGif.spec\` / Inno Setup 스크립트: \`installer/xgif_setup.iss\`.`
- `D:/ProjectX/XGif_v5/docs/xgif-setup/01-discovery-answers.md:30` — `Key files: ..., main.py, build_optimized.py, XGif.spec`
- `D:/ProjectX/XGif_v5/docs/xgif-setup/02-workflow-design.md:289` — `XGif.spec`, `build_optimized.py`, `installer/xgif_setup.iss`
- `D:/ProjectX/XGif_v5/docs/xgif-setup/03-pipeline-design.md:277,386` — 동일

**실측**: `ls D:/ProjectX/XGif_v5/XGif.spec` → **NO_SPEC** (파일 없음).

**동적 생성 확인**: `build_optimized.py:489` — `spec_path = os.path.join(PROJECT_DIR, "XGif.spec")`.
빌드 시점에 PyInstaller `--onefile ...`로 생성되는 "ephemeral spec"일 가능성. `.gitignore`
에 포함된 transient 파일이거나 빌드 아티팩트.

**영향도**:
- `release-engineer` 에이전트가 `XGif.spec`을 읽으려 하면 실패.
- Discovery 산출물(01-)의 "Key files" 리스트가 현재 시점과 불일치.
- prelude가 "PyInstaller spec"을 별도 커스텀 파일로 오해할 위험.

**Severity**: BLOCK — 에이전트가 prelude를 따라 `XGif.spec`을 열려다 실패 시 release
workflow 전체 중단. Phase 6 release-engineer가 실제 실행될 때 문제 표면화.

**Proposed Fix**:

`harness-invocation.md:131` (prelude-release-engineer 내):
```diff
-- PyInstaller spec: `XGif.spec` / Inno Setup 스크립트: `installer/xgif_setup.iss`.
+- PyInstaller 빌드 설정: `build_optimized.py` 가 런타임에 spec 파일을
+  (`$PROJECT_DIR/XGif.spec`) 동적 생성. 별도 커스텀 spec 파일은 저장소에 커밋돼 있지 않다.
+- Inno Setup 스크립트: `installer/xgif_setup.iss` (커밋됨).
```

01-discovery-answers.md는 이미 Phase 1-2 시점의 역사 스냅샷이므로 수정하지 않음 (이 파일
은 @import 대상이므로 신중). 대신 09에 NOTE만 기록.

---

## ASK — 사용자 결정 필요

### [ASK-01] `cli-tool-builder/skill.md` vs `harness-invocation.md` 에이전트 수 모순 — Override 의도 명시 방법

**앵커**:
- `D:/ProjectX/XGif_v5/.claude/skills/cli-tool-builder/skill.md:14-22` — **5명 에이전트** (command-designer, core-developer, test-engineer, docs-writer, release-engineer) 명시
- `D:/ProjectX/XGif_v5/.claude/rules/harness-invocation.md:99-108` — **2명만 사용** 명시, `command-designer`/`core-developer`/`test-engineer` 소환 MUST NOT

**증상**: 사용자가 `/cli-tool-builder`를 호출하면 Skill 도구는 `.claude/skills/cli-tool-builder/skill.md`를 로딩. 그러면 메인 세션은 5명 팀 파이프라인 설명을 먼저 본다. 그 뒤 `harness-invocation.md`의 "2-agent subset" 규칙을 적용해야 함을 알게 되지만, **순서상 혼란**이 발생하거나 `rule`을 간과하면 의도치 않게 5명 체인을 돌릴 수 있다.

**Severity**: ASK — 수정 방향이 둘로 갈림:
1. **옵션 A (권장)**: `cli-tool-builder/skill.md` 상단에 XGif-specific override 노트를 추가
   ```markdown
   > **XGif override**: 이 프로젝트에서는 `.claude/rules/harness-invocation.md`가
   > `/cli-tool-builder`를 2-agent subset(release-engineer + docs-writer)으로 축소한다.
   > 아래 5-agent 파이프라인은 harness-100 기본값이며, XGif에서는 적용되지 않는다.
   > STEP 6 release cut 또는 BootStrapper 도메인 전용.
   ```
   장점: 메인 세션이 skill.md를 먼저 읽더라도 즉시 rule로 redirect. Drift 방지.
   단점: harness-100 공유 skill을 프로젝트-local로 수정 → 공유 원칙 위반 가능성.

2. **옵션 B**: skill.md는 손대지 않고 `CLAUDE.md`의 "설치된 에이전트 하네스" 테이블에
   "(XGif는 release-engineer + docs-writer 2명만 활성화)" 각주 추가.
   장점: skill.md 공유성 유지. CLAUDE.md가 단일 진입 컨텍스트.
   단점: 메인 세션이 skill.md 호출 직후 CLAUDE.md를 재확인하지 않으면 drift 여전.

**권고**: 옵션 A. 하네스-aware 프로젝트가 하네스 skill을 로컬 커스터마이즈한 기록을
남기는 것이 D-1 패턴의 의도된 확장 방식.

---

### [ASK-02] CLAUDE.md 협업 규약의 `AskUserQuestion` 지침 vs 서브에이전트 프리앰블의 AskUserQuestion 금지

**앵커**:
- `D:/ProjectX/XGif_v5/CLAUDE.md:57-60` — `작업 중 결정이 모호하거나 합리적인 선택지가 둘 이상이면, 가정하지 말고 \`AskUserQuestion\` 도구로 먼저 사용자에게 확인한다.`
- 이 Audit 프롬프트 및 메모리(`feedback_autonomous_mode.md`) — 자율주행/서브에이전트 호출 시 `AskUserQuestion` 금지, Escalations 기록 우선

**증상**: 메인 세션에는 "모호하면 AskUserQuestion" 지시가 있고, 서브에이전트 호출에는
"AskUserQuestion 금지" 규약이 있다. 현재 CLAUDE.md는 둘을 구분하지 않고 **일반적으로**
AskUserQuestion을 권고한다. 서브에이전트가 이 규약을 그대로 상속하면 Escalations
프로토콜을 깰 위험.

**Severity**: ASK — 수정 방향:
1. **옵션 A**: CLAUDE.md 협업 규약에 "메인 세션 한정" 단서 추가:
   ```markdown
   - 작업 중 결정이 모호하거나 합리적인 선택지가 둘 이상이면, **메인 세션에 한해**
     `AskUserQuestion` 도구로 먼저 사용자에게 확인한다. 서브에이전트(`Task` 호출) 내부에
     서는 `AskUserQuestion`을 사용하지 않으며, 결정 사항을 산출물의 Escalations 섹션에
     `[ASK]`/`[BLOCKING]`/`[NOTE]` 태그로 기록하여 오케스트레이터에게 반환한다.
   ```
2. **옵션 B**: 규약을 그대로 두고, 서브에이전트 프리앰블(`harness-invocation.md`의 5개
   prelude)에 "AskUserQuestion 금지" 명시적 문장 추가. 각 prelude 별 중복 작성 비용.

**권고**: 옵션 A. CLAUDE.md는 단일 SSoT이므로 예외 조항을 거기서 한 번 명시하는
것이 가장 경제적.

---

## NOTE — 개선 여지 있으나 시급성 낮음

### [NOTE-01] Meta-leakage 잔재 — Phase 7에서 이미 P2/P3로 식별됨

**앵커**:
- `D:/ProjectX/XGif_v5/CLAUDE.md:82` — `하네스 에이전트는 범용 도메인 지식을 가지므로`
- `D:/ProjectX/XGif_v5/CLAUDE.md:69` — `## 설치된 에이전트 하네스 (from harness-100)`

**상태**: `07-validation-report.md`에서 P2/P3로 기록된 carry-forward 항목이 아직 수정되지 않았다. 신규 문제는 아니나 Phase 7 이후 3일이 지나 남아있음을 재확인.

**Severity**: NOTE — 기능 영향 없음. 쿨다운 기간이 지나서 작성자가 의도적으로 유지하는
것일 수도 있음.

**Proposed Fix**:

`CLAUDE.md:82`:
```diff
-하네스 에이전트는 범용 도메인 지식을 가지므로, 소환 시 다음 XGif-특수 사실을 함께 전달하여야 한다:
+각 에이전트는 범용 도메인 지식을 가지므로, 소환 시 다음 XGif-특수 사실을 함께 전달하여야 한다:
```

`CLAUDE.md:69` — 헤더 내 `(from harness-100)` 부분은 provenance 정보라 필요시 유지,
또는 간결하게:
```diff
-## 설치된 에이전트 하네스 (from harness-100)
+## 설치된 에이전트 하네스
```

---

### [NOTE-02] `.venv/` 부재 — 실행 규약과 환경 drift (현재 작업 세션 한정 가능성)

**앵커**:
- `D:/ProjectX/XGif_v5/CLAUDE.md:5-11` — `.venv/Scripts/python.exe ...` 실행 경로 다수
- `D:/ProjectX/XGif_v5/.claude/settings.json:17-26` — `.venv/Scripts/python.exe*` 권한 allowlist
- `D:/ProjectX/XGif_v5/.claude/rules/testing-standards.md:4-7` — 동일

**실측**: `ls D:/ProjectX/XGif_v5/.venv/Scripts/python.exe` → `NO_VENV`

**원인 추정**: 현재 bash 세션의 CWD 기준 lookup이 실패했거나, 실제 workspace에서 `.venv/`가
삭제·이동됨. `.gitignore`에 `.venv/`가 포함되어 커밋은 되지 않으므로 저장소 상태와
무관. 사용자 로컬 환경에 문제가 있을 수 있음.

**Severity**: NOTE — 하네스 문서 자체는 틀리지 않음. 그러나 서브에이전트가 `.venv/Scripts/python.exe`로 명령을 실행하려 하면 "command not found"로 실패. CLAUDE.local.md에
fallback 경로(시스템 Python 또는 pyenv 경로)를 기록하지 않으면 디버깅 어려움.

**Proposed Fix**: 사용자에게 환경 복구(venv 재생성) 권고. CLAUDE.local.md 템플릿에
`python --version`/`where python` fallback 섹션 추가는 선택사항.

---

### [NOTE-03] `testing-standards.md` 테스트 파일 목록이 `tests/unit/` 서브디렉터리 미반영

**앵커**: `D:/ProjectX/XGif_v5/.claude/rules/testing-standards.md:16-24`

**현재 목록**: `test_config.py` / `test_safety.py` / `test_utils.py` / `test_version.py` /
`test_encoder_e2e.py` / `test_screen_recorder_runtime.py` — 6개.

**실제 구조** (추가됨):
- `tests/unit/cli/test_arg_parsing.py`
- `tests/unit/core/test_encoder_presets.py` (removed in 2026-04-22 dead-code cleanup)
- `tests/unit/core/test_events.py`
- `tests/unit/core/test_overlay_pipeline.py`
- `tests/unit/core/test_settings.py`
- `tests/unit/editor/test_undo_manager.py`

`tests/unit/` 서브디렉터리가 2026-04-20 이후 신설되었는데, 문서 테이블은 평면적
루트 목록만 유지.

**Severity**: NOTE — 실행에는 문제 없음(pytest가 재귀 탐색). 문서 참조 가치 하락.

**Proposed Fix**:

`testing-standards.md:10-11` 아래에 구조 설명 추가:
```markdown
## 테스트 파일 위치
- 루트 테스트: `tests/` — 주요 E2E/통합 테스트.
- 서브 테스트: `tests/unit/{cli,core,editor}/` — 모듈별 단위 테스트 (wx 의존 여부로 분리).
- 파일명: `test_*.py` 접두사
...
```

그리고 16-24 테이블을 디렉터리별 2-레벨로 재구성. 구체 diff는 생략(사용자 취향).

---

### [NOTE-04] `.claude/agents/` 20개 중 `/cli-tool-builder` 비활성 3명이 여전히 존재

**앵커**: `D:/ProjectX/XGif_v5/.claude/agents/command-designer.md`, `core-developer.md`, `test-engineer.md`

**상태**: `harness-invocation.md`는 이 3명을 "MUST NOT be summoned"으로 지정. 그러나
`.claude/agents/` 디렉터리에 파일은 그대로 유지. 삭제하지 않는 이유는 `harness-100` 공유
install 패턴으로 20개 에이전트를 모두 배포하는 것이 원칙이기 때문.

**Severity**: NOTE — 현 정책 유효. 삭제 권고 없음. 단, `07-validation-report.md:74`에
기록된 "All 17 active agent names" 계산식 기억을 위한 재확인 목적.

---

### [NOTE-05] `_workspace/` 존재 — 이전 `/code-reviewer` 세션 잔재

**앵커**: `D:/ProjectX/XGif_v5/_workspace/` (2026-04-21 22:15~22:23에 생성된 01~05 리뷰 파일)

**상태**: Workspace Entry Cleanup Protocol에 따르면 다음 하네스 trigger 진입 시
`_workspace.prev-{YYYYMMDD-HHMMSS}/` 로 rename되어야 함. 현재는 정리되지 않은 채로
남아있음. 이번 Audit 트랙은 cleanup 프로토콜 적용 대상이 아니므로 (plugin invocation,
harness skill 아님) 정상 상황.

**Severity**: NOTE — 다음 `/code-reviewer`·`/test-automation` 호출 시 자동 rename될
예정. 수동 개입 불필요.

---

## Deferred Items (향후 작업)

1. **Ruff pre-existing 396건 errors**: `09-audit-findings.md` 작성 당시 기준. 현재 baseline은 372건이며 별도 정리
   wave 필요하나 하네스 audit 범위 밖.
2. **`docs/TODO.md` ↔ Phase 재분류**: 하네스 rule이 도입되기 전 작성된 TODO가
   M-grade/L-grade 판정 기준과 정합되는지 재검토 필요. 본 감사 범위 초과.
3. **`/harness-architect:ops-audit` 후속 실행**: 본 플레이북(harness-audit)은
   구성 진단 중심. 런타임/운영 부채(세션 연속성, 재시도 종료 조건, 이중 관리 drift,
   산출물 덮어쓰기, 크로스 워크플로우 중복)는 `ops-audit`에 위임. 사용자가 원할 때
   별도 실행 권고.

---

## Verification Checklist

메인 세션이 Escalations 해결 후 실행할 체크리스트:

### BLOCK 수정 적용 확인

- [ ] **BLOCK-01**: `.claude/hooks/precommit-m-grade-reminder.sh:56` grep 패턴에서
  `core/screen_recorder.py` 유지 + `core/capture_worker.py` 추가 확인 (5+1=6 파일/디렉터리).
  ```bash
  grep -c "capture_worker" .claude/hooks/precommit-m-grade-reminder.sh
  # Expected: 1
  ```
- [ ] **BLOCK-02,04**: rule 파일의 `ui/main_window.py` / `core/screen_recorder.py` /
  `core/capture_worker.py` LOC 수치가 실측과 일치.
  ```bash
  wc -l ui/main_window.py core/screen_recorder.py core/capture_worker.py
  # Expected: 1957, 688, 452
  ```
- [ ] **BLOCK-03**: `core/capture_backend.py` LOC 수치 갱신 확인.
  ```bash
  wc -l core/capture_backend.py
  # Expected: 780
  ```
- [ ] **BLOCK-05**: `core/gif_encoder.py` LOC 수치 신규 기재 확인 (rule 양쪽).
  ```bash
  grep -E "gif_encoder.py.*[0-9,]+ LOC" .claude/rules/workflow-orchestrator.md .claude/rules/harness-invocation.md
  # Expected: 2 matches
  ```
- [ ] **BLOCK-06**: `harness-invocation.md:131` prelude-release-engineer의 XGif.spec
  언급이 "동적 생성" 문맥으로 변경됨.

### ASK 결정 반영 확인

- [ ] **ASK-01**: `cli-tool-builder/skill.md` 상단 override 노트 추가 or `CLAUDE.md`
  각주 추가. 메인 세션의 다음 `/cli-tool-builder` 실행에서 2-agent 체인이 정확히
  호출되는지 확인.
- [ ] **ASK-02**: `CLAUDE.md:57-60` 또는 prelude 본문에 "서브에이전트 AskUserQuestion
  금지 + Escalations 기록" 명시적 문장 반영.

### NOTE 개선 (선택)

- [ ] **NOTE-01**: meta-leakage 잔재 수정 여부 (작성자 재량).
- [ ] **NOTE-02**: `.venv/` 복구 여부 (사용자 환경).
- [ ] **NOTE-03**: testing-standards.md 테이블 재구성 여부.

### 정합성 재검증 (Audit 재실행 간편화)

- [ ] `wc -l ui/main_window.py core/capture_backend.py core/gif_encoder.py core/screen_recorder.py core/capture_worker.py`
- [ ] `grep -E "^ {4}\"(ui|core)/" .claude/rules/workflow-orchestrator.md | wc -l` → 3
- [ ] `grep -c "AskUserQuestion" .claude/rules/*.md CLAUDE.md` → 메인/서브 구분 문맥 여부 확인

---

## 맺음말

본 감사는 `harness-audit` 플레이북을 따라 구성 중심 진단을 수행했다. 런타임/운영 부채
(세션 복구, 재시도 루프, 이중 관리 drift)는 `/harness-architect:ops-audit`에 위임 권고.

솔로 개발자 패턴은 유지됐다: `CLAUDE.local.md` 우선순위, `.gitignore` 포함 여부,
settings.local.json 빈 allow 배열 — 모두 정상. 팀 규모가 1인임을 반영한 간소한 allowlist
와 deny 목록이 Phase 7에서 검증됐고 이번 감사에서도 변화 없음.

수정 범위 우선순위:
1. 즉시(BLOCK-01~06): hook drift와 LOC 재동기화.
2. 단기(ASK-01, ASK-02): skill.md와 CLAUDE.md override/단서 추가.
3. 장기(NOTE-01~03): cosmetic 정리, 환경 복구, 문서 구조 개선.

모든 수정은 메인 세션이 Edit으로 적용한다. 본 `09-audit-findings.md`는 덮어쓰지 않고
보존할 것.
