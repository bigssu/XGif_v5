"""XGif CLI 패키지"""

# CLI 종료 코드 상수 (일관성을 위해 모든 서브커맨드에서 사용)
EXIT_SUCCESS = 0         # 정상 완료
EXIT_USER_ERROR = 1      # 사용자 입력 오류 (잘못된 인자, 파일 미존재 등)
EXIT_DEPENDENCY = 2      # 의존성 누락 (FFmpeg 미설치 등)
EXIT_RUNTIME_ERROR = 3   # 실행 중 오류 (인코딩 실패, 녹화 실패 등)
