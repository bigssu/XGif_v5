# XGif

Windows용 GIF/MP4 화면 녹화 프로그램. GUI와 CLI 모두 지원.

## 주요 기능

- **화면 녹화**: GIF 및 MP4 형식으로 화면의 전체 또는 특정 영역 녹화
- **캡처 백엔드**: GDI (기본) 또는 dxcam (DXGI Desktop Duplication, 고성능)
- **GPU 가속**: NVIDIA GPU 환경에서 CuPy를 이용한 실시간 프레임 처리
- **하드웨어 인코딩**: NVENC / QSV / AMF 자동 감지
- **HDR 보정**: HDR 모니터에서 정확한 색상 캡처
- **오디오 녹음**: 마이크 입력 동시 녹음 (MP4)
- **오버레이**: 워터마크, 키보드 입력 표시, 마우스 클릭 하이라이트
- **GIF 에디터**: 프레임 편집, 자르기, 크기 변경, 효과, 텍스트/스티커 삽입
- **CLI 지원**: 스크립트/자동화를 위한 커맨드라인 인터페이스
- **다국어**: 한국어 / 영어

## 요구 사항

- **OS**: Windows 10 / 11 (64-bit)
- **Python**: 3.11 이상
- **FFmpeg**: MP4 인코딩에 필요 (첫 실행 시 자동 다운로드)

### 선택적 의존성

| 패키지 | 용도 |
|--------|------|
| `dxcam` | 고성능 화면 캡처 (DXGI) |
| `cupy-cuda12x` | GPU 가속 프레임 처리 |
| `scipy` | 고급 오디오 믹싱 |

## 설치

### 소스에서 실행

```bash
# 저장소 클론
git clone https://github.com/bigssu/XGif_v5.git
cd XGif

# 가상환경 생성 (Python 3.11)
py -3.11 -m venv .venv

# 의존성 설치
.venv\Scripts\pip install -r requirements.txt

# 실행
.venv\Scripts\python main.py
```

### 빌드된 실행 파일

```bash
# PyInstaller로 exe 빌드
.venv\Scripts\python build_optimized.py
```

빌드 결과물은 `dist/` 폴더에 생성됩니다.

## 사용법

### GUI 모드

```bash
.venv\Scripts\python main.py
```

1. 녹화 영역을 드래그하여 선택하거나 프리셋 해상도 선택
2. **REC** 버튼으로 녹화 시작
3. **Stop** 버튼으로 녹화 종료 및 저장
4. 저장된 GIF를 클릭하면 GIF 에디터가 열림

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
