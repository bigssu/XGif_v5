# Phase 0 — Target Path & Project Context

## 요청 정보

| 항목 | 값 |
|------|-----|
| 요청명 | `xgif-setup` |
| 대상 경로 | `D:\ProjectX\XGif_v5` |
| 프로젝트명 | XGif |
| 프로젝트 유형 | Windows 데스크톱 앱 (Python/wxPython) |
| 팀 규모 | 솔로 (1인) |
| 성능 수준 | 고성능형 (Opus 중심) |
| 트랙 | 표준 경로 (Fast Track 아님, 에이전트 파이프라인 아님) |
| 예상 소요 | 20–45분 (+ Advisor 재검토 시 Phase당 +5–8분) |

## 프로젝트 상태 스냅샷 (Phase 0 시점)

- Git 브랜치: `main`
- 최신 커밋: `8290bfa v2.0.0: Bootstrapper 17건 버그 수정 + 아키텍처 리팩토링`
- 로컬 히스토리는 방금 `git reset --hard origin/main`으로 v2.0.0에 맞춰 교체됨
- 백업 브랜치: `backup-v0.56-before-v2-reset` (3d010be, 필요 시 복구 가능)
- 최상위 디렉터리: `BootStrapper/`, `cli/`, `core/`, `editor/`, `installer/`, `main.py`, `resources/`, `scripts/`, `tests/`, `ui/`
- 추가 참고 자료: `XGif_Architecture_Review.txt` (73KB — 아키텍처 리뷰 문서), `CLAUDE.md`(기존), `CHANGELOG.md`, `pyproject.toml`, `requirements*.txt`

## 트랙 라우팅 결정

- 에이전트 파이프라인 프로젝트가 아니므로 Phase 3·4의 운영 가드(Session Recovery / Failure Recovery) 필수 섹션은 **조건부** 적용 (해당 없으면 Advisor Dim 13 스킵).
- 도메인 리서치(Phase 2.5)는 기본적으로 스킵 가능 — Phase 1-2 Escalation으로 "핵심 도메인" 확정 필요 시에만 수행.
- Fast-Forward(Phase 3-5 통합) 미적용 (솔로 프로젝트이지만 아키텍처가 이미 복잡 — core/cli/ui/editor/BootStrapper 분리).

## 다음 Phase

Phase 1-2 (`phase-setup`) — 프로젝트 스캔 + 도메인 인터뷰 + 기본 하네스 생성.
