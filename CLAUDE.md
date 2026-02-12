# XGif 프로젝트 규칙

## 프로젝트 개요
- **앱**: XGif — Windows용 GIF/MP4 화면 녹화 프로그램
- **Python**: 3.11.9 (venv: `.venv/Scripts/python.exe`)
- **UI**: wxPython 4.2 (tkinter, PyQt 사용 금지)
- **실행**: `.venv/Scripts/python.exe main.py`
- **빌드**: `.venv/Scripts/python.exe build_optimized.py`
- **테스트**: `.venv/Scripts/python.exe -m pytest tests/ -v`

## 아키텍처
- `core/` — 핵심 엔진 (wx 의존성 없음, CLI에서 재사용)
- `ui/` — wxPython GUI
- `cli/` — CLI 인터페이스 (wx import 금지)
- `editor/` — GIF 에디터 (wxPython)
- `main.py` — 진입점 (CLI 서브커맨드 감지 → wx import 전에 분기)

## 필수 패턴
- 백그라운드 스레드에서 GUI 호출 → 반드시 `wx.CallAfter()` 사용
- 콤보박스 이벤트 핸들러 내에서 윈도우 크기 변경 → `wx.CallAfter()`로 지연
- DPI: `SetProcessDpiAwareness(1)` (SYSTEM_AWARE만 사용, PER_MONITOR_AWARE(2) 금지)
- bare except 금지 → `except Exception:` 사용
- FFmpeg 서브프로세스 → 예외 시 `process.kill()` (try-finally)
- wxPython 타이머 → `EVT_WINDOW_DESTROY`에서 `Stop()`
- wx 메뉴 이벤트 → `menu.Bind()` 사용 (`self.Bind(wx.EVT_MENU)` 금지)
- 번역 콜백 시그니처 → `retranslateUi(self, lang=None)`
- `core/` 모듈에서 wx 사용 시 → `wx.App.Get()` 확인 후 분기

## 테마
- 다크 테마: `THEME_MID` (배경 #202020, 텍스트 #FFFFFF, 강조 #0078D4)
- 에디터: `Colors`/`Fonts` 클래스 (`editor/ui/style_constants_wx.py`)
- 레코더: `FlatButton`, `CustomToggleSwitch` (`ui/capture_control_bar.py`)
- 폰트: Segoe UI Variable 우선, Segoe UI 폴백

## 설정
- 파일: `%APPDATA%\XGif\config.ini` (섹션: `[General]`)
- 기본값: `cli/config.py`의 `DEFAULT_SETTINGS`, `ui/settings_dialog.py`의 `DEFAULT_SETTINGS`
- 버전: `core/version.py` (Single Source of Truth)

## Python 코딩 표준

고성능 GUI (wxPython), 멀티프로세싱, GPU 최적화 전문 Windows 개발 기준.

### 핵심 원칙
- **성능 우선**: 이미지 전송에 `multiprocessing.SharedMemory` 사용. 대용량 데이터 pickling 금지.
- **Non-Blocking UI**: wxPython GUI는 절대 멈추면 안 됨. 모든 무거운 작업은 별도 프로세스/스레드에서 실행.
- **UX**: 모든 동작에 시각적 피드백 제공. 에러를 우아하게 처리 (예: GPU 없으면 CPU 폴백).
