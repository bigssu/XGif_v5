# FFmpeg 서브프로세스 규칙 — XGif

## 필수 패턴

FFmpeg 서브프로세스는 항상 `try-finally`로 감싸서 예외 시 프로세스를 종료한다.

```python
import subprocess

process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)
try:
    stdout, stderr = process.communicate(timeout=300)
except Exception:
    process.kill()
    raise
finally:
    # 리소스 정리
    if process.poll() is None:
        process.kill()
```

## 금지 패턴
- `except:` bare except 사용 금지 → `except Exception:` 사용
- `process.terminate()` 후 `wait()` 없이 종료 → 좀비 프로세스 발생 가능
- FFmpeg 경로 하드코딩 금지 → `core/ffmpeg_installer.py`의 경로 해석 함수 사용

## 경로 처리
- FFmpeg 바이너리 경로: `core/ffmpeg_installer.py`에서 관리
- 빌드된 실행 파일(`getattr(sys, 'frozen', False)`)에서는 `sys._MEIPASS` 기반 경로 사용
- `ffmpeg/` 디렉터리는 `.gitignore`에 포함됨 — 빌드 시만 포함

## 인코딩 인수
- Windows에서 한글 경로를 포함한 FFmpeg 명령: `encoding='utf-8'` 또는 바이트 인수 사용
- `subprocess.Popen(..., encoding='utf-8')` 또는 모든 경로 인수를 `str(Path(...))` 으로 변환

## 타임아웃
- `communicate(timeout=N)` 으로 무한 대기 방지
- 긴 인코딩 작업의 경우 백그라운드 스레드에서 실행하고 UI에 진행률 피드백 제공
