# Changelog

## [Unreleased]

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
