# XGif Bootstrapper

Python 3.11 + wxPython을 내장한 의존성 설치 부트스트래퍼

## 구조

```
bootstrap/
├── app_entry.py          # 메인 진입점
├── ui_main.py            # wxPython UI
├── logging_setup.py      # 로깅 설정
├── paths.py              # 경로 관리
├── requirements.txt      # 의존성
├── build.bat             # 전체 빌드 스크립트
├── build_simple.bat      # 간단 빌드
├── XGif_Bootstrapper.spec # PyInstaller spec
└── icon.ico              # (선택) 앱 아이콘
```

## 빌드 환경 설정

### 1. Python 3.11 가상환경 생성 (권장)

```powershell
cd C:\Users\su\Downloads\bootstrap
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. 의존성 설치

```powershell
pip install -r requirements.txt
```

### 3. 빌드

**방법 A: 간단 빌드**
```powershell
.\build_simple.bat
```

**방법 B: 전체 빌드 (아이콘 포함)**
```powershell
.\build.bat
```

**방법 C: spec 파일 사용**
```powershell
pyinstaller XGif_Bootstrapper.spec
```

## 빌드 결과

```
dist/XGif_Bootstrapper/
├── XGif_Bootstrapper.exe   # 실행 파일
└── _internal/              # Python 런타임 + 라이브러리
```

## 클린 PC에서 테스트

1. `dist/XGif_Bootstrapper` 폴더 전체를 USB나 네트워크로 복사
2. Python이 설치되지 않은 PC에서 `XGif_Bootstrapper.exe` 실행
3. 확인 사항:
   - UI가 즉시 표시되는가?
   - 로그가 `%LOCALAPPDATA%\XGif_Bootstrapper\logs\`에 생성되는가?
   - "로그 폴더 열기" 버튼이 작동하는가?

## 커스터마이징

### 실제 설치 로직 추가

`ui_main.py`의 `_run_install_task()` 메서드를 수정하여 실제 의존성 설치 로직 구현:

```python
def _run_install_task(self):
    try:
        # 1. pip 패키지 설치
        self._install_pip_packages()
        
        # 2. FFmpeg 다운로드
        self._download_ffmpeg()
        
        # 3. 기타 설정
        self._configure_app()
        
        evt = TaskCompleteEvent(success=True, error=None)
        wx.PostEvent(self, evt)
        
    except Exception as e:
        evt = TaskCompleteEvent(success=False, error=str(e))
        wx.PostEvent(self, evt)
```

### 아이콘 변경

1. 256x256 이상의 .ico 파일 준비
2. `icon.ico`로 저장
3. `build.bat` 또는 spec 파일로 빌드

## 문제 해결

### "wxPython을 찾을 수 없음" 오류

```powershell
pip install wxPython --force-reinstall
```

### 빌드 파일 크기가 너무 큼

spec 파일의 `excludes` 섹션에 불필요한 모듈 추가

### 콘솔 창이 표시됨

`--windowed` 옵션이 적용되었는지 확인, 또는 spec 파일에서 `console=False` 확인
