"""기본 설정값 — core.settings.AppSettings로 이전됨.

하위 호환을 위해 COMMON_DEFAULTS를 유지한다.
새 코드는 ``from core.settings import AppSettings`` 를 사용할 것.
"""

from core.settings import AppSettings as _AppSettings

# 하위 호환: 기존 COMMON_DEFAULTS dict를 AppSettings 기본값에서 생성
_defaults = _AppSettings()
COMMON_DEFAULTS = {
    "language": _defaults.language,
    "capture_backend": _defaults.capture_backend,
    "encoder": _defaults.encoder,
    "codec": _defaults.codec,
    "memory_limit_mb": _defaults.memory_limit_mb,
    "hdr_correction": _defaults.hdr_correction,
    "mic_audio": _defaults.mic_audio,
    "watermark": _defaults.watermark,
    "click_highlight": _defaults.click_highlight,
    "keyboard_display": _defaults.keyboard_display,
}
