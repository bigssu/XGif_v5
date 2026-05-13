# 아키텍처 경계 규칙 — XGif

## 모듈 의존성 방향
```
main.py → ui/ | cli/
ui/     → core/ (wx 허용)
cli/    → core/ (wx 금지)
core/   → (외부 라이브러리만, wx 조건부)
editor/ → core/ (wx 허용)
```

## 절대 금지 cross-import
| 위반 | 이유 |
|------|------|
| `cli/*.py`에서 `import wx` | headless 환경 크래시 |
| `core/*.py`에서 무조건적 `import wx` | CLI 재사용 불가 |
| `ui/*.py`에서 `cli/`로 역방향 import | 순환 의존성 |

## main.py CLI 조기 분기 패턴
```python
# wx import BEFORE 이 분기는 금지
def _is_cli_mode() -> bool:
    cli_commands = {'record', 'convert', 'config', 'doctor'}
    return len(sys.argv) >= 2 and sys.argv[1] in cli_commands

if _is_cli_mode():
    from cli.main import cli_main  # wx 없이 실행
    sys.exit(cli_main())

import wx  # GUI 모드에서만 도달
```

## 새 CLI 명령 추가 규칙
- 새 CLI 서브커맨드 추가 시 `_is_cli_mode()`의 `cli_commands` 집합에 추가한다.
- CLI 명령 구현은 반드시 `cli/` 안에 배치한다.
- 새 CLI 명령이 `core/`의 기능을 사용할 때, 해당 `core/` 모듈에 wx 의존성이 없는지 확인한다.

## 에디터 독립 실행
- `editor/`는 `python -m editor`로 독립 실행 가능하다.
- 에디터 진입점: `editor/__main__.py`

## editor/ → ui/ 공유 위젯 import 정책
`editor/` 는 `ui/` 의 **공유 위젯·테마·상수 모듈**을 import 할 수 있다. 단,
`ui/main_window.py` 같은 컴포지트 화면 모듈은 import 금지.

| 분류 | 모듈 | editor/ import 허용 여부 |
|------|------|-----------------------|
| 공유 위젯 (wx-only, 단일 책임) | `ui/dark_controls.py`, `ui/window_chrome.py` | ✅ 허용 |
| 테마/스타일 상수 | `ui/theme.py` | ✅ 허용 |
| 국제화 | `ui/i18n.py` | ✅ 허용 |
| 의존성 다이얼로그 | `ui/dependency_dialogs.py`, `ui/startup_check_dialog.py` | ✅ 허용 |
| 메인 윈도우/컴포지트 | `ui/main_window.py`, `ui/capture_control_bar.py` 등 | ❌ 금지 |

신규 공유 모듈을 추가할 때 위 표에 등재한다. 표에 없는 `ui/` 모듈을 `editor/`
에서 import 해야 한다면 먼저 표를 갱신하여 정책을 명문화하라.

## BootStrapper 격리
- `BootStrapper/`는 XGif 본체와 완전히 독립된 별도 애플리케이션이다.
- XGif 본체 코드(`main.py`, `ui/`, `core/`, `cli/`, `editor/`)에서 `BootStrapper/`를 import하지 않는다.
- BootStrapper는 Python/FFmpeg/venv 설치 후 XGif를 실행하는 래퍼이므로, 로직 공유 시
  공유 코드를 `core/`로 추출한다.
