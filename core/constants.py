"""핵심 모듈 공통 상수 — 매직 넘버 제거용."""

# ─── 프레임 처리 ───
MAX_FRAME_SIZE_BYTES = 100 * 1024 * 1024   # 100 MB — 단일 프레임 최대 크기
TIMING_SAMPLE_WINDOW = 200                  # FPS 측정 샘플 윈도우 (프레임 수)

# ─── 오버레이 ───
CLICK_HIGHLIGHT_DURATION_SEC = 0.3          # 클릭 하이라이트 지속 시간 (초)
CLICK_HIGHLIGHT_RADIUS = 20                 # 클릭 하이라이트 반지름 (px)

# ─── HDR ───
HDR_CACHE_DURATION_SEC = 2.0               # HDR 상태 캐시 유효 기간 (초)

# ─── 프레임 수집 ───
FRAME_COLLECTOR_TIMEOUT_SEC = 0.5          # 프레임 수집 큐 타임아웃 (초)

# ─── 인코딩 ───
ENCODING_TIMEOUT_SEC = 600                  # FFmpeg 인코딩 프로세스 타임아웃 (초)

# ─── 크래시 핸들링 ───
MAX_CRASH_COUNT = 10                        # 앱 자동 종료 크래시 임계값

# ─── 성능 모니터링 ───
PERFORMANCE_LOG_INTERVAL = 100             # 성능 로깅 간격 (프레임 수)

# ─── 프리뷰 ───
PREVIEW_FPS = 10                            # 미리보기 FPS
PREVIEW_UPDATE_MS = 100                     # 미리보기 타이머 간격 (ms)

# ─── 백엔드 ───
BACKEND_WARMUP_DELAY_MS = 500              # 백엔드 워밍업 대기 (ms)
ZERO_FRAME_WARNING_SEC = 3                 # 프레임 0개 경고 타이밍 (초)
