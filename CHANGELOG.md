# Changelog

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
