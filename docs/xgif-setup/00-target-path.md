# Phase 0 — Target Path & Project Context

> Maintenance note (2026-04-22): 이 문서는 Audit 시점 스냅샷을 보존한다. 최신 의존성 floor,
> 테스트 상태, repo-wide `ruff` baseline은 `README.md`, `CHANGELOG.md`, `docs/TODO.md`
> 를 우선 기준으로 본다.

## 요청 정보 (최신: 2026-04-21 Audit 재실행)

| 항목 | 값 |
|------|-----|
| 요청명 | `xgif-setup` |
| 대상 경로 | `D:\ProjectX\XGif_v5` |
| 프로젝트명 | XGif |
| 프로젝트 유형 | Windows 데스크톱 앱 (Python/wxPython) |
| 팀 규모 | 솔로 (1인) |
| 성능 수준 | 고성능형 (Opus 중심) |
| 트랙 | **Audit & Improve** (기존 하네스 진단/개선) |
| 이전 트랙 | 표준 경로 (2026-04-20 최초 구축, 00~08 산출물 완료) |
| 예상 소요 | Audit 단일 Phase: 10–20분 (발견 사항 많으면 +) |

## 프로젝트 상태 스냅샷 (2026-04-21 Audit 시점)

- Git 브랜치: `main` (clean working tree)
- 최신 커밋: `ba2f4a1 docs: GOD_OBJECTS 목록 갱신 + 크로스 리뷰 완결 기록 (Action Plan #12)`
- 직전 리팩토링 커밋 시퀀스 (P1~P3 Wave): `f8baa1c → 35e3ff1 → 75f55a9 → 85928aa → 2284ec7 → d29aabf → 2efe3d5`
- 주요 아키텍처 변경점:
  - `core/screen_recorder.py` 680 LOC 파사드로 축소 (P1 refactor, `d29aabf`)
  - `core/capture_worker.py` CaptureThread 분리 (~450 LOC)
  - `CaptureBackend` ABC warm-up 흡수 + `supports_managed_color` property 도입
- 기존 하네스 자산:
  - `CLAUDE.md` (harness-100 4개 도메인 하네스 기술)
  - `.claude/rules/*.md` 7개 — architecture-boundaries / ffmpeg-subprocess / harness-invocation / testing-standards / windows-encoding / workflow-orchestrator / wx-patterns
  - `CLAUDE.local.md` — 로컬 개인 설정 템플릿
- 잠재 drift 지점: `harness-invocation.md`·`workflow-orchestrator.md`의 GOD_OBJECTS/CRITICAL_FILES 목록 vs 실제 LOC/책임 분포, ruff/pytest 실행 경로 (.venv/Scripts/python.exe) vs 실제 환경.

## Audit 트랙 라우팅 결정

- Phase 1-2 단일 호출로 `harness-audit` 플레이북 실행 (전체 Phase 9까지 돌리지 않음).
- 진단 범위: CLAUDE.md 정합성 · .claude/rules/ 일관성 · 이전 docs/xgif-setup/ 산출물과 현재 코드 간 drift · harness-100 하네스 호출 체인 건강성.
- Audit 결과에 따라 수정 범위를 사용자에게 재확인 (Escalation → AskUserQuestion 통합).
- 파일 생성 규칙: 신규 발견 사항은 `docs/xgif-setup/09-audit-findings.md`에 기록. 기존 산출물은 보존하고 수정이 필요한 경우 별도 diff 섹션으로 제시.

## 다음 Phase

Phase 1-2 (`phase-setup`, Opus) — `harness-audit` 플레이북 사용, 기존 하네스 진단 + 개선 제안.
