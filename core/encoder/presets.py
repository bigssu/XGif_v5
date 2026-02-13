"""인코더 품질/타입 프리셋."""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class QualityPreset:
    """GIF 품질 프리셋."""
    name: str
    colors: int          # 팔레트 색상 수
    dither: str          # 디더링 알고리즘
    stats_mode: str      # palettegen stats_mode
    bayer_scale: int     # 베이어 스케일 (0-5)


QUALITY_PRESETS: Dict[str, QualityPreset] = {
    "high": QualityPreset(
        name="high",
        colors=256,
        dither="sierra2_4a",
        stats_mode="diff",
        bayer_scale=3,
    ),
    "medium": QualityPreset(
        name="medium",
        colors=192,
        dither="bayer",
        stats_mode="diff",
        bayer_scale=4,
    ),
    "low": QualityPreset(
        name="low",
        colors=128,
        dither="bayer",
        stats_mode="full",
        bayer_scale=5,
    ),
}

# FFmpeg 인코더 이름 → 사용자 표시 이름
ENCODER_TYPE_MAP: Dict[str, str] = {
    "auto": "Auto",
    "nvenc": "NVENC",
    "qsv": "QSV",
    "amf": "AMF",
    "cpu": "CPU",
}
