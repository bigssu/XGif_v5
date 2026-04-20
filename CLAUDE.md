# XGif 프로젝트 규칙

## 프로젝트 개요
- **앱**: XGif — Windows용 GIF/MP4 화면 녹화 프로그램 (PyInstaller 단일 실행 파일로 배포)
- **Python**: 3.11.9 (venv: `.venv/Scripts/python.exe`)
- **UI**: wxPython 4.2 (tkinter, PyQt 사용 금지)
- **실행**: `.venv/Scripts/python.exe main.py`
- **빌드**: `.venv/Scripts/python.exe build_optimized.py`
- **테스트**: `.venv/Scripts/python.exe -m pytest tests/ -v`
- **린팅**: `.venv/Scripts/python.exe -m ruff check . --fix` (line-length 120, target py311)
- **버전**: `core/version.py` (Single Source of Truth)

## 모듈 아키텍처
- `core/` — 핵심 엔진 (wx 의존성 없음, CLI에서 재사용 가능)
- `ui/` — wxPython 메인 GUI (레코더 컨트롤, 설정 다이얼로그)
- `cli/` — CLI 인터페이스 (wx import 절대 금지)
- `editor/` — GIF/비디오 에디터 (wxPython)
- `BootStrapper/` — 독립 의존성 설치 GUI (Python 3.11, FFmpeg, venv 자동화)
- `installer/` — Inno Setup 배포 스크립트
- `scripts/` — 빌드 유틸 스크립트
- `main.py` — 진입점: CLI 서브커맨드(`record|convert|config|doctor`) 감지 → wx import 전에 분기

## 필수 코딩 패턴
- 백그라운드 스레드에서 GUI 호출 → 반드시 `wx.CallAfter()` 사용
- 콤보박스 이벤트 핸들러 내 윈도우 크기 변경 → `wx.CallAfter()`로 지연
- DPI: `SetProcessDpiAwareness(1)` (SYSTEM_AWARE만 허용, PER_MONITOR_AWARE(2) 금지)
- bare `except` 금지 → `except Exception:` 사용
- FFmpeg 서브프로세스 → 예외 시 `process.kill()` (try-finally 필수)
- wxPython 타이머 → `EVT_WINDOW_DESTROY`에서 `Stop()` 호출
- wx 메뉴 이벤트 → `menu.Bind()` 사용 (`self.Bind(wx.EVT_MENU)` 금지)
- 번역 콜백 시그니처 → `retranslateUi(self, lang=None)`
- `core/` 모듈에서 wx 필요 시 → `wx.App.Get()` 확인 후 분기
- 이미지 전송 → `multiprocessing.SharedMemory` 사용 (대용량 데이터 pickling 금지)

## 금지 패턴
- `cli/` 또는 `core/`에서 `import wx` 금지
- `self.Bind(wx.EVT_MENU, ...)` 패턴 금지 (메뉴 이벤트는 `menu.Bind()`만)
- bare `except:` 금지
- `SetProcessDpiAwareness(2)` 금지
- GUI 이벤트 핸들러에서 직접 무거운 작업 실행 금지 (반드시 별도 스레드/프로세스로 위임)

## 테마 & UI 상수
- 다크 테마: `THEME_MID` (배경 `#202020`, 텍스트 `#FFFFFF`, 강조 `#0078D4`)
- 에디터 스타일: `Colors`/`Fonts` 클래스 (`editor/ui/style_constants_wx.py`)
- 레코더 커스텀 위젯: `FlatButton`, `CustomToggleSwitch` (`ui/capture_control_bar.py`)
- 폰트: Segoe UI Variable 우선, Segoe UI 폴백

## 설정 파일
- 위치: `%APPDATA%\XGif\config.ini` (섹션: `[General]`)
- 기본값 정의: `cli/config.py`의 `DEFAULT_SETTINGS`, `ui/settings_dialog.py`의 `DEFAULT_SETTINGS`

## 성능 원칙
- **Non-Blocking UI**: wxPython GUI는 절대 블로킹 금지. 무거운 작업은 별도 프로세스/스레드에서 실행
- **공유 메모리**: 프로세스 간 이미지 전달은 `multiprocessing.SharedMemory` 사용
- **GPU 폴백**: GPU 없거나 오류 시 CPU로 자동 폴백, 사용자에게 명확한 피드백 제공

## 협업 규약
- 작업 중 결정이 모호하거나 합리적인 선택지가 둘 이상이면, 가정하지 말고
  `AskUserQuestion` 도구로 먼저 사용자에게 확인한다. 코드나 명시적 답변에서 확인된
  사실에만 근거하여 진행한다.
- 커밋 메시지: 한국어 허용, 형식 `{타입}: {설명}` (예: `fix: FFmpeg 경로 오류 수정`)
- TODO 주석 형식: `# TODO: {이유}` (빈 TODO 금지)

## 린팅 & 포매팅
- 도구: `ruff` (pyproject.toml 설정 따름)
- line-length: 120, target: Python 3.11
- `E402` (모듈 import 위치) 경고 무시 — CLI 조기 분기에 필요한 패턴

## 설치된 에이전트 하네스 (from harness-100)

네 개의 도메인 하네스가 설치되어 있다. 각 하네스는 오케스트레이터 스킬 1개 + 전문 에이전트 5명 + 확장 스킬 2개로 구성된다.

| 하네스 | 트리거 스킬 | 전문 에이전트 | XGif 적용 포인트 |
|--------|-------------|--------------|-----------------|
| **code-reviewer** | `/code-reviewer` | style-inspector, security-analyst, performance-analyst, architecture-reviewer, review-synthesizer | ban-list(bare except, `self.Bind(wx.EVT_MENU)`, DPI 2) 검출, `core/` wx import 금지 검증 |
| **performance-optimizer** | `/performance-optimizer` | profiler, bottleneck-analyst, optimization-engineer, perf-reviewer, benchmark-manager | 화면 캡처 파이프라인, `multiprocessing.SharedMemory`, GPU/CPU 폴백 경로 분석 |
| **test-automation** | `/test-automation` | test-strategist, unit-tester, integration-tester, coverage-analyst, qa-reviewer | `tests/` 하위 pytest 확장, wx 없이 `core/` 단위 테스트 |
| **cli-tool-builder** | `/cli-tool-builder` | command-designer, core-developer, test-engineer, release-engineer, docs-writer | `record/convert/config/doctor` 서브커맨드 유지·확장 |

### 사용 시 XGif 고유 컨텍스트

하네스 에이전트는 범용 도메인 지식을 가지므로, 소환 시 다음 XGif-특수 사실을 함께 전달하여야 한다:

- **UI 프레임워크**: wxPython 4.2 (tkinter/PyQt 금지) — GUI 관련 제안은 반드시 wx 기준
- **실행 환경**: Windows 전용, `.venv/Scripts/python.exe`로 실행 (POSIX 가정 금지)
- **아키텍처 경계**: `cli/`와 `core/`는 wx import 금지, `BootStrapper/`는 독립 프로세스
- **성능 가정**: 이미지 전송은 `multiprocessing.SharedMemory`, pickling 금지
- **금지 패턴 목록**: 위 "금지 패턴" 섹션 참조 — 코드 리뷰·리팩토링 시 반드시 점검
- **빌드 결과**: PyInstaller 단일 exe — 동적 import·외부 파일 경로 주의

@import docs/xgif-setup/01-discovery-answers.md
