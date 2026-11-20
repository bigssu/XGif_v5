# XGif

Windows용 GIF/MP4 화면 녹화 프로그램. GUI와 CLI 모두 지원.

## 현재 기준

- 출시 후보 버전: `2.2.8`
- 문서 갱신일: `2026-11-20`
- 검증 환경: Windows, Python 3.11.9 프로젝트 `.venv`
- 주요 의존성 floor: `wxPython 4.2.5`, `dxcam 0.3.0`, `PyInstaller 6.20.0`
- 이전 2.2.0 후보의 테스트·패키지 검증: [검증 기록](docs/RELEASE_HARDENING_2026-11-17.md)
- 빌드 참고: `build_optimized.py`가 `XGif.spec`를 빌드 시점에 동적 생성
- 사내 배포 기준: 코드 서명 없이 PyInstaller/선택적 Inno Setup 산출물을 사용

## 주요 기능

- **화면 녹화**: GIF 및 MP4 형식으로 화면의 전체 또는 특정 영역 녹화
- **긴 GIF 녹화**: 원본 프레임은 설정한 메모리 한도와 128 MiB 중 작은 값까지 RAM에 보관하고, 이후에는 Windows 임시 폴더에 기록합니다. 1080p·15 FPS에서 임시 공간은 분당 약 5.2 GiB가 필요합니다. 공간이 부족하면 그때까지 기록한 프레임을 저장할 수 있습니다.
- **캡처 백엔드**: GDI (기본) 또는 dxcam (DXGI Desktop Duplication, 고성능)
- **GPU 가속**: NVIDIA GPU 환경에서 CuPy를 이용한 실시간 프레임 처리
- **하드웨어 인코딩**: NVENC / QSV / AMF 자동 감지
- **HDR 보정**: HDR 모니터에서 정확한 색상 캡처
- **오디오 녹음**: 마이크 입력 동시 녹음 (MP4)
- **오버레이**: 워터마크, 키보드 입력 표시, 마우스 클릭 하이라이트
- **GIF 에디터**: 프레임 편집, 자르기, 크기 변경, 효과, 텍스트/스티커 삽입
- **정밀 입력 UX**: 드롭다운은 항목 높이에 맞춰 열리고, 숫자/텍스트 필드는 클릭한 자리에서 바로 입력
- **안정적인 에디터 조작**: 저장 시 재생 중인 프리뷰를 즉시 멈추고, hover가 흔들려도 버튼 클릭이 유실되지 않음
- **CLI 지원**: 스크립트/자동화를 위한 커맨드라인 인터페이스
- **다국어**: 한국어 / 영어

## 요구 사항

- **OS**: Windows 10 / 11 (64-bit)
- **Python**: 3.11 이상
- **FFmpeg**: MP4 인코딩에 필요 (첫 실행 시 자동 다운로드)

### 선택적 의존성

| 패키지 | 용도 |
|--------|------|
| `dxcam` | 고성능 화면 캡처 (현재 floor: `0.3.0`) |
| `requirements-gpu.txt` | Windows CUDA 13.x용 GPU 가속 패키지 묶음 (`cupy-cuda13x[ctk]` 포함) |
| `scipy` | 고급 오디오 믹싱 (권장: `1.17.x`) |

## 설치

### 소스에서 실행

```bash
# 저장소 클론
git clone https://github.com/bigssu/XGif_v5.git
cd XGif_v5

# 가상환경 생성 (Python 3.11)
py -3.11 -m venv .venv

# 의존성 설치
.venv\Scripts\pip install -r requirements.txt

# 선택: NVIDIA GPU + CUDA 13.x 환경
.venv\Scripts\pip install -r requirements-gpu.txt

# 실행
.venv\Scripts\python main.py
```

### 빌드된 실행 파일

```bash
# PyInstaller로 exe 빌드
.venv\Scripts\python build_optimized.py

# 선택: Inno Setup 설치 파일까지 생성
.venv\Scripts\python build_optimized.py --installer
```

빌드 결과물은 `dist/` 폴더에 생성됩니다. 사내 배포는 서명 플래그 없이 진행합니다.

GUI는 `XGif.exe`, 터미널·자동화는 `XGif-cli.exe`를 사용합니다. CLI 실행 파일은
도움말·진행 상태·오류와 종료 코드를 콘솔에 전달합니다. 예: `XGif-cli.exe --help`,
`XGif-cli.exe convert input.gif output.mp4`. MP4 녹화와 CLI 변환에는 FFmpeg가 필요하고, 편집기에서 비디오를 열 때는 FFprobe도 필요합니다. `XGif-cli.exe doctor --install-ffmpeg`로 두 도구를 설치하거나 복구할 수 있습니다. 자동 설치 위치는 `%LOCALAPPDATA%\XGif\ffmpeg`입니다.

GPU 가속은 선택 사항입니다. 이번 Windows 설치본은 **CPython 3.11 64비트**용 CuPy를 사용합니다. GPU 설정의 **직접 설치** 또는 `XGif-cli.exe doctor --install-cupy`로 설치할 수 있습니다. 호환되는 기존 환경은 재사용합니다. 새 환경이 필요한 경우 PC에 같은 버전·비트 수의 Python이 있어야 합니다.

`%LOCALAPPDATA%\XGif\env`에 Python 3.12 등 다른 환경이 있으면 그대로 보존하고, 3.11용 패키지는 인접한 `env-cp311-64`에 설치합니다. **재검사**와 `XGif-cli.exe doctor`는 앱에서 CuPy를 불러와 장치 감지와 실제 CUDA 연산을 확인합니다. GUI 진단 로그는 `%APPDATA%\XGif\logs\app.log`에 있습니다.

## 사용법

### GUI 모드

```bash
.venv\Scripts\python main.py
```

1. 녹화 영역을 드래그하여 선택하거나 프리셋 해상도 선택
2. **REC** 버튼으로 녹화 시작
3. **Stop** 버튼으로 녹화 종료 및 저장
4. 저장된 GIF를 클릭하면 GIF 에디터가 열림
5. FPS/품질 드롭다운은 항목 수만큼만 열리며, 프레임 시간/크기/속도 같은 숫자 필드는 필드 안에서 직접 입력 가능

녹화 중에는 일시정지해도 캡처 영역이 고정됩니다. 영역을 바꾸려면 현재 녹화를 마친 뒤 다음 녹화의 테두리를 이동하세요.

### CLI 모드

```bash
# 전체 화면 GIF 녹화
python main.py record -o screen.gif

# 특정 영역 30fps MP4 녹화
python main.py record -r 100,100,1920x1080 -f 30 -o demo.mp4

# 3초 딜레이 후 10초 녹화
python main.py record -d 10 --delay 3 -o short.gif

# 커서 없이 녹화
python main.py record --no-cursor -o clean.gif

# 환경 진단
python main.py doctor

# FFmpeg 자동 설치
python main.py doctor --install-ffmpeg

# 설정 확인
python main.py config list

# 파일 변환 (GIF → MP4)
python main.py convert input.gif -F mp4

# 파일 변환 (MP4 → GIF, 리사이즈)
python main.py convert input.mp4 -F gif --resize 480x320
```

### CLI 녹화 중 키 조작

`-d`에는 일시정지 시간을 제외한 녹화 시간을 지정합니다. 인코딩에 실패하면 CLI가 복구 폴더 위치를 출력합니다. 복구가 완료된 폴더에서 `recovery.txt`의 FFmpeg 명령을 실행하면 `video.bgr`과 함께 보존된 마이크 음성으로 결과 파일을 만들 수 있습니다.

| 키 | 동작 |
|----|------|
| `Enter` / `q` | 녹화 중지 및 저장 |
| `Space` | 일시정지 / 재개 |
| `Ctrl+C` | 녹화 취소 (저장 안 함) |

## 프로젝트 구조

```
XGif/
├── main.py                 # 진입점 (GUI/CLI 분기)
├── build_optimized.py      # PyInstaller/Nuitka 빌드 스크립트
├── core/                   # 핵심 엔진 (wx 의존성 없음)
│   ├── screen_recorder.py  # 화면 녹화 엔진
│   ├── gif_encoder.py      # GIF 인코딩
│   ├── capture_backend.py  # GDI/dxcam 캡처 백엔드
│   ├── audio_recorder.py   # 오디오 녹음
│   ├── gpu_utils.py        # CuPy GPU 유틸리티
│   ├── hdr_utils.py        # HDR 감지/보정
│   ├── watermark.py        # 워터마크 오버레이
│   ├── keyboard_display.py # 키보드 입력 표시
│   └── ...
├── ui/                     # wxPython GUI
│   ├── main_window.py      # 메인 윈도우
│   ├── capture_overlay.py  # 캡처 영역 오버레이
│   ├── settings_dialog.py  # 설정 다이얼로그
│   └── ...
├── cli/                    # CLI 인터페이스
│   ├── main.py             # argparse 정의
│   ├── recorder.py         # CLI 녹화 세션
│   ├── converter.py        # GIF↔MP4 변환
│   ├── doctor.py           # 환경 진단
│   └── config.py           # 설정 관리
├── editor/                 # GIF 에디터
│   ├── core/               # 에디터 코어 (디코더, 인코더, 효과)
│   └── ui/                 # 에디터 UI (다이얼로그, 툴바)
├── resources/              # 아이콘 등 리소스
└── tests/                  # 테스트
```

## 설정

설정 파일 위치: `%APPDATA%\XGif\config.ini`

`config.ini.example`에서 사용 가능한 설정 항목과 기본값을 확인할 수 있습니다.

## 디버그 모드

```bash
# 환경변수
set XGIF_DEBUG=1
python main.py

# 또는 플래그
python main.py --debug
```

로그 파일: `%APPDATA%\XGif\logs\app.log`

## 테스트

```bash
.venv\Scripts\python -m pytest tests/ -v
```

## 라이선스

[MIT License](LICENSE)
