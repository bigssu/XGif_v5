---
phase: 2
completed: 2026-04-20T22:45:00Z
status: done
advisor_status: pending
---

# Phase 1-2 — Discovery & Base Harness

## Summary

XGif는 Python 3.11.9 / wxPython 4.2 기반 Windows 전용 GIF/MP4 화면 녹화 앱이다.
v2.0.0 리셋으로 `BootStrapper/`, `installer/`, `scripts/` 3개 최상위 디렉터리가 추가됐다.
기존 CLAUDE.md는 Feb 2026 작성으로 v2.0.0 신규 디렉터리(`BootStrapper/`, `installer/`)를
포함하지 않았다 — 업데이트 완료. 소스 파일 137개(BootStrapper 제외), 최대 디렉터리 깊이 4레벨로
풀 트랙 규모 신호가 있으나 에이전트 프로젝트가 아니고 CI 없음, 단일 서비스 구조이다.
`pytest` + `ruff` 설정이 `pyproject.toml`에 존재한다.
`.gitignore`의 `.claude/` 전체 무시 패턴을 `.claude/settings.local.json`만 무시하도록 수정했다
(settings.json과 rules/*.md는 공유 가능).

핵심 패턴 5종(wx.CallAfter, DPI, 메뉴 이벤트, FFmpeg kill, 타이머 Stop)을
`.claude/rules/`에 machine-enforceable 규칙으로 분리했다.

## Scan Results

```
[Target Project Scan Results]
- Path: D:\ProjectX\XGif_v5
- Key files: pyproject.toml, requirements.txt, requirements_cli.txt, requirements_minimal.txt,
             main.py, build_optimized.py, XGif.spec
- Language: Python (primary), BAT (BootStrapper 배포)
- Framework: wxPython 4.2 (GUI), pytest (test), ruff (lint)
- Build tool: build_optimized.py (PyInstaller wrapper), Inno Setup (installer/xgif_setup.iss)
- Test setup: pytest (pyproject.toml 설정), 7개 테스트 파일
- Linter: ruff (target py311, line-length 120)
- Git: .git 존재, branch=main, 최신 커밋=8290bfa v2.0.0
- .gitignore: 존재 (109줄, 수정됨)
- Existing Claude/Cursor: CLAUDE.md 존재 (Feb 2026), .claude/ 없었음
- 소스 파일 수: 137개 Python 파일 (BootStrapper, .venv 제외)
- 최대 디렉터리 깊이: 4레벨
- 환경 파일(.env*): 없음
- CI 워크플로우 수: 0개 (.github/ 없음)
- docker-compose: 없음
- 루트 외 추가 requirements.txt: BootStrapper/requirements.txt, BootStrapper/requirements_min.txt
  (BootStrapper 독립 앱이므로 XGif 본체와 별개)
- config.ini.example: 존재 (설정 파일 예시)
```

**모듈별 규모 (Architecture Review 기준)**:
- `core/`: 18파일, 6,484 LOC (캡처 엔진)
- `cli/`: 9파일, 1,413 LOC
- `ui/`: 10파일, 15,273 LOC
- `editor/`: 68파일, 15,563 LOC
- `BootStrapper/`: 11파일 (독립 앱)
- `tests/`: 7파일
- 전체 소스: 약 39,000+ LOC

## Pre-collected Answers

| 항목 | 값 |
|------|-----|
| A1. 프로젝트명 + 설명 | XGif — Windows용 GIF/MP4 화면 녹화 프로그램 |
| A2. 프로젝트 유형 | Windows 데스크톱 앱 (Python/wxPython) |
| A3. 팀 규모 | 솔로 (1인) |
| A4. Fast Track | 아님 (표준 경로) |
| A5. 성능 수준 | 고성능형 |

## Context for Next Phase

### 프로젝트 유형
Windows 데스크톱 앱 (Python/wxPython GUI + CLI 겸용, PyInstaller 배포)

### 기술 스택
- 언어: Python 3.11.9
- UI 프레임워크: wxPython 4.2
- 화면 캡처: DXCam (DXGI), FastGDI, GDI (추상화 레이어)
- 인코딩: FFmpeg 서브프로세스, imageio
- GPU: pynvml (NVIDIA/AMD 모니터링), CuPy (선택, CUDA 가속)
- 오디오: sounddevice + soundfile
- 이미지: Pillow, numpy
- 빌드: PyInstaller + build_optimized.py (982 LOC), Inno Setup
- 테스트: pytest (7개 파일, pyproject.toml 설정)
- 린터: ruff (target py311, line-length 120, pyproject.toml 설정)

### 솔로/팀
솔로 (1인)

### 에이전트 프로젝트 여부
아니오. Fast-Forward 불필요.

### 디렉터리 구조 요약
```
XGif_v5/
├── core/       — 캡처 엔진 (wx 무관, 18파일)
├── ui/         — wxPython GUI (10파일)
├── cli/        — CLI 인터페이스 (9파일, wx 금지)
├── editor/     — GIF 에디터 wxPython (68파일)
├── BootStrapper/ — 독립 설치 앱 (11파일)
├── installer/  — Inno Setup 배포
├── scripts/    — 빌드 유틸
├── tests/      — pytest (7파일)
├── resources/  — 앱 리소스
├── main.py     — 진입점
├── build_optimized.py — PyInstaller 빌드
└── pyproject.toml / requirements*.txt
```
- **소스 파일 수**: 137개 (BootStrapper, .venv 제외)
- **최대 디렉터리 깊이**: 4레벨

### 기존 설정 존재 여부
- 환경 파일(.env*): 없음
- CI 워크플로우: 0개 (.github/ 없음)
- docker-compose: 없음 (단일 서비스)
- BootStrapper/ 내 별도 requirements.txt 2개 (독립 앱, 본체와 무관)
- 기존 CLAUDE.md: 존재 (Feb 2026, v2.0.0 업데이트로 보완됨)
- 기존 .claude/: 없었음 (이번에 신규 생성)

### 도메인 후보
핵심 도메인은 **화면 녹화/인코딩 파이프라인**이다:
1. `screen-recording` — DXCam/GDI 캡처 → 프레임 버퍼 관리 → FFmpeg 인코딩
2. `gif-editor` — 프레임 편집, 이펙트, 내보내기 (editor/ 서브시스템)
3. `bootstrapper-installer` — Python/FFmpeg 자동 설치 (BootStrapper/)

Phase 2.5 도메인 리서치는 "화면 녹화/인코딩" 도메인으로 수행하면 유용하나,
기존 Architecture Review 문서(XGif_Architecture_Review.txt, 73KB)가 이미 상세 도메인 지식을 담고 있어
Phase 2.5 스킵 후 Phase 3로 직행도 합리적이다.

### CLAUDE.md v2.0.0 드리프트 사항
기존 CLAUDE.md(Feb 2026)에서 v2.0.0 신규 요소로 누락됐던 항목:
- `BootStrapper/` 모듈 설명
- `installer/` (Inno Setup)
- `scripts/` 디렉터리
- `ruff` 린팅 명령 및 설정
- `BootStrapper/` 격리 원칙 (XGif 본체와의 분리)
→ 위 항목 모두 CLAUDE.md에 추가 완료.

### 기각된 대안 (Rejected Alternatives)
- `.claude/` 전체를 gitignore에 유지: 기각 — settings.json과 rules/*.md는 팀/개인 재현성을 위해 공유해야 함
- rules를 CLAUDE.md 인라인에 포함: 기각 — CLAUDE.md 200줄 한도 초과 우려, rules 파일이 경로별 적용 등 더 유연함
- pyproject.toml의 ruff 설정을 rules에 복제: 기각 — pyproject.toml이 SSoT, 중복 유지 비용 발생

## Files Generated

- `D:\ProjectX\XGif_v5\CLAUDE.md` — 기존 파일 업데이트: v2.0.0 신규 모듈(BootStrapper/installer/scripts) 추가, ruff 명령, 협업 규약, @import 링크
- `D:\ProjectX\XGif_v5\.claude\settings.json` — 프로젝트 권한 설정 (pytest/ruff/git 자동 허용, 위험 명령 deny)
- `D:\ProjectX\XGif_v5\.claude\rules\wx-patterns.md` — wxPython 필수 패턴 (스레드, DPI, 메뉴, 타이머)
- `D:\ProjectX\XGif_v5\.claude\rules\architecture-boundaries.md` — 모듈 의존성 경계 규칙
- `D:\ProjectX\XGif_v5\.claude\rules\ffmpeg-subprocess.md` — FFmpeg 서브프로세스 try-finally 패턴
- `D:\ProjectX\XGif_v5\.claude\rules\windows-encoding.md` — Windows UTF-8 인코딩 규칙
- `D:\ProjectX\XGif_v5\.claude\rules\testing-standards.md` — pytest 테스트 위치/명령/원칙
- `D:\ProjectX\XGif_v5\CLAUDE.local.md` — 개인 로컬 설정 템플릿 (gitignore됨)
- `D:\ProjectX\XGif_v5\.claude\settings.local.json` — 개인 권한 추가 템플릿 (gitignore됨)
- `D:\ProjectX\XGif_v5\.gitignore` — `.claude/` 전체 무시에서 `settings.local.json`만 무시로 수정 + `CLAUDE.local.md` 추가

## Escalations

[ASK] Q5. 핵심 개발 원칙 확인 — 스캔 기반 추정: "성능 우선 + Non-Blocking UI + UX 피드백". 추가로 채택 중인 원칙이 있다면? 예: TDD 적용 여부, 가독성 vs 성능 트레이드오프 기준.

[ASK] Q6. 커밋 메시지 규칙 — 현재 .gitmessage/.commitlintrc 없음. CLAUDE.md에 `{타입}: {설명}` (한국어 허용) 형식을 기본으로 기록했는데, 수정이 필요한가? Conventional Commits 영어 강제 여부?

[ASK] Q10. 'Ask-first when uncertain' 지침 — CLAUDE.md에 이미 반영했다 (협업 규약 섹션). 내용이 적절한지 검토 요청: "작업 중 결정이 모호하거나 선택지가 둘 이상이면 AskUserQuestion 도구로 먼저 사용자에게 확인한다."

[ASK] Phase 2.5 도메인 리서치 수행 여부 — 기존 `XGif_Architecture_Review.txt` (73KB)가 상세 도메인 지식을 보유 중. Phase 2.5를 스킵하고 Phase 3로 직행해도 되는가, 아니면 "화면 녹화/인코딩" 도메인으로 Phase 2.5를 수행할 것인가?

[ASK] 핵심 도메인 식별 — 후보 3가지: (1) screen-recording (캡처→인코딩 파이프라인), (2) gif-editor (에디터 서브시스템), (3) bootstrapper-installer (설치 자동화). Phase 3 워크플로우 설계 시 어느 도메인을 중심으로 설계할 것인가?

[NOTE] `.gitignore` 수정 사항 — 기존 `.claude/` 전체 무시 패턴을 `.claude/settings.local.json`만 무시로 변경했다. 이로 인해 `.claude/settings.json`과 `.claude/rules/*.md`가 git 추적 대상이 된다. 의도한 동작인지 확인 권장.

[NOTE] Strict Coding 6-Step 신호 — 감지: 소스 파일 137개(>100), LOC ~39,000(>5,000), pytest 설정(2/7 신호). ASK 승격 임계값(2개 이상)에 해당하나, 솔로 데스크톱 앱으로 팀 협업 필요성이 낮고 기존 코딩 표준이 CLAUDE.md에 잘 정의되어 있어 [NOTE]로 기록. Phase 3에서 사용자가 원하면 Strict Coding 6-Step 채택 가능.

[NOTE] code-navigation 규칙 채택 고려 — `XGif_Architecture_Review.txt` (73KB)가 사실상 코드맵 역할을 하나, `.claude/rules/code-navigation.md` 공식 채택 시 research/implement 작업 시 이 파일을 체계적으로 활용할 수 있음. Phase 3에서 사용자 판단에 따라 채택 가능.

[NOTE] BootStrapper/ — v2.0.0에서 신규 추가된 478MB 규모의 독립 앱(Python 3.11 embedded + FFmpeg + venv 설치). `.claude/rules/architecture-boundaries.md`에 격리 원칙을 기록했다. BootStrapper의 `XGif_Setup.bat`이 주 배포 방법임.

## Next Steps

Phase 1-2 완료. 다음 Phase 진행 방향:

**풀 트랙 권장** (경량 트랙 8개 조건 중 코드베이스 규모 조건 불충족: 소스 파일 137개 > 100개 기준):
- 소스 파일 137개, 약 39,000 LOC — 경량 트랙 상한(100개) 초과
- 에이전트 프로젝트 아님, CI 없음, 단일 서비스 → 나머지 7개 조건은 충족

**권장 순서**:
1. Escalations 처리 (Q5, Q6, Q10, Phase 2.5 여부, 도메인 선택)
2. Phase 2.5 도메인 리서치 (선택, 사용자 결정에 따라)
3. Phase 3: 워크플로우 설계 (`phase-workflow`)

---

## Escalation Resolutions (사용자 결정, 2026-04-20)

| # | 질문 | 결정 |
|---|------|------|
| Q5 | 핵심 개발 원칙 | CLAUDE.md의 3대 원칙(성능 우선 / Non-Blocking UI / UX 피드백) 유지. TDD 미강제 — 솔로 데스크톱 앱. |
| Q6 | 커밋 메시지 규칙 | 기존 CLAUDE.md 기록 유지 — 한국어 허용 `{타입}: {설명}` 형식. Conventional Commits 영어 강제 안 함. |
| Q10 | Ask-first 지침 | CLAUDE.md 협업 규약 섹션 내용 그대로 확정. |
| Phase 2.5 | 도메인 리서치 수행 여부 | **SKIP** — `XGif_Architecture_Review.txt` (73KB)가 이미 상세 도메인 지식 보유. Phase 3 직행. |
| Core domain | 핵심 도메인 | **screen-recording** (캡처→프레임 버퍼→FFmpeg 인코딩 파이프라인)을 1차 도메인으로 확정. gif-editor / bootstrapper-installer는 **보조 도메인** (Phase 3 워크플로우에서 별도 엔트리포인트로 고려). |

### 추가 확정 사항

- **Strict Coding 6-Step**: 채택하지 않음. 솔로 개발자 + 기존 CLAUDE.md 코딩 표준으로 충분.
- **code-navigation 규칙**: Phase 3에서 `XGif_Architecture_Review.txt`를 코드맵 참조 자원으로 다룰지 워크플로우 설계 시 결정.
- **harness-100 사전 설치**: 4개 도메인 하네스 (code-reviewer / performance-optimizer / test-automation / cli-tool-builder)가 이미 `.claude/agents/` + `.claude/skills/`에 설치되어 있음 — Phase 3 워크플로우는 이 자원을 **재사용** 대상으로 포함하고 신규 하네스 생성은 최소화해야 한다.
- **Git 상태**: 방금 `git reset --hard origin/main`으로 v2.0.0(`8290bfa`)에 정렬됨. 백업 브랜치 `backup-v0.56-before-v2-reset` 보존.
