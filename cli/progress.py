"""터미널 진행률 표시"""
import sys
import time


class TerminalProgress:
    """인라인 진행률 표시 (\\r 사용)"""

    def __init__(self, quiet=False):
        self._quiet = quiet
        self._last_update = 0
        self._update_interval = 0.25  # 250ms마다 업데이트

    def update_recording(self, elapsed: float, frame_count: int, duration: float = None):
        """녹화 중 진행률"""
        if self._quiet:
            return
        now = time.time()
        if now - self._last_update < self._update_interval:
            return
        self._last_update = now

        mins, secs = divmod(int(elapsed), 60)
        if duration:
            remaining = max(0, duration - elapsed)
            r_mins, r_secs = divmod(int(remaining), 60)
            line = (
                f"\r  [녹화 중] {mins:02d}:{secs:02d} | "
                f"{frame_count} 프레임 | "
                f"남은 시간: {r_mins:02d}:{r_secs:02d}"
            )
        else:
            line = f"\r  [녹화 중] {mins:02d}:{secs:02d} | {frame_count} 프레임"

        sys.stdout.write(line + "    ")
        sys.stdout.flush()

    def update_paused(self, elapsed: float, frame_count: int):
        """일시정지 상태 표시"""
        if self._quiet:
            return
        now = time.time()
        if now - self._last_update < self._update_interval:
            return
        self._last_update = now

        mins, secs = divmod(int(elapsed), 60)
        line = f"\r  [일시정지] {mins:02d}:{secs:02d} | {frame_count} 프레임"
        sys.stdout.write(line + "    ")
        sys.stdout.flush()

    def update_encoding(self, current: int, total: int):
        """인코딩 진행률"""
        if self._quiet or total <= 0:
            return
        now = time.time()
        if now - self._last_update < self._update_interval:
            return
        self._last_update = now

        percent = min(100, int(current / total * 100))
        bar_width = 30
        filled = int(bar_width * percent / 100)
        bar = "#" * filled + "-" * (bar_width - filled)
        sys.stdout.write(f"\r  인코딩: [{bar}] {percent}%  ")
        sys.stdout.flush()

    def clear_line(self):
        """현재 줄 지우기"""
        if not self._quiet:
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()

    def print(self, message: str):
        """줄바꿈 포함 메시지 출력"""
        if not self._quiet:
            self.clear_line()
            print(message)
