"""
통합 설정 관리 — AppSettings dataclass (Single Source of Truth)

기존 core/defaults.py, cli/config.py, ui/settings_dialog.py에 분산된
설정 정의를 하나의 typed dataclass로 통합한다.
INI 포맷 유지 (configparser 기반), %APPDATA%\\XGif\\config.ini 저장.
"""

import configparser
import contextlib
import tempfile
import logging
import os
import shutil
import uuid
from dataclasses import dataclass, fields
from typing import Optional

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _config_lock(path, *, reading=False):
    # The INI is atomically replaced, so lock a stable sibling file.
    lock_path = os.fspath(path) + ".lock"
    try:
        handle = open(lock_path, "a+b")  # noqa: SIM115
    except PermissionError:
        if not reading:
            raise
        # Read-only profiles created before locking may have no sidecar.
        try:
            handle = open(lock_path, "rb")  # noqa: SIM115
        except FileNotFoundError:
            yield
            return
    with handle:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def get_config_path() -> str:
    """config.ini 경로 반환 (%APPDATA%\\XGif\\config.ini)"""
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(appdata, "XGif", "config.ini")


@dataclass
class AppSettings:
    """애플리케이션 설정 — 모든 키가 typed 필드로 정의됨.

    모든 값은 내부적으로 문자열로 저장/로드된다 (INI 호환).
    get_bool / get_int 헬퍼로 타입 안전 접근 가능.
    """

    # --- 공통 (CLI + UI) ---
    language: str = "ko"
    capture_backend: str = "gdi"
    encoder: str = "auto"
    codec: str = "h264"
    memory_limit_mb: str = "1024"
    hdr_correction: str = "false"
    mic_audio: str = "false"
    watermark: str = "false"
    click_highlight: str = "false"
    keyboard_display: str = "false"

    # --- UI 전용 ---
    preview_enabled: str = "false"
    skip_ffmpeg_check: str = "false"
    skip_cupy_check: str = "false"
    skip_dxcam_check: str = "false"
    startup_dep_checked: str = "false"

    # --- UI 상태 (마지막 세션 복원용) ---
    fps: str = "15"
    resolution_preset: str = "320 × 240"
    last_save_dir: str = ""

    def __post_init__(self):
        self._baseline = {f.name: f.default for f in fields(self)}

    # ─── 타입 안전 접근자 ───

    def get_bool(self, key: str) -> bool:
        """설정 값을 bool로 반환."""
        val = getattr(self, key, "false")
        return str(val).lower() == "true"

    def get_int(self, key: str, default: int = 0) -> int:
        """설정 값을 int로 반환."""
        try:
            return int(getattr(self, key, default))
        except (ValueError, TypeError):
            return default

    def get(self, key: str, fallback: str = "") -> str:
        """설정 값을 문자열로 반환 (configparser 호환)."""
        return str(getattr(self, key, fallback))

    def set(self, key: str, value: str, *, force: bool = False) -> None:
        """설정 값 변경."""
        if self.has_key(key):
            setattr(self, key, value)
            if force:
                self._baseline.pop(key, None)

    # ─── 유효 키 검사 ───

    @classmethod
    def valid_keys(cls) -> set:
        """유효한 설정 키 집합 반환."""
        return {f.name for f in fields(cls)}

    def has_key(self, key: str) -> bool:
        return key in self.valid_keys()

    # ─── 딕셔너리 변환 ───

    def to_dict(self) -> dict:
        """모든 설정을 {키: 문자열값} 딕셔너리로 반환."""
        return {f.name: str(getattr(self, f.name)) for f in fields(self)}

    # ─── 기본값 복원 ───

    def reset(self) -> None:
        """모든 설정을 기본값으로 복원."""
        defaults = AppSettings()
        for f in fields(self):
            setattr(self, f.name, getattr(defaults, f.name))
        self._baseline.clear()

    # ─── 직렬화 ───

    def save(self, path: Optional[str] = None, *, recover_invalid: bool = False) -> None:
        """INI 파일로 저장."""
        path = path or get_config_path()
        config_dir = os.path.dirname(path) or "."
        os.makedirs(config_dir, exist_ok=True)

        with _config_lock(path):
            self._save_locked(path, config_dir, recover_invalid)

    def _save_locked(self, path, config_dir, recover_invalid):
        config = configparser.ConfigParser(interpolation=None)
        # 기존 파일이 있으면 읽어서 알 수 없는 키 보존
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fp:
                    config.read_file(fp)
            except (configparser.Error, UnicodeError):
                if not recover_invalid:
                    raise
                backup = f"{path}.corrupt-{uuid.uuid4().hex}.bak"
                try:
                    shutil.copyfile(path, backup)
                except OSError:
                    with contextlib.suppress(FileNotFoundError):
                        os.remove(backup)
                    raise
                logger.warning("Preserved unreadable settings in %s", backup)
                config = configparser.ConfigParser(interpolation=None)

        if not config.has_section("General"):
            config.add_section("General")

        for key, value in self.to_dict().items():
            if value != self._baseline.get(key) or not config.has_option("General", key):
                config.set("General", key, value)

        staged_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=config_dir, prefix=".config-", suffix=".tmp", delete=False,
            ) as fp:
                staged_path = fp.name
                config.write(fp)
                fp.flush()
                os.fsync(fp.fileno())
            os.replace(staged_path, path)
            self._adopt(config)
        finally:
            if staged_path is not None:
                with contextlib.suppress(FileNotFoundError):
                    os.remove(staged_path)

    def _adopt(self, config):
        for f in fields(self):
            setattr(self, f.name, config.get("General", f.name, fallback=f.default))
        self._baseline = self.to_dict()

    @classmethod
    def load(cls, path: Optional[str] = None) -> "AppSettings":
        """INI 파일에서 로드. 파일이 없으면 기본값 반환."""
        path = path or get_config_path()
        settings = cls()

        if not os.path.exists(path):
            return settings

        config = configparser.ConfigParser(interpolation=None)
        try:
            with _config_lock(path, reading=True), open(path, encoding="utf-8") as fp:
                config.read_file(fp)
        except (OSError, UnicodeError, configparser.Error) as exc:
            logger.warning("Settings could not be loaded; using defaults: %s", exc)
            return settings

        if config.has_section("General"):
            settings._adopt(config)

        return settings

    # ─── configparser 호환 래퍼 ───
    # 기존 코드가 self.settings.get('General', key, fallback=...)
    # 패턴을 사용하므로 점진 이행을 위해 제공.

    def cp_get(self, section: str, key: str, fallback: str = "") -> str:
        """configparser.get() 호환 래퍼."""
        return self.get(key, fallback)

    def cp_set(self, section: str, key: str, value: str) -> None:
        """configparser.set() 호환 래퍼."""
        self.set(key, value)

    def has_section(self, section: str) -> bool:
        """configparser 호환 — 항상 True (단일 섹션)."""
        return True

    def add_section(self, section: str) -> None:
        """configparser 호환 — no-op."""
        pass

    def write(self, fp) -> None:
        """configparser.write() 호환 — save()로 위임."""
        # fp는 이미 열린 파일 객체이므로, 직접 configparser 포맷 작성
        config = configparser.ConfigParser(interpolation=None)
        config.add_section("General")
        for f in fields(self):
            config.set("General", f.name, str(getattr(self, f.name)))
        config.write(fp)
