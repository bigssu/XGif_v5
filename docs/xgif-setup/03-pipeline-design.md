---
phase: 4
completed: 2026-04-20T23:55:00Z
status: done
advisor_status: pending
---

# Pipeline Design — XGif

## Summary

Phase 3의 7-스텝 워크플로우를 구체적 에이전트 실행 체인과 라우팅 로직으로 옮긴 설계
산출물이다. XGif는 솔로 개발자의 Windows 데스크톱 앱이며 메인 세션은 **라우터-only** 역할
(사용자 요청 수신 → Complexity Gate → 도메인 감지 → 하네스/스킬 소환)만 담당한다. 에이전트는
사전 설치된 4개 하네스(code-reviewer / test-automation / performance-optimizer /
cli-tool-builder)의 17개 기존 에이전트를 **재사용**하고, 본 프로젝트에서는 신규 에이전트를
**프로비저닝하지 않는다**(리뷰 게이트용 도메인 레드팀 에이전트도 생성하지 않음 — 사유는
`## Pipeline Review Gate` 참조). 모든 파이프라인은 Complexity Gate(S/M/L)로 단축되며,
S-grade는 에이전트 0회 소환, M-grade는 핵심 3개 체인(Test → Review 감축판), L-grade는 전체
체인을 거친다. `_workspace/` 충돌 방지를 위해 각 하네스는 자기 네임스페이스 서브디렉터리
(`_workspace/{test|review|perf|cli}/`)를 사용하며, 경로 치환은 오케스트레이터 규칙 파일이
수행한다. 본 산출물은 Phase 5(agent-team)의 프로비저닝 입력 및 Phase 6(skill-forge)의 규칙
파일 스펙 입력으로 직접 연결된다.

## Main Session Role

**라우터 only**. 메인 세션은 다음만 수행한다:

1. 사용자 요청 수신
2. Complexity Gate 평가(파일 수 / 설계 결정 수 / God Object 포함 여부)
3. 변경 대상 도메인 감지(파일 경로 접두사)
4. 등급·도메인에 따라 사전 설치된 하네스 스킬을 순서대로 소환
5. 각 스킬이 반환한 결과를 사용자에게 보고

메인 세션은 **방법론을 직접 실행하지 않는다**(예: 직접 `pytest` 호출·코드 리뷰 스스로 수행
금지). S-grade는 예외적으로 메인 세션이 직접 Read/Edit하여 구현·테스트까지 마친다 — 에이전트
체인 호출 비용을 피하기 위해. M/L-grade는 반드시 하네스 스킬로 위임한다.

판별 신호: 에이전트 수 17개(기존), 체인 깊이 최대 5단계(code-reviewer/test-automation/perf),
사용자 진입점은 슬래시 커맨드 4개. → Phase 5에서 D-1(라우터-only) 기본값 채택.

---

## Main Session Routing (D-1 Decision Tree)

메인 세션이 수신한 모든 개발 태스크에 적용하는 결정 트리. 이 로직은 Phase 6에서
`.claude/rules/workflow-orchestrator.md` 로 구현된다.

### Step A — Complexity Gate 평가 (등급 결정)

```
INPUT: task_description, affected_files (유저가 명시했거나 task에서 추론 가능한 파일 목록)

DECIDE grade:
  IF any(file in GOD_OBJECTS) OR any(file.startswith("editor/ui/")):
      grade = max(grade, "M")      # auto-promote per Advisor NOTE (Dim 4)

  IF len(affected_files) <= 5
     AND no_new_external_dependency
     AND solution_is_obvious:
      grade = "S"
  ELIF len(affected_files) in 6..15 OR design_decisions in 1..2:
      grade = "M"
  ELIF new_feature OR new_library OR complex_dependency OR UI_restructure:
      grade = "L"
  ELSE:
      grade = "M"  # default upward bias

  # God Object override: S 등급이라도 God Object 수정 시 M 강제
  IF grade == "S" AND god_object_in_diff:
      grade = "M"

GOD_OBJECTS = [
    "ui/main_window.py",
    "core/screen_recorder.py",
    "core/capture_backend.py",  # DXCam/GDI/FastGDI 다중 분기, 수정 시 런타임 영향 광범위
]
```

불확실 시 상향(S→M, M→L). 다운그레이드는 사용자가 명시 요청한 경우에만.

### Step B — 도메인 감지

```
domain = None
IF any(path.startswith(("core/", "ui/")) for path in affected_files):
    domain = "screen-recording"
ELIF any(path.startswith("editor/") for path in affected_files):
    domain = "gif-editor"
ELIF any(path.startswith("BootStrapper/") for path in affected_files):
    domain = "bootstrapper-installer"
ELSE:
    domain = "screen-recording"  # 기본값 (루트·설정·테스트 공통 파일)

# 복수 도메인 변경 감지 시 screen-recording을 우선 (가장 보수적 규칙셋)
IF multiple_domains_in_diff:
    domain = "screen-recording"
    log_note("multi-domain change; screen-recording 규칙 적용")
```

### Step C — 도메인별 하네스 활성·비활성

| 도메인 | 활성 하네스 | 비활성 하네스 | 사유 |
|--------|------------|--------------|------|
| screen-recording | test-automation, code-reviewer, performance-optimizer | cli-tool-builder (기본 비활성) | PyInstaller 빌드 태스크일 때만 수동 활성 |
| gif-editor | test-automation (editor/core만), code-reviewer, performance-optimizer | cli-tool-builder | editor/ui는 wxPython GUI → 자동화 테스트 불가, `ui-only-skip` 플래그 설정 |
| bootstrapper-installer | code-reviewer, cli-tool-builder | **test-automation 비활성**, performance-optimizer 비활성 | BAT-기반 인스톨러, pytest 미적용 / 성능 최적화 대상 아님 |

`ui-only-skip` 플래그가 설정되면 STEP 3(test-automation)은 수동 스모크 테스트 안내만 출력하고
하네스 스킬을 소환하지 않는다.

### Step D — 등급별 스텝 선택

```
S-grade:   [STEP 2: Implement] → [STEP 3: Test (경량)] → Done
              └ 메인 세션 직접 구현 (에이전트 0회 소환)
              └ pytest 수동 실행, 새 테스트 추가는 사용자 판단

M-grade:   [STEP 1: Explore] → [STEP 2: Implement] → [STEP 3: Test (harness)]
                                                   → [STEP 4: Review (harness, 2-agent 감축)] → Done
              └ Explore/Implement은 메인 세션
              └ Test는 /test-automation 소환 (5-agent 풀)
              └ Review는 /code-reviewer 감축 모드 (style-inspector + architecture-reviewer + review-synthesizer, 3명)

L-grade:   [STEP 1: Explore] → [STEP 2: Implement] → [STEP 3: Test (harness 풀)]
                                                   → [STEP 4: Review (harness 풀, 5-agent)]
                                                   → [STEP 5: Optimize (해당 시)]
                                                   → [STEP 6: Package (릴리스 시)]
                                                   → [STEP 7: Release (릴리스 시)]
              └ 전체 5-agent 하네스 풀 파이프라인 모두 가능
              └ STEP 5는 plan.md 에 [performance-review] 플래그 있거나 프로파일러 회귀 시에만
              └ STEP 6-7은 사용자가 "릴리스 컷" 명시 요청 시에만
```

### Step E — 도메인별 슬래시 커맨드 매핑 (사용자 진입점)

| 사용자 진입점 | 호출 시점 | 소환 하네스 |
|---------------|-----------|------------|
| (task 시작) | 사용자가 구현 요청 | 메인 세션 Complexity Gate 평가 |
| `/test-automation` | M/L STEP 3, 또는 독립 테스트 확장 | test-automation 하네스 |
| `/code-reviewer` | M/L STEP 4, 또는 독립 PR 리뷰 | code-reviewer 하네스 |
| `/performance-optimizer` | L STEP 5 (조건부) | performance-optimizer 하네스 |
| `/cli-tool-builder` | L STEP 6 (릴리스 시), 또는 BootStrapper 도메인 태스크 | cli-tool-builder 하네스 |

---

## Per-Step Pipelines (Agent Execution Chains)

### STEP -1 — Complexity Gate (메인 세션, 에이전트 0회)

- 실행자: 메인 세션 (라우터)
- 산출물: 내부 결정 (grade, domain) — 파일 미생성
- 실행 시간: ~1초 (규칙 매칭)
- 리뷰 필요: 없음 (결정론적 규칙 적용)

### STEP 1 — Explore (M/L, 메인 세션, 에이전트 0회 기본)

- 실행자: 메인 세션 (필요 시 architecture-reviewer 1회 소환)
- 패턴: 순차 (스캔 → 초안 → 선택적 리뷰)
- 산출물: `docs/tasks/{task-name}/plan.md`
- 선택적 에이전트 소환: L-grade 이면서 architecture 경계 수정 시 `architecture-reviewer` 1명을
  메인 세션이 SendMessage로 호출(plan.md 리뷰만, 파일 수정 금지).
- 실행 시간: 5-15분 (코드 스캔 규모에 따라)

### STEP 2 — Implement (All grades, 메인 세션)

- 실행자: 메인 세션 (필요 시 optimization-engineer 1회 인라인 소환)
- 패턴: 순차 (plan.md 읽기 → 편집 → ruff lint)
- 산출물: 수정된 소스 파일
- 선택적 에이전트 소환: core/ 핫패스 수정이고 최적화 아이디어가 필요할 때
  `optimization-engineer`를 1회 자문용으로 소환(산출물: in-message 조언, 파일 미작성).
- 실행 시간: 가변

### STEP 3 — Test (`/test-automation`, 5-agent 체인)

```
Phase 1 (오케스트레이터 — 메인 세션):
  입력 수집 → _workspace/test/00_input.md 작성 → 실행 모드 결정

Phase 2 (에이전트 체인):
  1. test-strategist  (단독)
     입력:  변경 소스 파일 목록, testing-standards.md, capture→encode 파이프라인 컨텍스트
     출력:  _workspace/test/01_test_strategy.md

  2. unit-tester  ∥  integration-tester   (병렬)
     unit-tester:
       입력: 01_test_strategy.md + core/·cli/ 변경 파일
       출력: _workspace/test/02_unit_tests.md + tests/ 하위 신규 파일
     integration-tester:
       입력: 01_test_strategy.md + 변경 파일
         + **주입 컨텍스트: "XGif는 capture→encode 파이프라인. HTTP/DB 아님.
            통합 테스트는 DXCam/GDI mock, FFmpeg subprocess stub, 프레임 버퍼 플로우에 집중."**
       출력: _workspace/test/03_integration_tests.md + tests/integration/ 신규 파일

  3. coverage-analyst  (순차, unit/integration 완료 후)
     입력: 01 + 02 + 03 + pytest --cov 결과
     출력: _workspace/test/04_coverage_report.md
     SendMessage: 갭 발견 시 unit-tester / integration-tester에 추가 테스트 요청 (최대 2회)

  4. qa-reviewer  (최종)
     입력: 01~04 전체
     출력: _workspace/test/05_review_report.md
     SendMessage: 🔴 필수 수정 발견 시 해당 에이전트에 수정 요청 (최대 2회)

Phase 3 (오케스트레이터 — 메인 세션):
  산출물 검증 → 테스트 실행 결과(pytest pass/fail) 보고
```

**S-grade 대체**: 하네스 소환 없이 메인 세션이 직접 pytest 실행 + 필요시 1~2개 단위 테스트
추가. BootStrapper 도메인은 항상 이 경로(test-automation 비활성).

### STEP 4 — Review (`/code-reviewer`)

**L-grade (풀 파이프라인, 5-agent)**:

```
Phase 1 (오케스트레이터):
  입력 수집 → _workspace/review/00_input.md → diff 경로 정리

Phase 2 (에이전트 체인):
  1a. style-inspector      ]
  1b. security-analyst     ]  모두 병렬 (4-way fan-out)
  1c. performance-analyst  ]
  1d. architecture-reviewer]
     각자 _workspace/review/0{1..4}_*_review.md 산출

  2. review-synthesizer  (1a~1d 완료 후)
     입력: 01~04 전체 + .claude/rules/*.md (5개 규칙) + plan.md
     출력: _workspace/review/05_review_summary.md
     정책: High-severity 미해결 시 finding BLOCK 처리

Phase 3 (오케스트레이터): 최종 판정(Approve/Request Changes/Reject) 사용자 보고
```

**M-grade (감축 파이프라인, 3-agent)**:

```
Phase 2 (감축 체인):
  1a. style-inspector       ]  병렬 2-way
  1b. architecture-reviewer ]
  2.  review-synthesizer  (1a·1b 완료 후)

security-analyst, performance-analyst 스킵.
사유: M-grade는 로컬 변경 범위가 좁고 솔로 개발자 속도 존중.
보안·성능 이슈는 해당 도메인 태스크가 L로 승격될 때 재검증.
```

**S-grade**: 하네스 소환 없음. 메인 세션이 `ruff check` + 아키텍처 boundaries 규칙 수동 확인.

### STEP 5 — Optimize (`/performance-optimizer`, L-grade 조건부)

```
전제: L-grade AND ([performance-review] 플래그 OR 프로파일러 회귀 감지)

Phase 2 (에이전트 체인, 순차):
  1. profiler                (cProfile / line_profiler 실행)  → 01_profiling_report.md
  2. bottleneck-analyst      (핫스팟·근본원인)               → 02_bottleneck_analysis.md
  3. optimization-engineer   (ring buffer, DXCam pooling 등) → 03_optimization_plan.md
  4. benchmark-manager       (before/after FPS·encode time)  → 04_benchmark_results.md
  5. perf-reviewer           (회귀 방지 검증)                 → 05_review_report.md

순차성이 중요 (이전 산출이 다음 입력). 병렬화 없음.

SendMessage 루프: perf-reviewer가 🔴 발견 시 engineer에 수정 요청 (최대 2회)
```

실행 시간 예상: 20-60분 (프로파일러 실측 포함).

### STEP 6 — Package (`/cli-tool-builder`, 2-agent 부분 파이프라인)

XGif는 CLI가 아닌 GUI + 배포 인스톨러이므로 cli-tool-builder의 **일부 에이전트만** 사용.

```
Phase 2 (에이전트 체인, 순차):
  1. release-engineer
     입력: 변경 없는 clean source tree, core/version.py (bumped),
           XGif.spec, build_optimized.py, installer/xgif_setup.iss
           + **주입 컨텍스트 (Advisor NOTE Dim 1):
              "배포 대상은 PyPI/npm이 아니라 PyInstaller + Inno Setup.
               산출물: dist/XGif_{version}.exe, installer/XGif_Setup_{version}.exe.
               BootStrapper/XGif_Setup.bat 은 별도 배포 경로이므로 이 스텝의 범위 밖."**
     작업: build_optimized.py 실행 로그 캡처 → exe 부팅 smoke-test → Inno Setup 빌드 검증
     출력: _workspace/cli/05_release_config.md (build log 요약)

  2. docs-writer  (release-engineer와 병렬 가능)
     입력: core/version.py, 최근 커밋 로그 (git log v{prev}..HEAD)
     작업: CHANGELOG.md 신규 버전 섹션 작성
     출력: _workspace/cli/04_documentation.md + CHANGELOG.md 편집
```

**비활성 에이전트**: `command-designer` (XGif는 기존 CLI 개선 아님), `core-developer`
(본 체인은 코드 변경 없음), `test-engineer` (STEP 3에서 이미 커버).

**BootStrapper 배포는 수동**: BootStrapper는 478MB embedded Python + FFmpeg BAT 기반으로
Python 생태계 외부. 어떤 하네스도 적용 안 됨.

### STEP 7 — Release (메인 세션, 에이전트 ≤1회)

- 실행자: 메인 세션 (git tag, 수동 CHANGELOG 확정)
- 선택적 에이전트 소환: `docs-writer` 1회 (CHANGELOG 초안 작성 보조)
- 산출물: Git tag `v{version}`, CHANGELOG.md 최종본

---

## `_workspace/` Namespace Routing (ASK-1 Resolution)

**선택한 구현**: **옵션 (a) — 오케스트레이터 규칙 파일의 경로 치환**.

### 이유 (Rationale)

3가지 옵션을 비교:

| 옵션 | 장점 | 단점 | 채택 여부 |
|------|------|------|----------|
| (a) 규칙 파일 경로 치환 | 하네스 SKILL.md를 건드리지 않음. 공유 설치 하네스(.claude/skills/* 는 다른 프로젝트와 공유 가능)를 XGif 고유 규칙으로만 오버라이드. | 메인 세션이 스킬 호출 직전 `_workspace/` 문자열을 `_workspace/{alias}/`로 해석해야 함 — 규칙 파일이 이 의미론을 명확히 기재해야 함. | **채택** |
| (b) 명시적 경로 인자 주입 | 스킬 호출부가 자명해짐. | SKILL.md의 `_workspace/` 내부 참조(Phase 2 표)는 여전히 원본 경로 → 인자만으로 커버 불가. 스킬 수정 없이 완결 안 됨. | 기각 |
| (c) cwd 전환 | 단순. | `cd _workspace/test/`는 프로젝트 루트 기반 상대 경로를 깨뜨림(하네스 SKILL이 `tests/`, `core/` 등을 가정). Windows에서 하위 프로세스 간 cwd 전파 취약. | 기각 |

### 규칙 파일 구현 사양 (Phase 6 skill-forge가 제작)

오케스트레이터 규칙 파일(`workflow-orchestrator.md`)에 다음 규정을 포함:

```
## _workspace 네임스페이스 바인딩

하네스 스킬 소환 시, 해당 스킬의 `_workspace/` 참조는 다음과 같이 해석된다:

| 스킬                   | 해석 대상 네임스페이스 |
|------------------------|----------------------|
| /test-automation       | _workspace/test/      |
| /code-reviewer         | _workspace/review/    |
| /performance-optimizer | _workspace/perf/      |
| /cli-tool-builder      | _workspace/cli/       |

오케스트레이터(메인 세션)는 스킬 소환 프롬프트에 다음 한 줄을 **선행 주입**한다:

  "이 파이프라인의 `_workspace/` 은 프로젝트 루트 기준 `_workspace/{alias}/` 를 의미한다.
   모든 중간 산출물(`00_input.md` ~ `05_*.md`)을 이 서브디렉터리에 기록·조회하라."

여기서 {alias}는 소환된 스킬명의 첫 토큰(test|review|perf|cli). 이 주입은 매 소환마다
반복한다(세션 내 캐시 불가 — 스킬 프롬프트는 각 호출에서 신선하게 구성).

또한 각 서브디렉터리가 존재하지 않으면 오케스트레이터가 `mkdir -p _workspace/{alias}/`를
선행 실행하여 디렉터리를 보장한다.
```

**디렉터리 레이아웃**:

```
_workspace/
├── test/      # test-automation 하네스 전용
│   ├── 00_input.md
│   ├── 01_test_strategy.md
│   ├── 02_unit_tests.md
│   ├── 03_integration_tests.md
│   ├── 04_coverage_report.md
│   └── 05_review_report.md
├── review/    # code-reviewer 전용
│   ├── 00_input.md, 01..04_*_review.md, 05_review_summary.md
├── perf/      # performance-optimizer 전용
│   ├── 00_input.md, 01..05_*.md
└── cli/       # cli-tool-builder 전용
    ├── 00_input.md, 04_documentation.md, 05_release_config.md
```

`.gitignore` 추가: `_workspace/` (Phase 7-8 단계에서 반영).

---

## Context Injection Requirements for Phase 5

Advisor NOTE(Dim 1, Dim 7)에 따라, Phase 5(agent-team)가 기존 하네스 에이전트를 소환할 때
**다음 컨텍스트 주입이 필수**다. 주입 방식은 **오케스트레이터 규칙 파일의 "에이전트 프롬프트
프리루드" 블록**이다(에이전트 .md 파일은 수정 금지 — 설치 하네스 원본 유지 원칙).

### 주입 대상 #1 — release-engineer (cli-tool-builder / STEP 6)

```
[Prelude injected at summon time]

당신은 XGif 프로젝트의 릴리스 엔지니어입니다. 이 프로젝트에 대해 다음을 유념하세요:

- 배포 대상: **PyPI/npm/Homebrew가 아닙니다**. PyInstaller + Inno Setup 기반 Windows
  전용 인스톨러입니다.
- 빌드 진입점: `build_optimized.py` (PyInstaller 래퍼, 982 LOC)
- PyInstaller spec: `XGif.spec`
- Inno Setup 스크립트: `installer/xgif_setup.iss`
- 출력 산출물:
  - `dist/XGif_{version}.exe`  (단일 exe, smoke-test 부팅 필수)
  - `installer/XGif_Setup_{version}.exe`  (Inno Setup 산출)
- 버전 관리: `core/version.py` 가 **Single Source of Truth**. 빌드 전 수동 bump 필수.
- GitHub Actions·CI·PyPI 업로드는 XGif에 **없습니다** (manual upload).
- BootStrapper BAT 배포(478MB embedded Python + FFmpeg)는 이 스텝의 범위 **밖**입니다.

CI/CD·PyPI publish·conventional commits 권고를 제안하지 마세요.
```

### 주입 대상 #2 — integration-tester (test-automation / STEP 3)

```
[Prelude injected at summon time]

당신은 XGif 프로젝트의 통합 테스트 엔지니어입니다. 다음을 유념하세요:

- XGif는 **HTTP API 서비스나 DB 백엔드가 아닙니다**. 화면 **capture → 프레임 버퍼 →
  FFmpeg 인코딩** 파이프라인입니다.
- 통합 테스트의 대상:
  - 캡처 백엔드 스위칭 (DXCam / FastGDI / GDI 폴백 체인)
  - FFmpeg 서브프로세스 수명주기 (try-finally로 kill 보장 — rules/ffmpeg-subprocess.md)
  - 프레임 버퍼에서 인코더로의 전달 (SharedMemory 또는 파이프)
  - 에디터: frame collection load/save, Undo/Redo
- HTTP mock, DB containers, REST API 테스트, Testcontainers는 **해당 없음**.
- Pytest fixture 전략: DXCam은 mock, FFmpeg은 stub subprocess, wx 의존 코드는 테스트하지
  않음(아키텍처 경계 — core/ 테스트에 wx import 금지).
- UI 테스트(wx GUI)는 자동화 제외. 이 영역은 manual smoke 유지.

Flask/FastAPI/Django 가정으로 mock DB/API를 제안하지 마세요.
```

### 주입 대상 #3 — style-inspector (code-reviewer / STEP 4, 모든 grade)

```
[Prelude injected at summon time]

당신은 XGif 프로젝트의 스타일 리뷰어입니다. 다음을 유념하세요:

- Linter: **ruff** (target py311, line-length 120). pyproject.toml이 SSoT.
- 코딩 표준: `CLAUDE.md` 의 "## 필수 패턴" 섹션과 `.claude/rules/*.md` 5개 파일.
- 특히 검사할 항목:
  - bare except 금지 → `except Exception:` 사용 (wx-patterns.md)
  - wx.CallAfter() 사용 여부 (GUI 호출이 배경 스레드에서 올 때)
  - FFmpeg subprocess try-finally + kill() 패턴 (ffmpeg-subprocess.md)
  - core/ 에 wx import 금지 (architecture-boundaries.md)
- Black·isort·flake8 제안 금지 — ruff가 커버.
```

### 주입 대상 #4 — architecture-reviewer (code-reviewer / STEP 4)

```
[Prelude injected at summon time]

모듈 경계 검사 기준: `.claude/rules/architecture-boundaries.md`.
- core/ → wx import 금지, core/ ↔ ui/ 의존성 단방향 (ui → core)
- cli/ → wx import 금지
- editor/ → 독립 wxPython 서브시스템, core/ 호출 허용, ui/와 공유 모듈 최소화
- BootStrapper/ → 독립 앱, XGif 본체 모듈 import 금지

God Object 주의 파일: `ui/main_window.py` (1,983 LOC), `core/screen_recorder.py`,
`editor/ui/*` — 이 파일들 수정 시 책임 범위 확장 여부 평가 필요.
```

### 주입 대상 #5 — optimization-engineer (performance-optimizer / STEP 5)

```
[Prelude injected at summon time]

최적화 타겟 영역 (Architecture Review 섹션 5):
- 캡처: DXCam 풀링, FastGDI ring buffer
- 프레임 버퍼: multiprocessing.SharedMemory (대용량 프레임 pickling 금지)
- FFmpeg 파이프: async stderr, 파이프 throughput
- GPU: CuPy 선택적 가속, pynvml 모니터링

UI 스레드 블로킹 금지. 모든 무거운 작업은 별도 프로세스/스레드 (CLAUDE.md "핵심 원칙").
```

### 주입 메커니즘 사양 (Phase 6 skill-forge가 구현)

오케스트레이터 규칙 파일에 "에이전트 프리루드 바인딩" 섹션을 두고, 각 에이전트가 소환될 때
메인 세션이 Task/SendMessage 프롬프트 서두에 해당 프리루드를 삽입한다. 구체 구현 형태:

```
prelude_bindings:
  release-engineer: |
    {prelude-release-engineer 텍스트}
  integration-tester: |
    {prelude-integration-tester 텍스트}
  style-inspector: |
    {prelude-style-inspector 텍스트}
  architecture-reviewer: |
    {prelude-architecture-reviewer 텍스트}
  optimization-engineer: |
    {prelude-optimization-engineer 텍스트}
```

각 프리루드는 ≤ 300자(한국어 기준)로 유지하여 토큰 예산 압박 최소화.

---

## Complexity Gate Heuristics (Pseudo-Rule Form)

Advisor NOTE(Dim 4)에 따라 God Object 수정 시 등급 자동 상향을 추가한 최종 규칙.

```
## Complexity Gate Rule (workflow-orchestrator.md에 포함될 본문)

### 감지 대상 파일 집합 (God Objects / Critical Paths)
GOD_OBJECTS = {
    "ui/main_window.py",           # 1,983 LOC, UI 엔트리 포인트
    "core/screen_recorder.py",      # 캡처 orchestrator
    "core/capture_backend.py",      # DXCam/FastGDI/GDI 다중 분기
    "core/gif_encoder.py",          # FFmpeg 파이프 제어
}

CRITICAL_DIRS = {
    "editor/ui/",                   # 대형 에디터 UI 레이어
}

### Grade 결정 규칙 (상향 우선)

1. IF any file in diff matches GOD_OBJECTS OR starts with any path in CRITICAL_DIRS:
       min_grade = "M"   # 자동 최소 M 승격

2. IF diff introduces new external dependency (requirements*.txt 변경)
      OR diff introduces new subsystem module (core/ 신규 파일):
       grade = "L"

3. ELSE IF len(diff.files) <= 5 AND max(changed_lines_per_file) <= 80
           AND no_rules_touched AND no_tests_new:
       grade = "S"

4. ELSE IF len(diff.files) in 6..15 OR design_decisions in 1..2:
       grade = "M"

5. ELSE:
       grade = "L"

6. grade = max(grade, min_grade)   # God Object 승격 반영

### 상향 바이어스
불확실 시 항상 상향. 다운그레이드는 사용자 명시 요청(`--grade=S` 등) 시에만.

### S-grade 보호 조건 (S를 S로 유지 가능한 케이스)
- 단일 파일, 단일 함수 수정
- 버그 수정(조건문 하나 추가, 상수 변경 등)
- ruff autofix
- docstring·주석 정리
- 이 외는 M으로 승격.
```

---

## Pipeline Review Gate

### 분류 결정 배경

XGif의 파이프라인은 **모두 사전 설치 하네스의 체인**이며, 본 프로젝트는 신규 "생성·결정·설계"
파이프라인을 프로비저닝하지 **않는다**. 각 하네스의 내부 5-agent 체인은 이미 말단에
**종합·리뷰 에이전트**(`review-synthesizer`, `qa-reviewer`, `perf-reviewer`)를 포함하고
있어 내재적 리뷰 게이트가 존재한다. 이 상황에서 파이프라인 리뷰 게이트 규칙
(`.claude/rules/pipeline-review-gate.md`)을 어떻게 적용할지 판단이 필요하다.

### 본 프로젝트 대상 파이프라인 분류표

| 파이프라인 | 성격 | 분류 | 리뷰어 (내재 or 전용) | 면제 사유 |
|------------|------|------|--------------------|----------|
| STEP -1 Complexity Gate | 결정론적 규칙 평가 | **exempt** | — | 결정론적 분류, 외부 정보·생성물 없음 |
| STEP 1 Explore (plan.md 작성) | 계획 생성 | **mandatory_review** | 내재: L-grade 시 `architecture-reviewer` 1회 | — |
| STEP 2 Implement | 코드 생성 | **mandatory_review** | 내재: STEP 4의 5-agent 체인이 diff 전체를 검증 | — |
| STEP 3 Test (test-automation) | 테스트 설계·생성 | **mandatory_review** | 내재: `qa-reviewer` (체인 말단) | — |
| STEP 4 Review (code-reviewer) | 리뷰 자체 | **exempt** (재귀 차단) | — | 리뷰의 리뷰 금지 (pipeline-review-gate.md §3) |
| STEP 5 Optimize | 최적화 코드 생성 | **mandatory_review** | 내재: `perf-reviewer` (체인 말단) | — |
| STEP 6 Package | 결정론적 빌드 실행 | **exempt** | — | build_optimized.py 실행 + PyInstaller 빌드는 결정론적 변환. 검증은 smoke-test(exe 부팅 확인)로 수행 |
| STEP 7 Release | 결정론적 I/O (git tag, CHANGELOG append) | **exempt** | — | 단순 I/O 및 기존 산출물 배포 |

### 에스컬레이션 래더

모든 mandatory_review 파이프라인의 BLOCK 처리는
`.claude/rules/pipeline-review-gate.md` **"에스컬레이션 래더"** 규약을 따른다 (1회=오케스트레이터
자동 승인, 2회=사용자 결정, 3회=중단). 래더 본문은 복붙하지 않으며 해당 규칙 파일을 참조한다.

### 도메인 리뷰어 신규 프로비저닝 여부

**프로비저닝하지 않는다**. 사유:

1. **내재적 리뷰 존재**: 3개 mandatory_review 파이프라인(STEP 3/5의 하네스 체인)은 이미 체인
   말단에 리뷰어 에이전트를 포함한다 — `qa-reviewer`(test-automation), `perf-reviewer`
   (performance-optimizer), `review-synthesizer`(code-reviewer). 이들은 XGif 본 프로젝트에
   **사전 설치된 하네스의 일부**로 `.claude/agents/`에 이미 존재한다.
2. **도메인 특화 방어**: 위 3개 리뷰어는 각자 도메인(테스트 품질 / 성능 회귀 / 코드 리뷰
   통합)에 특화돼 있어 "범용 Advisor 하나로 통합" 금지 원칙과 충돌하지 않는다.
3. **리뷰 전용 권한**: 이들은 실행 모드에서 SendMessage로만 수정 요청하며, 파일 쓰기는
   해당 하네스 `_workspace/` 서브디렉터리의 리포트 파일에 한정된다.
4. **STEP 1(Explore)**: L-grade에서 architecture-reviewer 1회 소환으로 plan.md 리뷰
   커버. M-grade plan은 솔로 개발자의 직접 리뷰로 충분(Advisor 결정 반영).
5. **STEP 2(Implement)**: 생성된 diff는 STEP 4(code-reviewer 하네스)가 종합 리뷰하므로 별도
   리뷰어 불필요.

### 재귀 차단 확인

- STEP 4(code-reviewer)의 결과물 `_workspace/review/05_review_summary.md`는 다시 리뷰받지
  않는다.
- 3개 내재적 리뷰어의 리포트 자체도 다음 스텝에서 재리뷰 대상이 아니다.

### 리뷰어 allowed_dirs 확인

| 리뷰어 | allowed_dirs |
|--------|--------------|
| qa-reviewer | `_workspace/test/` (자기 리포트만 쓰기) |
| perf-reviewer | `_workspace/perf/` (자기 리포트만 쓰기) |
| review-synthesizer | `_workspace/review/` (자기 리포트만 쓰기) |
| architecture-reviewer (선택적, STEP 1) | read-only (plan.md는 메인 세션이 수정) |

설치 하네스 에이전트 .md 파일은 수정하지 않으므로, 위 제약은 오케스트레이터 규칙 파일
(`workflow-orchestrator.md`)에 "쓰기 범위" 규약으로 기록한다.

---

## Failure Recovery & Artifact Versioning

각 파이프라인의 실패 복구 종료 조건과 산출물 버저닝을 명시한다.

| 파이프라인 | max_retries | 에스컬레이션 분기 | timeout | 산출물 버저닝 전략 |
|------------|------------|------------------|---------|------------------|
| STEP -1 Complexity Gate | n/a (결정론적) | n/a | n/a | 산출물 없음 (메모리만) |
| STEP 1 Explore | 2회 (메인 세션 직접) | max 도달 시 `orchestrator_ask` → 사용자에게 "plan 범위 좁히기·태스크 재정의" 요청 | 15분 (코드 스캔 포함) | `docs/tasks/{task-name}/plan.md` — 태스크명 수준에서 고유. 동일 태스크 재실행 시 **덮어쓰기**(idempotency_guarantee: 동일 task_description + 동일 diff → 동일 plan) |
| STEP 2 Implement | 3회 (ruff lint 실패 시 자동 수정 2회 + 수동 1회) | max 도달 시 사용자에게 수정된 diff 보고 후 결정 요청 | 가변 (사용자 페이스) | 소스 파일: git이 버전 관리. 별도 전략 없음. |
| STEP 3 Test | 2회 (하네스 내부 SendMessage 수정 루프 — qa-reviewer가 최대 2회 수정 요청, SKILL.md §Phase2 규약) | max 도달 시 `_workspace/test/05_review_report.md`에 누락 명시하고 진행 | 각 에이전트 10분, 전체 40분 | `_workspace/test/` — **덮어쓰기**. 동일 태스크 재실행 시 이전 리포트 소실. 필요 시 사용자가 git commit으로 보존. |
| STEP 4 Review | 2회 (review-synthesizer의 내부 재분석 요청 최대 2회, SKILL.md 규약) | max 도달 시 해결 못한 finding 리포트에 명시하고 진행 | 각 에이전트 10분, 전체 50분 (병렬 4-way) | `_workspace/review/` — 덮어쓰기. 세션 단위 소비. |
| STEP 5 Optimize | 2회 (perf-reviewer 수정 요청 최대 2회) | max 도달 시 benchmark 결과와 미해결 이슈 보고 | 각 에이전트 15분, 전체 60분 | `_workspace/perf/` — 덮어쓰기. benchmark는 보존 필요 시 별도 커밋. |
| STEP 6 Package | 1회 (PyInstaller 빌드는 비결정론 요소가 적어 재시도 대신 로그 분석) | 실패 시 사용자에게 build log 보고 + build_optimized.py 직접 디버깅 요청 | 10분 (PyInstaller 평균) | `dist/XGif_{version}.exe` — `version` suffix로 자연 버저닝. 동일 version 재빌드는 덮어쓰기. `_workspace/cli/` 리포트는 세션 소비. |
| STEP 7 Release | 0회 (수동) | n/a | n/a | git tag 고유성, CHANGELOG는 append-only |

**재시도 상한 정책**:
- 설계 상 모든 재시도 루프는 상한을 가진다(2회 기본). 상한 도달 시 **파이프라인 재실행이
  아닌 사용자 에스컬레이션**으로 넘어간다.
- 이는 `.claude/rules/pipeline-review-gate.md` "에스컬레이션 래더"(1회·2회·3회 프로토콜)와
  **개념적으로 호환**. 래더는 리뷰어 BLOCK 회수를 추적하고, 본 표는 **일반 실행 실패** 재시도
  상한을 정의한다. 두 메커니즘은 충돌하지 않으며 병행 적용된다.

**timeout 정책**:
- 에이전트 단일 소환 timeout: 15분 (하네스 무반응 방지)
- 전체 하네스 체인 timeout: 60분 (최악의 경우)
- Timeout 도달 시: 마지막 완료 에이전트까지의 산출물을 보존하고 이후 체인 중단 + 사용자 보고

---

## Agent-Skill Mapping

본 프로젝트는 **신규 에이전트를 프로비저닝하지 않는다**. 아래는 **기존 설치 하네스 에이전트의
XGif 문맥 매핑**이다.

| 에이전트 | 소속 하네스 | 모델 권장 | 쓰기 범위 | 담당 스킬 |
|---------|------------|----------|----------|-----------|
| test-strategist | test-automation | sonnet | `_workspace/test/` | test-automation (주), test-design-patterns (확장) |
| unit-tester | test-automation | sonnet | `_workspace/test/`, `tests/` | test-automation, mocking-strategy |
| integration-tester | test-automation | sonnet | `_workspace/test/`, `tests/integration/` | test-automation, mocking-strategy |
| coverage-analyst | test-automation | sonnet | `_workspace/test/` | test-automation |
| qa-reviewer | test-automation | sonnet | `_workspace/test/` (read-only plan 대상, 자기 리포트만 write) | test-automation |
| style-inspector | code-reviewer | sonnet | `_workspace/review/` | code-reviewer |
| security-analyst | code-reviewer | sonnet | `_workspace/review/` | code-reviewer, vulnerability-patterns |
| performance-analyst | code-reviewer | sonnet | `_workspace/review/` | code-reviewer, refactoring-catalog |
| architecture-reviewer | code-reviewer | opus (L-grade 설계 경계 분석) / sonnet (M) | `_workspace/review/` | code-reviewer, refactoring-catalog |
| review-synthesizer | code-reviewer | sonnet | `_workspace/review/` (합의 리포트만) | code-reviewer |
| profiler | performance-optimizer | sonnet | `_workspace/perf/` | performance-optimizer |
| bottleneck-analyst | performance-optimizer | sonnet | `_workspace/perf/` | performance-optimizer, query-optimization-patterns (N/A — XGif는 DB 없음, 스킵), refactoring-catalog |
| optimization-engineer | performance-optimizer | sonnet | `_workspace/perf/`, `core/` (신중 — 구현 주입 시 메인 세션 확인) | performance-optimizer, caching-strategy-selector |
| benchmark-manager | performance-optimizer | sonnet | `_workspace/perf/`, `tests/benchmarks/` (있다면) | performance-optimizer |
| perf-reviewer | performance-optimizer | sonnet | `_workspace/perf/` | performance-optimizer |
| release-engineer | cli-tool-builder | sonnet | `_workspace/cli/`, build 로그만 (소스 미수정) | cli-tool-builder |
| docs-writer | cli-tool-builder | sonnet | `_workspace/cli/`, `CHANGELOG.md` | cli-tool-builder |

**비활성 에이전트** (본 프로젝트에서 소환 안 함):
- `command-designer` (cli-tool-builder) — XGif는 신규 CLI 도구 개발 아님
- `core-developer` (cli-tool-builder) — 본 체인에서 코드 구현은 메인 세션 담당
- `test-engineer` (cli-tool-builder) — STEP 3(test-automation)이 우선

**모델 선택 근거**:
- 기본 sonnet (구현·분석·리뷰 균형)
- L-grade에서 `architecture-reviewer` 만 opus (설계 경계 위반 탐지의 깊이 필요)
- haiku 미사용 (반례 탐색 약화 위험, pipeline-review-gate.md §리뷰어 Guardrails)

---

## Communication Points

| 소통 포인트 | 유형 | 용도 |
|------------|------|------|
| 메인 세션 → 하네스 스킬 | 스킬 호출 (Task/SendMessage 프롬프트) | 스킬 소환 + 프리루드 주입 + `_workspace/{alias}/` 경로 바인딩 |
| test-strategist → unit-tester / integration-tester | SendMessage | 테스트 범위·모킹 전략 전달 (병렬 팬아웃) |
| unit-tester → integration-tester | SendMessage | 모킹 인터페이스 목록 공유 |
| unit/integration-tester → coverage-analyst | 파일 (`_workspace/test/0{2,3}_*.md`) | 테스트 목록 전달 |
| coverage-analyst → unit/integration-tester | SendMessage | 갭 발견 시 추가 테스트 요청 (최대 2회) |
| qa-reviewer → any test agent | SendMessage | 필수 수정 요청 (최대 2회) |
| style-inspector → security-analyst | SendMessage | 주석 내 민감 정보 플래그 전달 |
| style-inspector → performance-analyst | SendMessage | 복잡 함수 목록 전달 |
| 4개 리뷰 analyst → review-synthesizer | 파일 (`_workspace/review/0{1..4}_*.md`) | 4-way 팬인 |
| review-synthesizer → analyst | SendMessage | 추가 분석 요청 (최대 2회) |
| profiler → bottleneck-analyst | 파일 (`_workspace/perf/01_profiling_report.md`) | baseline 전달 |
| bottleneck-analyst → optimization-engineer | 파일 (`02_bottleneck_analysis.md`) | 병목 우선순위 전달 |
| optimization-engineer → benchmark-manager | 파일 (`03_optimization_plan.md`) | 최적화 코드 전달 |
| perf-reviewer → optimization-engineer | SendMessage | 회귀 우려 수정 요청 (최대 2회) |
| release-engineer ↔ docs-writer | SendMessage | CHANGELOG 항목 vs 빌드 결과 교차 확인 |
| PreCommit 훅 (Phase 7-8 설치) | Hook 출력 | M-grade 리마인더 (non-blocking) |

**핸드오프 파일(`_state.json`)**: 본 프로젝트는 **사용하지 않는다**. 각 하네스는 자기
`_workspace/{alias}/` 하위에 파일로 상태를 기록하며, 세션 간 지속성은 git commit으로 처리.

---

## Hook Specifications (Deferred to Phase 7-8)

Advisor ASK-2 결정(solo speed 존중 + M-grade Review 자동 강제 안 함)에 따라 PreCommit 훅은
**non-blocking 리마인더**로 제공한다.

### Hook #1 — `precommit-m-grade-reminder.sh` (PreCommit, non-blocking)

**탐지 기준** (OR 조건, 하나라도 충족 시 리마인더 발동):

```
trigger_conditions:
  file_count_threshold: 2               # git diff --cached 파일 수 >= 2
  new_function_defs_threshold: 3        # 추가된 라인 중 `def ` 정규식 매칭 >= 3
  new_imports_threshold: 1              # 추가된 `import ` / `from ... import` 라인 >= 1
  god_object_touched: true              # diff에 GOD_OBJECTS 파일 포함
  critical_dir_touched: true            # diff에 editor/ui/ 파일 포함
```

위 **어느 것이든** 충족 시 stdout 출력(커밋 차단 X):

```
[reminder] This looks like an M-grade change (detected: {reasons}).
           Consider running /code-reviewer before pushing.
           To skip this reminder, use `git commit --no-verify`.
```

**차단 동작**: 없음 (exit 0). 리마인더는 정보만 제공.
**정확도 목표**: 잡음 억제 우선. False positive가 잦으면 threshold를 상향 조정한다(3→5 등).

**Phase 7-8 설치 책임**: Phase 7-8(hooks-mcp-setup)이 `.claude/hooks/` 에 이 훅을 생성하고
`.claude/settings.json` 의 PreCommit 섹션에 등록. 본 Phase 4는 사양만 기록.

### Hook #2 — (선택) `postwrite-s-grade-ruff.sh` (PostToolUse, non-blocking)

**발동 조건**: S-grade 실행(메인 세션 직접 구현)에서 Edit 툴 사용 후.

**동작**: `ruff check --fix` 자동 실행 + 결과 출력. 실패해도 차단 없음.

**비용·가치**: Phase 7-8에서 구현 여부 재판단(구현하지 않을 수도 있음). 본 Phase 4에서는
"가능성"만 기록.

---

## Orchestrator Rule File Spec (Phase 6 Input)

Phase 6(skill-forge)이 `.claude/rules/workflow-orchestrator.md` 를 제작할 때 **반드시 포함**할
섹션 명세. 이 파일은 메인 세션이 모든 개발 태스크 시작 시 참조하는 always-apply 규칙이다.

### 필수 섹션 체크리스트

- [ ] `## Main Session Role` — "라우터-only" 선언, 예외(S-grade)
- [ ] `## Complexity Gate` — GOD_OBJECTS 리스트, grade 결정 규칙(S/M/L), 상향 바이어스
- [ ] `## Domain Detection` — 파일 경로 접두사 → 도메인 매핑
- [ ] `## Domain-Harness Activation Matrix` — 도메인별 활성/비활성 하네스 표
- [ ] `## Grade-Step Selection` — S/M/L 등급별 스텝 체인 표
- [ ] `## Slash Command Mapping` — 4개 슬래시 커맨드 ↔ 하네스 ↔ 워크플로우 스텝
- [ ] `## _workspace Namespace Binding` — 경로 치환 규칙 (본 산출물 ASK-1 섹션 전체)
- [ ] `## Agent Prelude Bindings` — 5개 프리루드 텍스트(release-engineer /
      integration-tester / style-inspector / architecture-reviewer / optimization-engineer)
- [ ] `## Retry Policy` — 표 4.6: max_retries / escalation / timeout
- [ ] `## Review Gate Reference` — pipeline-review-gate.md 참조 + 본 프로젝트 분류표 링크
- [ ] `## Hook Invocation` — precommit-m-grade-reminder 탐지 기준(설치는 Phase 7-8)

### 파일 규모 목표

≤ 200줄 (CLAUDE.md 한도와 정합). 초과 시 서브-섹션을 `docs/` 이동 또는 별도 규칙 파일로 분리.

### Meta-Leakage 차단

이 규칙 파일은 **출하 산출물(shipped harness)** 이다. 따라서 다음 용어를 **사용하지 않는다**:
- "Phase 1", "Phase 3", "phase-pipeline", "phase-workflow" 등의 메타 용어
- "harness-architect", "skill-forge", "agent-team" 등 플러그인 내부 이름
- "Advisor", "Dim 12", "Red-team Advisor" 등 검증 레이어 용어

허용 용어: "Complexity Gate", "workflow step", "harness" (일반 명사), "agent", "skill",
"hook", "rule".

### 본 산출물(`03-pipeline-design.md`) vs 규칙 파일 관계

본 산출물은 **내부 설계 스크래치패드** (Phase 4~5~6 간 전달용)이므로 메타 용어 사용 허용.
Phase 6이 이 내용을 규칙 파일로 옮길 때 용어를 필터링해야 한다.

---

## Rejected Alternatives

### 기각 1: 신규 도메인 레드팀 에이전트 프로비저닝

**옵션**: STEP 3/5/6 각각을 위해 `test-redteam`, `perf-redteam`, `release-redteam` 에이전트
3명을 신규 생성.

**기각 사유**: 하네스 내부 체인에 이미 `qa-reviewer` / `perf-reviewer` /
`review-synthesizer` 리뷰어가 있다. 추가 레드팀은 **리뷰의 리뷰**가 되어
`pipeline-review-gate.md §3 재귀 금지`를 위반한다. 또한 솔로 개발자의 17개 에이전트 이미
충분하며, 추가 3명은 체인 호출 당 비용 ~30% 증가 대비 가치 낮음.

### 기각 2: `_workspace/` 전역 공유 (하네스별 서브디렉터리 없음)

**옵션**: 모든 하네스가 `_workspace/` 루트를 공유하고 파일명 prefix로 구분
(`test_00_input.md`, `review_00_input.md` 등).

**기각 사유**: Advisor ASK-1 해결 결정에 따라 서브디렉터리 채택. Prefix 방식은 하네스
SKILL.md를 직접 수정해야 하고(설치 하네스는 공유 설치 리소스이므로 수정 지양),
Cross-session 충돌 잡음 크다.

### 기각 3: 메인 세션에 implementer-agent 프로비저닝 (에이전트 파이프라인화)

**옵션**: 메인 세션을 라우터가 아닌 에이전트 파이프라인 모드로 전환. `implementer-agent`,
`explorer-agent` 등 새로 추가.

**기각 사유**: XGif는 agent-pipeline 프로젝트가 아니다(Phase 1-2 확정). 솔로 개발자의 IDE
태스크 흐름은 메인 세션 직접 작업이 자연스럽다. 에이전트 파이프라인화는 Complexity Gate의 S
경로를 무력화하여 비용만 증가.

### 기각 4: Specialist Review(security/design/ux) 에이전트 상시 활성

**옵션**: L-grade에서 `security-redteam`, `design-redteam`, `ux-redteam` 에이전트를 자동
소환.

**기각 사유**: Phase 3 워크플로우 결정(Specialist Review는 L + 명시 플래그 + UI 디렉터리
변경 AND 조건)에 따라 조건부 실행. 자동 활성은 비용 낭비. 명시 플래그 경로는 그대로 유지.

### 기각 5: `/cli-tool-builder` 를 STEP 6 자동 호출

**옵션**: STEP 4 완료 시 항상 자동으로 STEP 6 패키징 실행.

**기각 사유**: Package는 릴리스 인텐트가 있을 때만 실행(워크플로우 정의). 모든 M/L 태스크를
PyInstaller 빌드하면 분당 10분씩 비용 발생. 사용자 명시 트리거 유지.

### 기각 6: PreCommit 훅을 blocking으로 설치

**옵션**: M-grade 감지 시 커밋 실패 처리하고 `/code-reviewer` 강제.

**기각 사유**: Advisor ASK-2 결정. 솔로 개발자 고속 반복 존중. Blocking은 `--no-verify`
우회를 유발하여 오히려 훅 신뢰도 저하. 리마인더만으로 충분.

---

## Context for Next Phase

### 에이전트 목록 (Phase 5 agent-team 입력)

**프로비저닝 대상: 0명 (신규 생성 없음)**. 사전 설치된 17명의 에이전트를 그대로 사용하며,
에이전트 .md 파일 수정도 하지 않는다(공유 설치 리소스 원칙).

Phase 5는 대신 다음을 수행:
1. 17명 에이전트 각각이 xgif 문맥에서 소환될 때 **컨텍스트 프리루드** 주입 메커니즘 구현
2. 이 주입은 Phase 6의 규칙 파일(`workflow-orchestrator.md`)의 "Agent Prelude Bindings"
   섹션이 실제 수행 — Phase 5는 이 규약이 Phase 6에 전달되도록 Context 보존
3. `_workspace/{alias}/` 디렉터리 레이아웃 및 쓰기 범위 규약 전달

### 스킬 목록 (Phase 6 skill-forge 입력)

**신규 제작 대상: 1개 규칙 파일**.

| 항목 | 이름 | 경로 | 책임 |
|------|------|------|------|
| 규칙 파일 | workflow-orchestrator | `.claude/rules/workflow-orchestrator.md` | Main Session D-1 routing, Complexity Gate, 도메인 감지, `_workspace/` 바인딩, 프리루드 바인딩, 재시도 정책, 리뷰 게이트 참조 |

**스킬 파일 신규 제작: 없음**. 사전 설치된 4개 스킬(test-automation / code-reviewer /
performance-optimizer / cli-tool-builder)을 그대로 사용.

### 실행 순서/패턴 (핵심 요약)

- S-grade: 메인 세션 직접, 0 에이전트
- M-grade: 메인 세션 → /test-automation (5명) → /code-reviewer (3명 감축)
- L-grade: 메인 세션 → /test-automation (5명 풀) → /code-reviewer (5명 풀)
           → /performance-optimizer (5명, 조건부)
           → /cli-tool-builder (2명, 릴리스 시)

### 소통 포인트 요약

- 메인 세션 ↔ 스킬: Task/SendMessage 프롬프트 + 프리루드 주입
- 하네스 내부: SendMessage + `_workspace/{alias}/` 파일
- 하네스 간: 격리 원칙 (다른 하네스의 `_workspace/` 서브디렉터리 접근 금지)
- 크로스 세션: git commit + git tag

### 메인 세션 역할 확정

**라우터-only** (D-1 기본값). Phase 5의 Orchestrator Pattern Decision 에 D-1 적용.

### Pipeline Review Gate Decisions 표 (Phase 5 리뷰어 프로비저닝 입력)

| 파이프라인 | 분류 | 리뷰어 에이전트 | 면제 사유 |
|-----------|------|-----------------|----------|
| STEP -1 Complexity Gate | exempt | — | 결정론적 규칙 평가, 생성물 없음 |
| STEP 1 Explore (plan) | mandatory_review | `architecture-reviewer` (내재, L만) | — (M은 사용자 직접 리뷰) |
| STEP 2 Implement | mandatory_review | `review-synthesizer` (내재, STEP 4에서 커버) | — |
| STEP 3 Test | mandatory_review | `qa-reviewer` (내재) | — |
| STEP 4 Review 자체 | exempt | — | 재귀 금지 |
| STEP 5 Optimize | mandatory_review | `perf-reviewer` (내재) | — |
| STEP 6 Package | exempt | — | 결정론적 빌드 실행 + smoke-test |
| STEP 7 Release | exempt | — | 결정론적 I/O (git tag, CHANGELOG) |

**Phase 5 조치**: 신규 레드팀 에이전트 프로비저닝 **불필요**. 기존 하네스 내재 리뷰어가
도메인 특화 리뷰를 담당. 단, Phase 6 규칙 파일에 각 리뷰어의 allowed_dirs 제약
(`_workspace/{alias}/` 쓰기 + 타 영역 read-only)을 명시한다.

### Failure Recovery & Artifact Versioning 요약

- 모든 재시도 루프 상한: 2회 기본 (Step 4.6 표 참조)
- `_workspace/{alias}/` 산출물: 덮어쓰기 전략 (세션 소비, git으로 보존 선택적)
- `docs/tasks/{task-name}/plan.md`: idempotent 덮어쓰기 (동일 diff → 동일 plan)
- `dist/XGif_{version}.exe` / `installer/XGif_Setup_{version}.exe`: version suffix 버저닝
- CHANGELOG.md: append-only

---

## Files Generated

- `D:\ProjectX\XGif_v5\docs\xgif-setup\03-pipeline-design.md` — 본 파일 (Phase 4 파이프라인
  설계 산출물)

---

## Escalations

[NOTE] 신규 에이전트 프로비저닝 없음 — XGif는 사전 설치된 17개 하네스 에이전트만으로 7-스텝
워크플로우를 완전 커버한다. 추가 프로비저닝은 비용 대비 가치 낮음(기각 1 참조). Phase 5는
"에이전트 파일 수정 없음, 프리루드 주입 규약만 Phase 6에 전달" 방향으로 진행한다.

[NOTE] 도메인 레드팀 신규 생성 안 함 — 3개 mandatory_review 파이프라인이 하네스 내재
리뷰어(qa-reviewer / review-synthesizer / perf-reviewer)를 이미 말단에 포함하며, 이들은
도메인 특화 + 파일 쓰기 제한 + 재귀 차단 요건을 충족한다. 추가 레드팀은 "리뷰의 리뷰"를
유발하여 pipeline-review-gate.md §3 위반. Advisor Dim 12 재검증 시 이 결정 근거를 확인할 수
있도록 본 섹션과 `## Pipeline Review Gate` 에 명시했다.

[NOTE] `_workspace/` 루트 경로는 `.gitignore`에 추가 필요 — Advisor ASK-1 결정. 구현은
Phase 7-8(hooks-mcp-setup) 단계에서 반영. 본 산출물은 규약만 정의.

[NOTE] architecture-reviewer 모델 업그레이드 — L-grade 설계 경계 분석 시 opus 권장.
Phase 5 프로비저닝에서 에이전트 .md의 model 필드를 수정하지 않고, 대신 오케스트레이터가
소환 시 `model: opus` 오버라이드를 명시한다(Task 도구의 model 파라미터 경로). 솔로 솔로
프로젝트이므로 opus 비용은 감당 가능.

[NOTE] M-grade STEP 4 감축 파이프라인(3-agent: style + architecture + synthesizer)은 Phase 3
결정(감축 허용)과 정합. 만일 사용자가 M-grade에서도 풀 5-agent 리뷰를 원하면 `--review=full`
인자 경로를 규칙 파일에 선택지로 기재할 수 있음 — Phase 6에서 구현 여부 판단.

[NOTE] 재시도 카운터와 리뷰 에스컬레이션 래더는 **독립 메커니즘**. 전자는 일반 실행 실패
(에이전트 오류, timeout), 후자는 리뷰어 BLOCK 반복. 동일 파이프라인 호출 내에서 양쪽이 병행
작동할 수 있다. 규칙 파일에 둘의 관계를 명시해야 함(Phase 6 책임).

[NOTE] BootStrapper 도메인은 test-automation 하네스 비활성 + cli-tool-builder 부분 활성
규약. 향후 BootStrapper BAT 자동화 요구가 생기면 cli-tool-builder 확장 또는 신규 하네스
필요. 현 시점에서는 기각 5 근거 유지.

[NOTE] optimization-engineer의 `core/` 쓰기 권한 — 하네스 기본 정책은 코드 수정 가능이나,
XGif는 신중한 운용을 위해 "제안 → 메인 세션 확인 → 메인 세션이 Edit" 패턴 권장. Phase 6
규칙 파일에 "optimization-engineer는 `_workspace/perf/` 에만 직접 쓰기, 소스 수정은 메인
세션 승인 필요" 규약 포함 필요.

---

## Next Steps

Phase 5: agent-team 소환 — 본 파이프라인 설계를 입력으로 사전 설치된 17개 에이전트의 XGif
문맥 프리루드 바인딩을 Phase 6에 전달하고, 신규 에이전트 프로비저닝 없음을 확정한다. Phase 6
skill-forge는 `.claude/rules/workflow-orchestrator.md` 규칙 파일을 제작한다(본 산출물의
"Orchestrator Rule File Spec" 섹션 준수, meta-leakage 용어 필터링 수행).
