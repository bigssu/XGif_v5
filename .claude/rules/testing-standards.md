# 테스트 표준 — XGif

## 실행 명령
```
.venv/Scripts/python.exe -m pytest tests/ -v
.venv/Scripts/python.exe -m pytest tests/test_config.py -v   # 특정 파일
.venv/Scripts/python.exe -m pytest tests/ -v -k "config"     # 키워드 필터
```

## 테스트 파일 위치
- 모든 테스트: `tests/` 디렉터리
- 파일명: `test_*.py` 접두사
- 클래스명: `Test*` 접두사
- 함수명: `test_*` 접두사

## 테스트 대상 모듈
| 테스트 파일 | 대상 |
|------------|------|
| `test_config.py` | 설정 파일 I/O (`cli/config.py`) |
| `test_safety.py` | 코드 품질 체크 (금지 패턴 정적 검사) |
| `test_utils.py` | 유틸 함수 (`core/utils.py`) |
| `test_version.py` | 버전 모듈 (`core/version.py`) |
| `test_encoder_e2e.py` | GIF 인코딩 E2E |
| `test_screen_recorder_runtime.py` | 스크린 레코더 |

## 작성 원칙
- wx 없이 실행 가능한 테스트만 `tests/`에 배치 (wx 의존 테스트는 별도 표시)
- 외부 프로세스(FFmpeg) 의존 테스트: `@pytest.mark.integration` 마커 사용
- 임시 파일 생성 테스트: `tmp_path` fixture 사용 (직접 파일 생성/삭제 금지)
- GPU 의존 테스트: `@pytest.mark.skipif(not gpu_available(), reason="GPU 없음")` 사용

## 새 기능 추가 시
- `core/` 함수 추가 → `tests/test_*.py`에 단위 테스트 추가 필수
- `cli/` 명령 추가 → CLI E2E 테스트 추가 권장
- wxPython GUI 변경 → 자동 테스트보다 수동 검증 (wxPython headless 어려움)
