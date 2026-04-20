# Windows 인코딩 규칙 — XGif

## stdout/stderr UTF-8 재설정
`main.py` 최상단에서 이미 처리됨. 새 진입점을 추가할 때도 동일하게 적용한다:

```python
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass
```

## 파일 I/O
- 텍스트 파일 읽기/쓰기는 반드시 `encoding='utf-8'` 명시
- `open(path, 'r')` — 금지 (플랫폼 기본 인코딩에 의존)
- `open(path, 'r', encoding='utf-8')` — 올바른 방식

## 설정 파일 (config.ini)
- `configparser.ConfigParser` 사용 시: `read(path, encoding='utf-8')`
- 쓰기 시: `write()` 전 `open(path, 'w', encoding='utf-8')` 명시

## 로그 파일
- 로그 핸들러 생성 시 `encoding='utf-8'` 지정 (`RotatingFileHandler(..., encoding='utf-8')`)

## 경로 처리
- Windows 경로에 한글/유니코드 포함 가능: `pathlib.Path` 사용 권장
- `os.path.join()` 대신 `Path(...) / 'subdir'` 패턴 선호
- 환경변수 `%APPDATA%` 접근: `os.environ.get('APPDATA', '')` + `Path` 조합

## subprocess에서 한글 경로
- FFmpeg 등 subprocess 호출 시 경로를 `str(path)` 로 변환하여 전달
- `creationflags=subprocess.CREATE_NO_WINDOW` — GUI 빌드에서 콘솔 창 숨김 (이미 적용된 패턴 유지)
