# Changelog

## [Unreleased]

### 변경 예정
- 다음 릴리스 항목은 여기에 누적합니다.

## [2.1.5] - 2026-05-18

### 변경
- 앱/에디터 버전과 제품 메타데이터를 `2.1.5` / `2026-05-18` 기준으로 갱신.
- README의 테스트 통과 수를 최신 상태로 갱신.

### 수정
- GIF 에디터 프레임 시간 설정에서 `.1` 같은 선행 0 없는 소수 입력도 인라인 필드에서 정상 커밋되도록 회귀 테스트를 추가.
- 인라인 숫자/텍스트 편집 종료 중 wx 이벤트 핸들러를 `Unbind` 하지 않도록 수정해, 이벤트 처리 중 dynamic event table 변경으로 발생하던 PaintEvent/SystemError 크래시를 차단.
- 닫힌 인라인 에디터에서 늦게 도착한 Enter/Focus/Key 이벤트는 현재 활성 에디터와 일치할 때만 처리하도록 보호.

## [2.1.4] - 2026-05-18

### 변경
- 앱/에디터 버전과 제품 메타데이터를 `2.1.4` / `2026-05-18` 기준으로 갱신.
- README의 테스트 통과 수를 최신 상태로 갱신.

### 수정
- GIF 에디터의 프레임 시간 설정 다이얼로그에서 인라인 `SpinCtrlDouble` 편집 중 적용/Enter/포커스 이동 시 wx 네이티브 객체를 이벤트 안에서 즉시 파괴하지 않도록 수정.
- 프레임 시간 설정 값 읽기 전에 인라인 편집 값을 명시적으로 커밋하고 초→ms 변환을 반올림으로 처리.

## [2.1.3] - 2026-05-18

### 변경
- 앱/에디터 버전과 제품 메타데이터를 `2.1.3` / `2026-05-18` 기준으로 갱신.
- README의 테스트 통과 수와 도움말의 직접 입력 UX, 저장 시 프리뷰 정지 동작을 최신 상태로 갱신.

### 수정
- owner-drawn 버튼이 일시적인 `EVT_LEAVE_WINDOW` 때문에 hover가 풀려도 실제 커서가 버튼 위에 있으면 클릭 이벤트가 유실되지 않도록 전역 버튼 판정을 보정.
- `wx.CB_DROPDOWN` 형태의 커스텀 드롭다운이 별도 입력 팝업을 열지 않고 필드 안 `TextCtrl`에서 직접 편집되도록 수정.
- GIF 에디터 저장/다른 이름 저장 진입 시 프리뷰가 재생 중이면 저장 다이얼로그 또는 저장 작업 전에 즉시 일시정지하도록 수정.
- 배포 빌드에서 NumPy 내부 테스트 확장(`_multiarray_tests`)이 포함되지 않도록 필터링.

## [2.1.2] - 2026-05-18

### 변경
- 앱/에디터 버전과 제품 메타데이터를 `2.1.2` / `2026-05-18` 기준으로 갱신.
- README의 테스트 통과 수와 설치본 GPU 가속 안내를 최신 상태로 갱신.

### 수정
- 설치본에서 NVIDIA GPU는 감지되지만 CuPy가 없는 경우 메인 GPU 감지/버튼이 `CuPy: X` 정보창에 머물지 않고 설치 가이드를 열도록 연결.
- 설치본의 CuPy 직접 설치가 시스템 Python site-packages가 아니라 XGif가 실제로 로드하는 `%LOCALAPPDATA%\XGif\env` 외부 환경을 생성/사용하도록 수정.

## [2.1.1] - 2026-05-18

### Deprecated (예정)
- `editor/ui/icon_utils_wx.py` 의 레거시 `_draw_*` 메서드(약 700 LOC) — 2.2.0 에서 Registry 패턴 마이그레이션과 함께 일괄 삭제 예정.

### 변경
- 앱/에디터 버전과 제품 메타데이터를 `2.1.1` / `2026-05-18` 기준으로 갱신.
- README의 검증 기준, 테스트 통과 수, 사내 배포 기준을 최신 상태로 갱신.
- 사내 배포에서는 코드 서명 없이 PyInstaller/선택적 Inno Setup 산출물을 사용하도록 문서화.

### 보안 / 안전성
- 도움말 다이얼로그의 `mailto` 주제 문자열을 `urllib.parse.quote` 로 인코딩하여 향후 사용자 입력 확장 시 URL 인젝션 위험을 사전 차단.
- `scripts/sign_exe.ps1` 문서 예시에서 유사-실제 PFX 비밀번호를 `<your-pfx-password>` placeholder 로 치환하고 환경변수 `XGIF_SIGN_PASSWORD` 사용을 권장 사용법으로 격상.
- `scripts/sign_exe.ps1` 와 `scripts/create_selfsign_cert.ps1` 의 `-Password` 파라미터를 `[System.Security.SecureString]` 으로 강제. 평문 `[string]` 입력 경로 제거.
- 양 스크립트가 `XGIF_SIGN_PASSWORD` 와 `XGIF_PFX_PASSWORD` 환경변수 alias 를 모두 인식, 받은 평문은 즉시 SecureString 으로 승격하고 원본 env 변수를 비움.
- signtool 호출 직전에만 BSTR 추출 + 호출 직후 `ZeroFreeBSTR` 로 메모리 zero out, 평문 잔류 위험 최소화.
- BootStrapper `download_file()` 에 `expected_sha256` 옵셔널 인자 도입. 다운로드 직후 `.part` 단계에서 SHA-256 검증, 불일치 시 자동 재시도.
- `BootStrapper/XGif_Setup.bat` 가 VC++ Redistributable 다운로드 후 Microsoft 코드 서명 확인을 사용자에게 안내.

### 수정
- `pyproject.toml`, Windows file version resource, 테스트의 릴리스 메타데이터를 `core/version.py` 의 SSoT(`2.1.1`) 에 맞춰 동기화.
- 커스텀 드롭다운 팝업이 실제 항목 높이만큼만 열리도록 보정해 하단 빈 공백을 제거.
- 숫자 입력 컨트롤이 별도 입력 팝업을 열지 않고 클릭한 필드 안에서 직접 편집되도록 개선.
- 인라인 숫자 편집 중 child `EVT_TEXT` 가 부모 spin 핸들러로 전파되어 첫 입력에 편집기가 닫히는 회귀를 차단.
- 드롭다운 row-height fallback이 native/best-size 경로 모두에서 텍스트 최소 높이보다 작아지지 않도록 보정.
- recorder/editor 전환 또는 종료 경로에서 캡처 영역 `CaptureOverlay`만 화면에 남는 orphan window 문제를 전역 종료 정리와 부모 lifecycle guard로 차단.

## [2.1.0] - 2026-05-13

### 변경
- 에디터 도움말을 앱 요약, 편집 기능, 단축키, 제품 정보 탭으로 재구성
- 에디터 정보 창을 커스텀 다크 다이얼로그로 교체하여 펼침 영역 텍스트 겹침 방지
- 앱/에디터 버전과 개발자/수정일 메타데이터를 `core/version.py` 기준으로 갱신
- 에디터 UI 아이콘, 카드 깊이, 메뉴/라인 톤을 현대적인 다크 스타일로 재정비
- 의존성 최소 버전을 현재 설치 가능한 조합으로 갱신 (`wxPython 4.2.5`, `dxcam 0.3.0`, `PyInstaller 6.20.0` 등)
- CUDA 13.x GPU 가속 의존성을 기본 설치에서 분리하고 `requirements-gpu.txt`로 선택 설치하도록 정리
- 프로젝트 문서를 현재 저장소 상태 기준으로 재정렬

### 수정
- 메인 녹화 창의 실시간 프리뷰 UI와 BGR→RGB 렌더링 경로 복구
- `xgif doctor --install-cupy`가 CUDA 13.x 검증 패키지 조합을 설치하도록 갱신
- `ruff check .` 전체 실패 항목 정리 및 프리뷰/CuPy 설치 회귀 테스트 추가
- 최신 `dxcam` 0.3.x가 OpenCV extra 없이 동작하도록 `processor_backend="numpy"` 경로 고정
- 기존 가상환경에 구버전 `dxcam`이 남아 있어도 레거시 시그니처로 자동 재시도되도록 호환 가드 추가
- Windows `where ffmpeg` 출력 디코딩 경고 제거

### 삭제
- 설치/빌드 흐름에서 Windows 보안 상태 변경 및 Defender 회피 관련 처리 제거
- 무참조 `core/encoder/` 패키지 제거
- 무참조 `DXCamPool`, GPU helper 일부, `tests/unit/core/test_encoder_presets.py` 제거

## [0.56] - 2026-02-08

### 추가
- 의존성 UX 시스템: 첫 실행 시 자동 진단, 기능별 인터셉트, "다시 묻지 않기" 지원
- 버전 관리 모듈 (`core/version.py`) — Single Source of Truth
- `core/dependency_checker.py`: 통합 의존성 검사
- `ui/dependency_dialogs.py`: 의존성 안내 다이얼로그
- `ui/startup_check_dialog.py`: 시작 시 진단 다이얼로그

### 변경
- GIF 에디터 다크 테마 통합: `Colors`/`Fonts`를 `THEME_MID`에 동기화 (19개 파일)
- 빌드 시스템 개선: PyInstaller/Nuitka 옵션, 자동 venv, 의존성 제외 목록 강화
- `requirements.txt` 버전 범위 명시 및 정리

### 수정
- HDR 감지 Windows API 반환값 역전 (`hdr_utils.py`)
- GIF 디코더 무한루프 (`gif_decoder.py`: `continue` 전 인덱스 증가 누락)
- GIF 인코더 `stderr_text` NameError (`gif_encoder.py`)
- DXCam 워밍업 시 카메라 충돌 — 공유 카메라 사용으로 변경
- `screen_recorder.py` timing 리스트 무한 성장 (200개 초과 시 trim)
- `video_decoder.py` OOM 방지 — `iio.imiter()` 스트리밍으로 변경
- GPU/CPU 색조 편이 비율 불일치 (`editor_gpu_utils.py`)
- `worker_wx.py` executor 재생성 (shutdown 후 영구 파괴 문제)
- `editor_main_window_wx.py` 저장 콜백 `wx.CallAfter()` 래핑
- `frame_list_widget_wx.py` 우클릭 메뉴 핸들러 누적 방지
- 언어변경 콜백 시그니처 통일 (`retranslateUi(self, lang=None)`)
- DXCam `camera.start()` 락 내에서 호출
- 오디오 녹음 `recording=True` 위치 수정
- 키보드 디스플레이 스레드 안전성 (`_lock` 사용)
- 번역 콜백 누수 — `unregister_callback()` 추가

## [0.55] - 2026-02-03

### 추가
- CLI 인터페이스: `record`, `convert`, `config`, `doctor` 서브커맨드
- dxcam 선택적 설치 기능 (설정 다이얼로그에서)
- 크래시 핸들러 (`core/crash_handler.py`)

### 변경
- Windows 11 Dark Theme UI 리팩토링 (THEME_MID, FlatButton)
- DPI 스케일링 수정 (SYSTEM_AWARE)

### 수정
- 캡처 영역 동기화 버그 (`wx.EVT_MOVE` 바인딩 누락)
- 해상도 변경 시 C 레벨 크래시 (`wx.CallAfter()` 적용)
- FFmpeg 다운로드 스레드 크래시
- 코드 감사 1차 (20건): 레이스컨디션, GDI 핸들 누수, 좀비 스레드 등
