---
phase: 5
completed: 2026-04-20T24:30:00Z
status: done
advisor_status: pending
---

# Agent Team — XGif

## Summary

XGif는 사전 설치된 harness-100의 20개 에이전트 중 **17개를 활성 재사용**하고, **3개는 본 프로젝트에서 비활성**(`command-designer`, `core-developer`, `test-engineer`)으로 분류한다. 본 Phase 5는 **신규 에이전트 프로비저닝을 수행하지 않으며**, 기존 에이전트 `.md` 파일도 수정하지 않는다(공유 설치 리소스 원칙 — 다른 프로젝트와 `.claude/agents/` 디렉토리를 공유해 upstream harness-100 업데이트와 호환 유지). 메인 세션은 D-1 오케스트레이터 패턴(라우터-only)이며, 사용자의 슬래시 커맨드(`/code-reviewer`, `/test-automation`, `/performance-optimizer`, `/cli-tool-builder`) 진입마다 ①진입 클린업(`_workspace/` → `_workspace.prev-{ts}/`로 리네임 후 빈 `_workspace/` 재생성), ②5종 XGif 컨텍스트 프리루드 주입, ③하네스 스킬 소환을 수행한다. 하네스 내부 SendMessage 그래프는 기존 skill.md가 이미 정의하고 있어 재정의하지 않고 참조만 한다. Phase 6(skill-forge)은 본 산출물의 소환 컨트랙트 전체를 `.claude/rules/workflow-orchestrator.md` 한 파일로 인코딩해야 하며, 산출물은 Phase 어휘(`Phase 1..9`, `harness-architect`, `Advisor` 등)를 포함하지 않는다.

## Team Structure

**솔로 개발자 프로젝트 — 팀 단위(`TeamCreate`)를 사용하지 않는다.** 사전 설치된 4개 하네스 각각이 이미 5-agent 체인을 내장하고 있어 추가 `TeamCreate` 호출은 중복이다. 본 프로젝트는 모델 B(서브에이전트 소환 — 하네스 스킬이 Task/SendMessage로 내부 5명을 오케스트레이션)에 의존한다.

논리적 클러스터(하네스 단위)는 다음과 같이 구분되며, 각 클러스터는 자기 하네스 스킬 진입 시에만 활성화된다:

- **Test cluster** (harness: test-automation) — 5명
- **Review cluster** (harness: code-reviewer) — 5명
- **Performance cluster** (harness: performance-optimizer) — 5명
- **Release cluster** (harness: cli-tool-builder) — 2명 활성 / 3명 비활성

독립 에이전트(팀 소속 무관, 단발 소환): `architecture-reviewer`는 L-grade STEP 1(Explore)에서 plan.md 리뷰용으로 `code-reviewer` 클러스터 밖에서 단독 소환될 수 있다. `optimization-engineer`는 STEP 2(Implement)에서 자문용으로 단독 소환 가능하다(`core/` 쓰기는 메인 세션 승인 필요).

### 전체 20개 에이전트 전수표

| # | 에이전트 | 활성 | 역할 | 소속 하네스 | 트리거 스텝 |
|---|---------|------|------|------------|------------|
| 1 | test-strategist | yes | 테스트 전략 / 피라미드 / CI 설계 | test-automation | STEP 3 |
| 2 | unit-tester | yes | core/cli pytest 단위 테스트 | test-automation | STEP 3 |
| 3 | integration-tester | yes | capture→encode 파이프라인 통합 테스트 | test-automation | STEP 3 |
| 4 | coverage-analyst | yes | 커버리지 갭 분석 / P0·P1 테스트 우선순위 | test-automation | STEP 3 |
| 5 | qa-reviewer | yes | 테스트 품질 최종 리뷰 (내재 리뷰어) | test-automation | STEP 3 |
| 6 | style-inspector | yes | ruff 컨벤션 / ban-list 검출 | code-reviewer | STEP 4 (M·L) |
| 7 | security-analyst | yes | 인젝션·subprocess·bare except 누수 | code-reviewer | STEP 4 (L만) |
| 8 | performance-analyst | yes | 프레임 패스 핫스팟 / 락 경합 | code-reviewer | STEP 4 (L만) |
| 9 | architecture-reviewer | yes | 모듈 경계 / wx import 금지 / God Object | code-reviewer | STEP 1 (L), STEP 4 (M·L) |
| 10 | review-synthesizer | yes | 리뷰 종합 / 우선순위 / 최종 판정 (내재 리뷰어) | code-reviewer | STEP 4 (M·L) |
| 11 | profiler | yes | cProfile / line_profiler 측정 | performance-optimizer | STEP 5 (L 조건부) |
| 12 | bottleneck-analyst | yes | 병목 근본 원인 / 우선순위 | performance-optimizer | STEP 5 (L 조건부) |
| 13 | optimization-engineer | yes | 링버퍼 / DXCam 풀링 / SharedMemory 구현 | performance-optimizer | STEP 2 자문, STEP 5 (L 조건부) |
| 14 | benchmark-manager | yes | before/after FPS·encode·메모리 | performance-optimizer | STEP 5 (L 조건부) |
| 15 | perf-reviewer | yes | 회귀 방지 검증 (내재 리뷰어) | performance-optimizer | STEP 5 (L 조건부) |
| 16 | release-engineer | yes | PyInstaller + Inno Setup 빌드 / smoke-test | cli-tool-builder | STEP 6 |
| 17 | docs-writer | yes | CHANGELOG append / 릴리스 노트 | cli-tool-builder | STEP 6·7 |
| 18 | command-designer | **no** | (범용: 신규 CLI 설계) — XGif는 기존 CLI 유지 | cli-tool-builder | — |
| 19 | core-developer | **no** | (범용: CLI 핵심 구현) — 본 체인은 구현을 메인 세션이 수행 | cli-tool-builder | — |
| 20 | test-engineer | **no** | (범용: CLI 테스트) — STEP 3의 test-automation이 우선 | cli-tool-builder | — |

합계: **활성 17 / 비활성 3 / 신규 0**.

## Orchestrator Pattern Decision

**D-1 (순수 오케스트레이터, 메인 세션 = 라우터).**

판별 근거:
- 에이전트 수 ≥ 3 (17개)
- 체인 깊이 최대 5단계 (test-automation / code-reviewer / performance-optimizer)
- 메인 세션은 Complexity Gate 평가와 하네스 스킬 소환만 수행하며, 방법론(pytest 실행, 코드 리뷰 수행, 벤치마크)을 직접 실행하지 않는다
- 사용자 진입점은 `/code-reviewer`, `/test-automation`, `/performance-optimizer`, `/cli-tool-builder` 4개 슬래시 커맨드 — 이는 D-2(하이브리드, 진입점 스킬)의 형태로 보일 수 있으나, **진입점 스킬이 이미 설치된 하네스의 기존 skill.md이므로 본 프로젝트에서 새 진입점 스킬을 제작하지 않는다**. Phase 6이 신규 제작하는 것은 `.claude/rules/workflow-orchestrator.md` 규칙 파일 1개뿐이다
- 따라서 WHO/HOW 분리의 HOW 위치는 **이미 존재하는 `.claude/skills/{harness}/skill.md`** 이며, 본 프로젝트가 새로 생산할 파일은 규칙 파일뿐이다 → D-1 pure

**Phase 6 저장 위치 결정 영향**: 본 Phase 5는 `playbooks/` 신규 파일을 만들지 않으며, Phase 6 또한 `.claude/skills/` 신규 스킬을 만들지 않는다. 유일한 신규 산출물은 `.claude/rules/workflow-orchestrator.md` (always-apply 규칙)이다.

## Agent-Skill Ownership Table

| 에이전트 | 담당 스킬 (소환 시 사용) | 예상 저장 위치 |
|---------|------------------------|-------------|
| test-strategist | test-automation (주), test-design-patterns (확장) | `.claude/skills/test-automation/skill.md`, `.claude/skills/test-design-patterns/skill.md` |
| unit-tester | test-automation, mocking-strategy | `.claude/skills/test-automation/skill.md`, `.claude/skills/mocking-strategy/skill.md` |
| integration-tester | test-automation, mocking-strategy | 위와 동일 |
| coverage-analyst | test-automation | `.claude/skills/test-automation/skill.md` |
| qa-reviewer | test-automation | 위와 동일 |
| style-inspector | code-reviewer | `.claude/skills/code-reviewer/skill.md` |
| security-analyst | code-reviewer, vulnerability-patterns | `.claude/skills/code-reviewer/skill.md`, `.claude/skills/vulnerability-patterns/skill.md` |
| performance-analyst | code-reviewer, refactoring-catalog | `.claude/skills/code-reviewer/skill.md`, `.claude/skills/refactoring-catalog/skill.md` |
| architecture-reviewer | code-reviewer, refactoring-catalog | 위와 동일 |
| review-synthesizer | code-reviewer | `.claude/skills/code-reviewer/skill.md` |
| profiler | performance-optimizer | `.claude/skills/performance-optimizer/skill.md` |
| bottleneck-analyst | performance-optimizer, refactoring-catalog | `.claude/skills/performance-optimizer/skill.md`, `.claude/skills/refactoring-catalog/skill.md` |
| optimization-engineer | performance-optimizer, caching-strategy-selector | `.claude/skills/performance-optimizer/skill.md`, `.claude/skills/caching-strategy-selector/skill.md` |
| benchmark-manager | performance-optimizer | `.claude/skills/performance-optimizer/skill.md` |
| perf-reviewer | performance-optimizer | 위와 동일 |
| release-engineer | cli-tool-builder | `.claude/skills/cli-tool-builder/skill.md` |
| docs-writer | cli-tool-builder | 위와 동일 |

**소유권 원칙 예외**: 일부 확장 스킬(test-design-patterns, mocking-strategy, refactoring-catalog 등)은 **복수 에이전트가 공유 참조**한다. 이는 사전 설치된 harness-100 설계에 기인하며(확장 스킬은 도메인 레퍼런스 역할), 본 프로젝트의 변경 사항이 아니다. 소유권 충돌은 발생하지 않는다 — 확장 스킬들은 읽기 전용 레퍼런스이며, `_workspace/`에 쓰지 않는다.

**XGif 고유 스킬 신규 제작 없음**. query-optimization-patterns(DB용)·ux-linter·arg-parser-generator 등 미사용 확장 스킬은 본 프로젝트에서 소환 경로가 없다(DB·UX·CLI 설계 모두 범위 외).

## Agent Identities

**파일 미수정 원칙**: 본 섹션은 에이전트 `.md` 파일의 내용을 복제하지 않으며, 각 에이전트가 XGif 컨텍스트에서 수행하는 역할만 요약한다. 실제 WHO 정의는 `.claude/agents/{name}.md` (사전 설치 원본)에 있고, XGif-고유 제약은 **소환 시 주입되는 프리루드**로 전달된다(Phase 6 규칙 파일 책임).

| 에이전트 | XGif 컨텍스트에서의 페르소나 요약 | 프리루드 필요 여부 |
|---------|-----------------------------|-----------------|
| test-strategist | capture→encode 파이프라인의 테스트 피라미드 설계 (pytest 중심, GUI 자동화 제외) | 간접 (integration-tester 프리루드 참조) |
| unit-tester | core/·cli/ wx-free 단위 테스트 작성 | 간접 (프로젝트 rules/testing-standards.md 참조) |
| integration-tester | DXCam/GDI/FastGDI mock + FFmpeg subprocess stub + 프레임 버퍼 플로우 | **필수** — HTTP/DB 가정 차단 |
| coverage-analyst | core/ 80% / cli/ 90% / editor/core/ 70% 목표 | 없음 |
| qa-reviewer | 테스트 품질 최종 판정 (내재 리뷰어) | 없음 |
| style-inspector | ruff + CLAUDE.md ban-list(bare except, self.Bind(wx.EVT_MENU), DPI 2, cli/core wx-import) | **필수** — Black/flake8 제안 차단 |
| security-analyst | Windows subprocess injection, path traversal, bare except leaks | 없음 (일반 규칙 충분) |
| performance-analyst | 프레임 패스 핫스팟, 락 경합, FFmpeg 파이프 throughput | 없음 (STEP 4 리뷰 범위) |
| architecture-reviewer | 모듈 경계(`core/` ↔ `ui/` 단방향, `cli/` wx 금지, `editor/` 독립, `BootStrapper/` 독립) + GOD_OBJECTS 4개 | **필수** — 범용 SOLID 대신 프로젝트 경계 강조 |
| review-synthesizer | 리뷰 종합 + 최종 판정 (내재 리뷰어) | 없음 |
| profiler | cProfile/line_profiler — 캡처/인코드 패스 측정 | 없음 |
| bottleneck-analyst | 프레임 카피 오버헤드, FFmpeg 파이프 throughput, GPU/CPU 분기 | 없음 (optimization-engineer 프리루드에 컨텍스트 포함) |
| optimization-engineer | DXCam 풀링, FastGDI ring buffer, SharedMemory, CuPy fallback, wx.CallAfter | **필수** — 최적화 타겟 영역 명시 |
| benchmark-manager | before/after FPS·encode time·메모리 | 없음 |
| perf-reviewer | 회귀 방지 (race condition, 동기화 누락) | 없음 |
| release-engineer | PyInstaller + Inno Setup (PyPI/npm/Homebrew/Docker **아님**), `core/version.py` SSoT, BootStrapper 범위 외 | **필수** — CI/PyPI 제안 차단 |
| docs-writer | CHANGELOG append-only (한국어 허용 `{타입}: {설명}`) | 없음 (커밋 메시지 규칙은 CLAUDE.md 참조) |

**프리루드 필수 5명**: integration-tester, style-inspector, architecture-reviewer, optimization-engineer, release-engineer. 본문은 `03-pipeline-design.md > Context Injection Requirements for Phase 5` 에 이미 수록되어 있다(복제 금지 — SSoT 유지).

## Communication Patterns

### 메인 세션 ↔ 하네스 스킬

- 구현: Task 도구 호출 또는 슬래시 커맨드 실행(`/code-reviewer`, `/test-automation`, `/performance-optimizer`, `/cli-tool-builder`)
- 호출 시점마다 다음을 선행 주입: ①진입 클린업 명령 → ②XGif 컨텍스트 프리루드(해당 에이전트 소환 대상이 있으면) → ③등급·도메인 메타데이터
- 주입 반복 규칙: LLM은 세션 내 프리루드를 캐시할 수 없으므로, **매 소환마다 새로 주입**한다

### 하네스 내부 5-agent SendMessage 그래프

하네스별 내부 소통 그래프는 **기존 skill.md가 이미 정의**하고 있어 본 산출물에서 재정의하지 않는다. 각 하네스의 skill.md `Phase 2: 팀 구성 및 실행` 표와 `팀원 간 소통 흐름` 블록이 SSoT이다. 참조만 기록한다:

| 하네스 | skill.md 경로 | 핵심 그래프 요약 (skill.md 인용) |
|-------|--------------|-------------------------------|
| test-automation | `.claude/skills/test-automation/skill.md` | strategist → (unit-tester ∥ integration-tester) → coverage-analyst → qa-reviewer. qa-reviewer가 🔴 필수 수정 발견 시 해당 에이전트에 SendMessage (최대 2회) |
| code-reviewer | `.claude/skills/code-reviewer/skill.md` | (style-inspector ∥ security-analyst ∥ performance-analyst ∥ architecture-reviewer) 4-way 팬아웃 → review-synthesizer 팬인. 상호 SendMessage: style→security(주석 내 민감 정보), style→performance(복잡 함수 목록), security→performance(조치 성능 영향), security→architecture(인증 아키텍처), performance→architecture(구조적 병목) |
| performance-optimizer | `.claude/skills/performance-optimizer/skill.md` | profiler → bottleneck-analyst → optimization-engineer → benchmark-manager → perf-reviewer. 순차. perf-reviewer가 회귀 우려 발견 시 optimization-engineer에 SendMessage (최대 2회) |
| cli-tool-builder | `.claude/skills/cli-tool-builder/skill.md` | 본 프로젝트는 2-agent 부분 사용(release-engineer + docs-writer). 두 에이전트는 SendMessage로 버전/빌드 결과를 교차 확인 |

### 파일 핸드오프

- `_workspace/` 루트 단일 공유(Option A+ 결정). 모든 에이전트가 직접 쓰기
- 하네스 간 격리는 **시간적 분리**로 달성: 진입 클린업 → 현 하네스 실행 → 다음 하네스 진입 시 또 클린업
- 이전 산출물은 `_workspace.prev-{timestamp}/`로 보존(최대 3개, 오래된 것부터 삭제)

### 훅 (Phase 7-8 설치 대상)

- `precommit-m-grade-reminder.sh` — M-grade 감지 시 `/code-reviewer` 권장 non-blocking 출력
- (선택) `postwrite-s-grade-ruff.sh` — S-grade Edit 후 `ruff check --fix` 자동 실행

## Summon Contracts

각 하네스 진입점에 대한 메인 세션의 소환 컨트랙트. Phase 6 규칙 파일이 이 전부를 인코딩해야 한다.

### Contract A — `/code-reviewer`

**Pre-conditions**:
1. **진입 클린업 의무 실행**: 기존 `_workspace/` 존재 시 `mv _workspace _workspace.prev-{YYYYMMDD-HHMMSS}/` 후 `mkdir _workspace`
2. `_workspace.prev-*` 폴더 수 > 3이면 가장 오래된 것부터 삭제
3. 현재 grade·domain 확정(Complexity Gate 평가 완료)

**필수 프리루드 주입** (각 에이전트 소환 직전):
- 대상 에이전트에 `style-inspector`가 포함되면 → **prelude-style-inspector** 주입
- 대상 에이전트에 `architecture-reviewer`가 포함되면 → **prelude-architecture-reviewer** 주입
- (프리루드 본문은 `03-pipeline-design.md > Context Injection Requirements for Phase 5` 참조)

**모델 티어 기본값**: 16/17 에이전트 sonnet, `architecture-reviewer`는 L-grade에서 opus 오버라이드. `--opus` 플래그가 특정 에이전트에 주어지면 해당 에이전트만 opus로 승격.

**실행 모드**:
- L-grade: 5-agent 풀 파이프라인 (style + security + performance + architecture + synthesizer)
- M-grade: **3-agent 감축** (style + architecture + synthesizer)
- `--review=full` 플래그 있으면 M-grade도 5-agent 풀로 실행
- S-grade: 하네스 소환 없음 (메인 세션이 `ruff check` 수동 실행)

**Post-conditions**: `_workspace/00_input.md`, `_workspace/0{1..4}_*_review.md` (해당 에이전트만), `_workspace/05_review_summary.md` 생성. High-severity 미해결 시 review-synthesizer가 BLOCK 처리 → 메인 세션이 사용자에게 보고.

### Contract B — `/test-automation`

**Pre-conditions**: 진입 클린업 + grade·domain 확정. `ui-only-skip` 플래그(gif-editor 도메인 editor/ui/ 전용 변경) 시 소환 금지 — 수동 스모크 안내만.

**필수 프리루드 주입**:
- `integration-tester` 소환 직전 → **prelude-integration-tester** 주입 (HTTP/DB 가정 차단)

**모델 티어**: 5명 모두 sonnet 기본.

**실행 모드**:
- M·L-grade: 5-agent 풀 파이프라인
- S-grade: 하네스 소환 없음 (메인 세션이 pytest 수동 실행)
- BootStrapper 도메인: **항상 비활성** (BAT 인스톨러, pytest 미적용)

**Post-conditions**: `_workspace/00_input.md` ~ `_workspace/05_review_report.md` 생성. 신규 테스트 파일은 `tests/` 또는 `tests/integration/`에 직접 커밋. pytest 실행 결과(pass/fail)를 메인 세션이 사용자에 보고.

### Contract C — `/performance-optimizer`

**Pre-conditions**: 진입 클린업 + L-grade 확정 + (`[performance-review]` 플래그 있거나 프로파일러 회귀 감지).

**필수 프리루드 주입**:
- `optimization-engineer` 소환 직전 → **prelude-optimization-engineer** 주입 (DXCam 풀링, FastGDI ring buffer, SharedMemory, CuPy fallback, wx.CallAfter)

**모델 티어**: 5명 모두 sonnet 기본.

**실행 모드**: L-grade 조건부. 5-agent 순차 파이프라인. **병렬 금지**(이전 산출이 다음 입력).

**`optimization-engineer` 쓰기 범위 예외**:
- 기본은 `_workspace/` 직접 쓰기 허용
- 그러나 **`core/` 소스 수정은 메인 세션 승인 필요**. 규칙 파일에 "optimization-engineer는 구현 주입 시 `_workspace/03_optimization_plan.md`에 제안만 작성하고, 메인 세션이 확인 후 Edit 도구로 `core/`에 반영한다" 규약 기록.

**Post-conditions**: `_workspace/01_profiling_report.md` ~ `_workspace/05_review_report.md`. benchmark 결과(before/after FPS·encode·메모리)는 사용자 요청 시 git commit으로 보존.

### Contract D — `/cli-tool-builder`

**Pre-conditions**: 진입 클린업 + (STEP 6 릴리스 인텐트 또는 BootStrapper 도메인 태스크).

**필수 프리루드 주입**:
- `release-engineer` 소환 직전 → **prelude-release-engineer** 주입 (PyInstaller + Inno Setup, BootStrapper 범위 외)

**모델 티어**: release-engineer sonnet, docs-writer sonnet.

**실행 모드**: **2-agent 부분 파이프라인만**. `command-designer` / `core-developer` / `test-engineer` 3명은 본 프로젝트에서 항상 비활성. 소환 프롬프트에 "이 세션에서 활성 에이전트는 release-engineer + docs-writer" 명시.

**Post-conditions**:
- `dist/XGif_{version}.exe` (PyInstaller)
- `installer/XGif_Setup_{version}.exe` (Inno Setup)
- `_workspace/04_documentation.md` + `CHANGELOG.md` append
- `_workspace/05_release_config.md` (build log 요약)
- smoke-test 실패 시 메인 세션이 build log를 사용자에게 보고 후 수동 디버깅 요청

## Cross-Cutting Contracts

이 절의 규약은 모든 하네스 소환에 공통 적용된다.

### 진입 클린업 프로토콜

**의무 발동 조건**: 사용자가 4개 슬래시 커맨드(`/code-reviewer`, `/test-automation`, `/performance-optimizer`, `/cli-tool-builder`) 중 하나를 호출.

**프로토콜** (메인 세션이 스킬 실행 직전에 수행):
1. `_workspace/` 디렉토리 존재 확인
2. 존재 시: `mv _workspace _workspace.prev-{YYYYMMDD-HHMMSS}/` — 삭제 아님, 리네임. 직전 하네스 결과를 사용자가 재참조 가능하게 보존
3. `_workspace.prev-*` 폴더 수가 3을 초과하면 가장 오래된 것부터 삭제(4개 이상 생기지 않게)
4. `mkdir _workspace` — 빈 디렉토리 재생성
5. 스킬 진입

**병렬 실행 금지**: 동시에 두 개의 슬래시 커맨드를 실행하지 않는다. 하나가 끝난 뒤에만 다음을 호출 — `_workspace/` 공유 충돌 방지.

**Phase 7-8 gitignore**: `_workspace/`, `_workspace.prev-*` 둘 다 `.gitignore` 추가 대상.

### `--review=full` 옵션 핸들링

- 기본: M-grade STEP 4 = 3-agent(style + architecture + synthesizer)
- `--review=full` 플래그: M-grade도 5-agent(security, performance 추가) 실행
- L-grade는 항상 5-agent. 플래그 효과 없음
- 규칙 파일에 "사용자가 수동으로 full 리뷰를 원할 때만 의도적으로 켠다" 기재

### `--opus` 옵션 핸들링

- 기본: 16/17 에이전트 sonnet
- `architecture-reviewer` L-grade 자동 opus (오버라이드)
- `--opus={agent-name}` 플래그: 해당 에이전트만 opus로 승격. 예: `/code-reviewer --opus=security-analyst`
- 솔로 프로젝트 + Opus 비용 감당 가능 전제(01-discovery-answers.md A5 `고성능형` 확정)

### GOD_OBJECTS 등급 승격 규칙

**SSoT 4-파일 리스트**:
```
GOD_OBJECTS = {
    "ui/main_window.py",           # 1,983 LOC, UI 엔트리 포인트
    "core/screen_recorder.py",      # 캡처 orchestrator
    "core/capture_backend.py",      # DXCam/FastGDI/GDI 다중 분기
    "core/gif_encoder.py",          # FFmpeg 파이프 제어
}
```

**Critical dirs**: `editor/ui/`

**승격 규칙**:
- diff에 GOD_OBJECTS 또는 `editor/ui/` 접두사 파일 포함 → 최소 M-grade 강제
- S-grade 판정이 나와도 이 조건을 만족하면 M으로 상향
- 다운그레이드는 사용자가 명시적 `--grade=S` 요청할 때만

### 쓰기 범위 일반 규약

**Option A+ 채택 결과**: 모든 활성 에이전트는 `_workspace/` 루트에 직접 쓴다. 서브디렉토리 기반 권한 분리는 없다. 대신 **시간적 분리**(진입 클린업)로 하네스 간 충돌 방지.

**핵심 제약**:
| 구분 | 쓰기 허용 |
|------|----------|
| 모든 하네스 에이전트 | `_workspace/` (자기 세션 내) |
| unit-tester / integration-tester | 추가로 `tests/`, `tests/integration/` |
| optimization-engineer | 추가로 `core/` — **메인 세션 확인 후에만**. 제안은 `_workspace/03_optimization_plan.md`에 기록 |
| benchmark-manager | 추가로 `tests/benchmarks/` (존재 시) |
| docs-writer | 추가로 `CHANGELOG.md` |
| release-engineer | 추가로 build log만 (소스 미수정) |

**소스 파일 수정 원칙**: 테스트 코드, CHANGELOG.md 외의 소스 수정은 메인 세션이 승인 후 Edit.

**디렉토리 분리 기반 권한 enforcement는 채택하지 않는다** (Option A+ 결정). Phase 6 규칙 파일은 위 표를 텍스트 규약으로 기록하되 PreToolUse 훅으로 강제하지 않는다(솔로 프로젝트 오버헤드 최소화).

## Agent Prelude Index

5종 XGif 컨텍스트 프리루드. **본문은 `03-pipeline-design.md` §`Context Injection Requirements for Phase 5`에 수록**되어 있어 본 산출물은 크로스 레퍼런스 맵만 제공한다 — 복제 금지 원칙(SSoT 유지).

| Prelude 이름 | 대상 에이전트 | 발동 하네스 | 본문 위치 |
|-------------|-------------|------------|----------|
| prelude-release-engineer | release-engineer | `/cli-tool-builder` (STEP 6) | `03-pipeline-design.md` §`주입 대상 #1` |
| prelude-integration-tester | integration-tester | `/test-automation` (STEP 3) | `03-pipeline-design.md` §`주입 대상 #2` |
| prelude-style-inspector | style-inspector | `/code-reviewer` (STEP 4, 모든 grade) | `03-pipeline-design.md` §`주입 대상 #3` |
| prelude-architecture-reviewer | architecture-reviewer | `/code-reviewer` (STEP 4) + 단독 소환 (L STEP 1) | `03-pipeline-design.md` §`주입 대상 #4` |
| prelude-optimization-engineer | optimization-engineer | `/performance-optimizer` (STEP 5) + 인라인 자문 (STEP 2) | `03-pipeline-design.md` §`주입 대상 #5` |

**Phase 6 인코딩 규약**: 각 프리루드를 `.claude/rules/workflow-orchestrator.md`의 `## Agent Prelude Bindings` 섹션에 그대로 복사하되, 다음 단어를 치환·제거한다 (meta-leakage 차단):
- "Phase X", "phase-Y" → 제거 또는 "this workflow" 등으로 의역
- "Advisor", "Red-team Advisor", "NOTE Dim N" → 제거
- "harness-architect", "skill-forge", "agent-team" → 제거
- "03-pipeline-design.md" 내부 링크 → 독립 문장으로 풀어 씀

프리루드는 각 ≤300자(한국어 기준)이며, 매 소환마다 새로 주입된다(세션 캐시 불가).

## Ownership Guard Scope

**소유권 가드 불필요 — 단일 세션·순차 실행 프로젝트**.

근거:
- 솔로 개발자, 단일 세션 — 동시 Write 충돌 시나리오 없음
- 순차 실행만 허용(진입 클린업이 이를 강제)
- Option A+에 따라 `_workspace/` 서브디렉토리 기반 권한 분리가 제거됨
- PreToolUse 훅으로 소유권 강제는 오버헤드 대비 가치 낮음(잘못된 위치 Write 발생 시 진입 클린업이 다음 실행에 영향 주지 않도록 흡수)

예외는 있다 — **optimization-engineer의 `core/` 쓰기**는 규약상 "메인 세션 승인"을 요구한다. 이는 훅이 아닌 **규칙 파일 텍스트 규약**으로 기재되고, LLM 준수 기반이다. 실제 위반 시 영향은 `git diff` 확인 단계에서 탐지 가능.

## Phase 6 Handoff

Phase 6(skill-forge)이 **반드시 제작해야 할 신규 산출물**:

### 필수 산출물 (1개)

**`.claude/rules/workflow-orchestrator.md`** — always-apply 규칙 파일. 본 Phase 5의 모든 결정과 `03-pipeline-design.md`의 사양을 통합한다.

필수 포함 섹션(체크리스트):
- [ ] `## Main Session Role` — "라우터-only" 선언, S-grade 예외(메인 세션 직접 구현)
- [ ] `## Complexity Gate` — GOD_OBJECTS 4-파일 SSoT, grade 결정 규칙(S/M/L), 상향 바이어스, editor/ui/ 승격
- [ ] `## Domain Detection` — 파일 경로 접두사(core/·ui/·editor/·BootStrapper/) → 도메인 매핑
- [ ] `## Domain-Harness Activation Matrix` — 도메인별 활성/비활성 하네스 표 (screen-recording / gif-editor / bootstrapper-installer)
- [ ] `## Grade-Step Selection` — S/M/L 등급별 스텝 체인
- [ ] `## Slash Command Mapping` — 4개 슬래시 커맨드 ↔ 하네스 ↔ 워크플로우 스텝
- [ ] `## _workspace Entry Cleanup Protocol` — 진입 클린업 5단계 규약 (mv → mkdir → 3개 초과 삭제)
- [ ] `## Agent Prelude Bindings` — 5개 프리루드 본문 (meta-leakage 필터 적용 후)
- [ ] `## Review Mode Flags` — `--review=full` / `--opus` / `--grade=S` 핸들링
- [ ] `## Optimization-engineer Write Policy` — core/ 수정 시 메인 세션 승인 규약
- [ ] `## Retry Policy` — max_retries / escalation / timeout 표 (03-pipeline-design.md §`Failure Recovery`에서 이관)
- [ ] `## Review Gate Reference` — `.claude/rules/pipeline-review-gate.md` 참조 + 본 프로젝트 분류표
- [ ] `## Hook Invocation` — precommit-m-grade-reminder 탐지 기준(Phase 7-8 설치)

### 규약 사항 (Phase 6 준수 의무)

1. **Meta-leakage 필터 강제**: 규칙 파일은 출하 산출물이므로 다음 용어 금지 — "Phase 1..9", "phase-workflow", "phase-pipeline", "harness-architect", "skill-forge", "agent-team", "Advisor", "Dim N", "Red-team". 허용 용어: "Complexity Gate", "workflow step", "harness", "agent", "skill", "hook", "rule"
2. **파일 규모 ≤ 200줄** (CLAUDE.md 한도와 정합). 초과 시 서브-섹션을 별도 파일로 분리
3. **SSoT 유지**: 프리루드 본문은 `03-pipeline-design.md`에서 복사하되, Phase 6 이후에는 규칙 파일이 새로운 SSoT가 된다. docs/ 산출물은 스크래치패드로 보존
4. **에이전트 `.md` 파일 수정 금지**. 프리루드는 규칙 파일에만 기록. 공유 설치 리소스 원칙 유지

### 선택적 산출물 (Phase 6 판단)

- **per-skill wrapper 규칙**: `workflow-orchestrator.md`가 200줄을 초과하거나 특정 하네스 전용 규약이 복잡해지면 `.claude/rules/harness-{name}-config.md` 로 분리 가능. 기본은 단일 파일 유지

### Phase 6이 제작하지 않을 것 (확정)

- 신규 에이전트 `.md` — 금지 (Phase 5 결정)
- 신규 스킬 `.claude/skills/*/skill.md` — 불필요 (사전 설치 4개 하네스로 충분)
- `playbooks/*.md` — 불필요 (D-1 패턴이지만 HOW 파일은 이미 기존 skill.md에 존재)
- 에이전트 팀 `TeamCreate` 호출 — 불필요 (하네스 내부 5-agent는 skill.md가 오케스트레이션)

## Model Tier Applied

**적용된 Model Tier**: **고성능형** (프롬프트 `[Model Tier]` 필드, 01-discovery-answers.md A5 확정).

### Agent Model Table

| 에이전트 | 역할 | 복잡도 | 모델 | 근거 |
|---------|------|--------|------|------|
| test-strategist | 테스트 전략 설계 | 복잡 설계 | sonnet | 고성능형 매트릭스는 opus지만, 하네스 `.md` 수정 금지 원칙에 따라 **skill.md 기본 모델(sonnet) 유지** |
| unit-tester | pytest 단위 테스트 구현 | 구현 | sonnet | 동일 — 에이전트 `.md` 미수정 |
| integration-tester | 통합 테스트 구현 | 구현 | sonnet | 동일 |
| coverage-analyst | 커버리지 갭 분석 | 단순 검증 | sonnet | 동일 (고성능형 매트릭스는 sonnet으로 일치) |
| qa-reviewer | 테스트 품질 리뷰 | 구현 | sonnet | 동일 |
| style-inspector | ruff + 컨벤션 검사 | 단순 검증 | sonnet | 동일 |
| security-analyst | 보안 취약점 분석 | 복잡 설계 (L-grade에서) | sonnet (기본) / `--opus` 수동 | 동일 — 자동 opus 오버라이드 없음 |
| performance-analyst | 핫스팟 분석 | 구현 | sonnet | 동일 |
| architecture-reviewer | 아키텍처 경계 분석 | 복잡 설계 | sonnet (M) / **opus (L)** | **유일한 자동 오버라이드** — L-grade는 오케스트레이터가 소환 시 `model: opus` 명시. 01-discovery-answers.md `고성능형` + L-grade 설계 리스크 |
| review-synthesizer | 리뷰 종합 | 구현 | sonnet | 동일 |
| profiler | 프로파일링 실행 | 단순 검증 | sonnet | 동일 |
| bottleneck-analyst | 병목 근본 원인 | 복잡 설계 | sonnet | 동일 |
| optimization-engineer | 최적화 구현 | 복잡 설계 | sonnet | 동일. `--opus=optimization-engineer` 수동 승격 가능 |
| benchmark-manager | 벤치마크 | 구현 | sonnet | 동일 |
| perf-reviewer | 회귀 검증 | 구현 | sonnet | 동일 |
| release-engineer | PyInstaller 빌드 | 구현 | sonnet | 동일 |
| docs-writer | CHANGELOG 작성 | 구현 | sonnet | 동일 |

**핵심 원칙**: 에이전트 `.md` frontmatter `model` 필드는 **수정하지 않는다**(upstream harness-100 공유 설치 호환). XGif-고유 모델 티어는 **오케스트레이터가 Task 도구 소환 시 model 파라미터로 명시적 지정**한다. `architecture-reviewer` L-grade가 유일한 자동 오버라이드. 그 외는 모두 `--opus={name}` 수동 플래그.

**16/17 에이전트가 sonnet인 사실상 균형형 비용 프로파일**이나, 사용자가 고성능형을 명시 지정했으므로 `--opus` 경로를 상시 열어둔다.

## Rejected Alternatives

### 기각 1: 에이전트 `.md` 파일 XGif-고유 편집

**옵션**: 5명(integration-tester 등)의 `.md` 파일에 XGif 컨텍스트(프리루드 내용)를 본문 수정으로 삽입.

**기각 사유**: 사전 설치 하네스(harness-100)는 다른 프로젝트와 `.claude/agents/` 디렉토리를 공유한다. 편집 시 upstream 업데이트(`chub update harness-100` 등) 시 충돌·덮어쓰기 위험. 공유 설치 리소스 원칙 유지가 장기 유지보수 비용 최소화.

### 기각 2: 신규 도메인 레드팀 에이전트 프로비저닝

**옵션**: screen-recording-redteam, test-redteam, release-redteam 3명 신규 추가.

**기각 사유**: 3개 하네스에 이미 `qa-reviewer` / `review-synthesizer` / `perf-reviewer` 내재 리뷰어 존재. 추가 레드팀은 "리뷰의 리뷰" 발생 → `.claude/rules/pipeline-review-gate.md` §3 재귀 금지 위반. 솔로 개발자 + 17명으로 충분. (03-pipeline-design.md `기각 1` 재확인)

### 기각 3: 하네스별 `_workspace/{test|review|perf|cli}/` 서브디렉토리

**옵션**: Phase 3 advisor 초기 제안(ASK-1). 각 하네스가 자기 네임스페이스 서브디렉토리 사용.

**기각 사유**: 에이전트 `.md`가 `_workspace/<NN>_xxx.md`를 본문에 하드코드 → 프리루드 경로 치환은 LLM 조언 수준에 그치고 파일시스템 리다이렉트 메커니즘 없음. Phase 4 advisor BLOCK 판정 후 **Option A+(루트 공유 + 진입 클린업)**으로 대체. 본 Phase 5는 Option A+ 계승.

### 기각 4: `TeamCreate`로 공식 팀 편성

**옵션**: 4개 하네스를 `TeamCreate("test-team")`, `TeamCreate("review-team")` 등 Claude Code Teams API로 편성.

**기각 사유**: 하네스 skill.md가 이미 5-agent 오케스트레이션을 내장한다. `TeamCreate`는 중복 레이어이며 솔로 프로젝트 오버헤드만 추가. 모델 B(서브에이전트 소환) 충분.

### 기각 5: `playbooks/` 신규 제작

**옵션**: D-1 패턴이므로 HOW 파일을 `playbooks/` 아래 신규 제작.

**기각 사유**: HOW는 이미 `.claude/skills/{harness}/skill.md`에 존재한다. `playbooks/`는 메인 세션의 자동 디스커버리 회피용이나, 본 프로젝트에서 HOW 진입점은 슬래시 커맨드(skill.md)이며 자동 디스커버리 회피 이슈 없음. 중복 파일 생성 방지.

### 기각 6: PreToolUse 훅으로 쓰기 범위 강제

**옵션**: `.claude/hooks/pre-tool-use-workspace-guard.sh`를 만들어 각 에이전트의 allowed_dirs를 파일시스템 수준에서 강제.

**기각 사유**: Option A+ 결정으로 `_workspace/` 서브디렉토리 기반 권한 분리가 제거됨. 남은 enforcement 대상은 optimization-engineer의 `core/` 쓰기뿐이며, 이는 규칙 파일 텍스트 규약으로 충분(LLM 준수 + git diff 확인). 훅 오버헤드 대비 가치 낮음.

### 기각 7: Model Tier 고성능형 → 모든 에이전트 opus 자동 승격

**옵션**: 01-discovery-answers.md A5 `고성능형`을 따라 17명 전원 opus.

**기각 사유**: 에이전트 `.md` frontmatter 미수정 원칙과 충돌. 전원 opus는 비용 급증(sonnet 대비 5배). 대신 `architecture-reviewer` L-grade만 자동 opus + `--opus={name}` 수동 승격 경로 유지로 유연성 확보.

### 기각 8: wxPython GUI 자동화 테스트 에이전트 신규 추가

**옵션**: `wx-gui-tester` 에이전트 신규 생성 → pywinauto/wx.lib.agw 기반 UI 자동화 테스트.

**기각 사유**: Phase 1-2 NOTE 및 Phase 3 Escalation에서 확정 — 자동 UI 테스트는 Windows 디스플레이 요구 + pytest 통합 불가로 **manual smoke 유지**. 향후 요구 발생 시 별도 하네스로 추가 가능.

## Files Generated

- `D:\ProjectX\XGif_v5\docs\xgif-setup\04-agent-team.md` — 본 파일 (Phase 5 산출물)
- **신규 에이전트 `.md` 파일: 0개** (D-1 패턴이지만 공유 설치 하네스 재사용 원칙에 따라 신규 생성 없음)

## Context for Next Phase

### Orchestrator Pattern Decision
**D-1 (순수 오케스트레이터)**. 메인 세션은 라우터 역할. WHO/HOW 분리에서 WHO는 사전 설치 `.claude/agents/`, HOW는 사전 설치 `.claude/skills/{harness}/skill.md`. 신규 `playbooks/` 생성 불필요.

### 에이전트-스킬 소유권 테이블
§`Agent-Skill Ownership Table` 참조. 17개 활성 에이전트 × 2-3개 스킬(주 스킬 + 확장 스킬). 확장 스킬(test-design-patterns, mocking-strategy, refactoring-catalog, caching-strategy-selector, vulnerability-patterns)은 복수 에이전트가 읽기 전용으로 공유.

### Phase 6이 제작할 스킬 목록 확정
**신규 스킬 0개**. 신규 규칙 파일 1개: `.claude/rules/workflow-orchestrator.md`.

### 각 에이전트 Identity/원칙
§`Agent Identities` 참조. 5명에 프리루드 필수(integration-tester, style-inspector, architecture-reviewer, optimization-engineer, release-engineer). 프리루드 본문은 `03-pipeline-design.md` §`Context Injection Requirements for Phase 5`가 SSoT.

### 팀 구조와 소유권 가드 범위
팀 단위 없음(솔로 + 하네스 내장 오케스트레이션). 소유권 가드 불필요(단일 세션 + 진입 클린업으로 시간적 분리). 예외는 optimization-engineer의 `core/` 쓰기 — 텍스트 규약만.

### Model Tier Applied
**고성능형** (A5 확정). 단, 에이전트 `.md` 미수정 원칙으로 16/17명 sonnet 기본 + `architecture-reviewer` L-grade 자동 opus + `--opus={name}` 수동 플래그 경로.

### Agent Model Table
§`Model Tier Applied > Agent Model Table` 참조.

### Phase 6 핸드오프 체크리스트
§`Phase 6 Handoff`의 필수 포함 섹션 체크리스트 13개. Meta-leakage 용어 필터 의무. 파일 규모 ≤ 200줄.

## Escalations

[NOTE] **신규 에이전트 프로비저닝 0건** — 사전 설치된 17개 에이전트가 7-스텝 워크플로우를 완전 커버. Phase 4 advisor resolution 및 본 Phase 5의 8개 기각 옵션 참조. Phase 6이 추가 에이전트를 제안한다면 본 결정 재검토 필요(현 시점에서는 제안 없음).

[NOTE] **프리루드 SSoT는 `03-pipeline-design.md`** — 본 Phase 5 산출물은 프리루드 본문을 복제하지 않는다. Phase 6 규칙 파일 제작 시 해당 문서에서 직접 복사 + meta-leakage 필터 적용. 복제 금지는 "문서 간 동기화 부담 제거" + "LLM 컨텍스트 중복 비용 절감"을 위함.

[NOTE] **Option A+ 진입 클린업 협약 의존** — 본 팀 설계는 모든 하네스가 `_workspace/` 루트를 공유하되 시간적 분리(진입 클린업)로 충돌을 방지하는 구조에 의존한다. Phase 6 규칙 파일에 `## _workspace Entry Cleanup Protocol` 섹션이 반드시 포함되어야 하며, 누락 시 하네스 간 파일 덮어쓰기 위험. Phase 9 검증 단계에서 이 섹션 존재 여부 필수 체크.

[NOTE] **`architecture-reviewer` L-grade opus 오버라이드 — 에이전트 파일 미수정** — 오케스트레이터가 Task 도구 소환 시 `model: opus` 파라미터를 명시적으로 지정. `.claude/agents/architecture-reviewer.md` frontmatter `model` 필드는 기본값(sonnet 또는 무명시) 유지. Phase 6 규칙 파일의 `## Agent Prelude Bindings` 또는 `## Slash Command Mapping` 섹션에 "L-grade 시 architecture-reviewer는 model=opus 오버라이드" 1줄 기재 필요.

[NOTE] **`optimization-engineer` core/ 쓰기 규약은 LLM 준수 기반** — PreToolUse 훅으로 강제하지 않음(기각 6). Phase 6 규칙 파일의 `## Optimization-engineer Write Policy` 섹션에 "제안은 `_workspace/03_optimization_plan.md`에 작성, `core/` 직접 Edit은 메인 세션 승인 후에만" 규약 명시. 위반은 git diff 단계에서 탐지.

[NOTE] **wxPython GUI 테스트 gap 영구 유지** — Phase 1-2 / Phase 3 결정 계승. 본 팀 편성에 UI 테스트 에이전트 포함 없음. `gif-editor` 도메인의 `editor/ui/*` 변경 시 `ui-only-skip` 플래그로 test-automation 하네스 비활성(manual smoke 안내). 향후 요구 발생 시 Phase 7-8 또는 별도 작업으로 처리.

[NOTE] **BootStrapper 도메인 test-automation 비활성 규약** — 지속 유지. Phase 6 규칙 파일의 `## Domain-Harness Activation Matrix`에 bootstrapper-installer 도메인 → test-automation 비활성 + performance-optimizer 비활성 행 반드시 포함.

## Next Steps

Phase 6: skill-forge 소환 — `.claude/rules/workflow-orchestrator.md` 규칙 파일 1개를 제작한다. 본 산출물의 Summon Contracts / Cross-Cutting Contracts / Agent Prelude Index / Phase 6 Handoff 섹션을 입력으로 사용하고, `03-pipeline-design.md` 의 프리루드 본문을 메타 용어 필터 적용 후 복사한다. 신규 에이전트·스킬·플레이북 생성 없음.

---

## Phase 5 Advisor Resolutions (2026-04-20, 자율 모드)

Advisor verdict: **PASS-WITH-NOTES** (BLOCK 0 / ASK 2 / NOTE 6). 자율 모드로 ASK 2건을
확정 결정, NOTE 중 Phase 6 실행 영향 항목은 본 섹션에 재기술한다.

### RESOLVED-ASK-1: 프리루드 주입 메커니즘 — **orchestrator rule file이 skill.md orchestration을 대체**

Advisor 지적이 정확하다: harness-100 skill.md는 내부에서 Task/SendMessage 호출을 하지만,
main session이 그 호출 경로에 개입해 에이전트별 프리루드를 주입할 표준 메커니즘이 없다.
`.md` 파일 수정 금지 원칙을 지키려면 다음 세 가지 옵션이 있다:

1. **OPT-A: 최상위 prelude 단일 번들** — `/code-reviewer` 호출 시 모든 프리루드를 한 번에
   붙여 skill.md에 전달, 에이전트가 자기 관련 섹션을 self-select.
   - 문제: Task는 새 컨텍스트 생성 — skill에 번들된 프리루드는 skill이 Task 호출 시 재-전송
     해주지 않으면 에이전트까지 도달 안 함.
2. **OPT-B: XGif-wrapper skill 신규 생성** — `/xgif-review` 같은 래퍼 스킬이 프리루드 주입 후
     harness 스킬을 호출.
   - 문제: 신규 스킬 4개 추가 필요, Phase 5 "0 신규 스킬" 원칙 위반.
3. **OPT-C: orchestrator rule file이 harness skill.md의 orchestration을 대체**
   — `workflow-orchestrator.md` 규칙에 각 트리거(`/code-reviewer` 등) 호출 시 main session이
     수행할 **완전한 Task 호출 시퀀스**를 기록. harness skill.md는 참조 문서로 유지하되
     실질 orchestration은 rule file이 담당.
   - 각 Task 호출 시 해당 agent의 프리루드를 main session이 직접 prepend.
   - 에이전트 `.md` 미수정 / 신규 스킬 0 원칙 모두 준수.
   - Task 모델 오버라이드(`architecture-reviewer` opus) 자연스럽게 처리 가능.

**자율 모드 확정 결정**: **OPT-C 채택**.

- `.claude/rules/workflow-orchestrator.md` 가 4개 트리거의 **invocation sequence SSoT**가 된다.
- harness-100 `.claude/skills/*/skill.md` 는 **참조 문서**로 유지, 그러나 main session은 이를
  읽기만 하고 orchestration은 rule file을 따른다.
- 결과: 프리루드는 main session이 각 Task 호출에 직접 삽입 — 도달 보장.
- Trade-off: rule file이 200줄을 초과할 가능성 증가 → NOTE Dim 5 반영하여 **파일 분할을 Phase
  6에 사전 인가**한다.

### RESOLVED-ASK-2: 모델 티어 정당화 수정 — **"비용 우선" 명시**

- `04-agent-team.md` Agent Model Table 및 관련 Rejected Alternatives의 근거 문구 "에이전트
  `.md` 미수정 원칙"은 **기술적 틀림**. Task 호출 시 `model:` 파라미터로 override 가능.
- **수정**: Phase 6 규칙 파일 및 본 산출물의 모델 티어 설명 문구를 **"비용 우선 — 사용자
  고성능형 선택은 architecture-reviewer L-grade opus 자동 + `--opus` 수동 플래그 조합으로
  존중"** 으로 통일.
- `--opus` 수동 플래그는 `workflow-orchestrator.md` `## Review Mode Flags` 섹션에 명시. 사용자가
  특정 실행에서 opus로 승격 원할 때 사용.

### NOTE 반영 (Phase 6 실행 영향 항목)

| NOTE | Phase 6 처리 |
|------|--------------|
| Dim 2 — M-grade plan.md 리뷰어 부재 | `workflow-orchestrator.md` `## Grade-Step Selection` 섹션에 "M-grade: plan.md = solo 자가 리뷰, 자동 에이전트 리뷰 없음 (L-grade 승격 시 architecture-reviewer 프리-구현 리뷰)" 명시. 침묵 아닌 명시적 문서화. |
| Dim 4 — optimization-engineer 쓰기 강제 | `## Optimization-engineer Write Policy` 섹션에 **강제 imperative 문체** 사용: "MUST NOT write directly to `core/` source files. MUST write suggestions to `_workspace/03_optimization_plan.md`. Direct source edits require main-session confirmation." |
| Dim 5 — 200줄 초과 우려 | **파일 분할 사전 인가**. Phase 6 판단으로 다음 분할 허용: `.claude/rules/workflow-orchestrator.md` (메인, 라우팅) + `.claude/rules/harness-invocation.md` (4개 트리거 세부 Task 시퀀스 + 프리루드) + 필요 시 `.claude/rules/complexity-gate.md` (grade 판정 상세). 각 파일 ≤ 200줄. |
| Dim 8 — `_workspace/` 경로 컨벤션 | **Phase 5 flat root가 authoritative**. Phase 3/4의 `_workspace/{alias}/` 서브경로 표기는 superseded. 규칙 파일은 flat root 기준으로 작성 (`_workspace/00_input.md` 형식). |
| Dim 12 — 0 신규 redteam 에이전트 | 유지. qa-reviewer / review-synthesizer / perf-reviewer가 도메인 리뷰어 역할. 규칙 파일에 "도메인-specific external redteam 미채택, 하네스 내재 리뷰어 사용" 명시. |

### Phase 6 지시 변경점 요약

- **산출물**: `.claude/rules/workflow-orchestrator.md` (메인) + **조건부 분할 허용** (≤200줄 기준).
- **핵심 변경**: **rule file이 harness skill.md orchestration 대체**. 각 트리거의 완전한 Task
  호출 시퀀스를 rule에 기록, 프리루드는 main session이 Task 호출마다 prepend.
- **모델 티어 문구**: "비용 우선" 사유로 명시, `--opus` 수동 플래그는 선택 경로로 기록.
- **쓰기 정책**: optimization-engineer에 강제 imperative 문체 적용.
- **M-grade 리뷰 부재**: 침묵 아닌 명시적 문서화.
- **경로 컨벤션**: flat `_workspace/` 루트만 사용 (서브 네임스페이스 표기 superseded).
