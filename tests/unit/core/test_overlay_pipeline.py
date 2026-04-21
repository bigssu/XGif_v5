"""OverlayPipeline 적용 순서 테스트."""

import numpy as np
from core.overlay.pipeline import OverlayBase, OverlayPipeline


class DummyOverlay(OverlayBase):
    """테스트용 더미 오버레이."""

    def __init__(self, label: str):
        super().__init__()
        self.label = label
        self.applied = False

    def apply(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        self.applied = True
        # 프레임의 첫 픽셀에 마커 추가
        frame[0, 0, 0] += 1
        return frame


class TestOverlayPipeline:
    def test_apply_order(self):
        p = OverlayPipeline()
        o1 = DummyOverlay("first")
        o1.set_enabled(True)
        o2 = DummyOverlay("second")
        o2.set_enabled(True)
        p.add(o1)
        p.add(o2)

        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        result = p.apply(frame)

        assert o1.applied
        assert o2.applied
        assert result[0, 0, 0] == 2  # 두 번 적용

    def test_disabled_overlay_skipped(self):
        p = OverlayPipeline()
        o1 = DummyOverlay("enabled")
        o1.set_enabled(True)
        o2 = DummyOverlay("disabled")
        o2.set_enabled(False)
        p.add(o1)
        p.add(o2)

        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        result = p.apply(frame)

        assert o1.applied
        assert not o2.applied
        assert result[0, 0, 0] == 1

    def test_empty_pipeline(self):
        p = OverlayPipeline()
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        result = p.apply(frame)
        assert np.array_equal(result, frame)

    def test_remove(self):
        p = OverlayPipeline()
        o = DummyOverlay("test")
        p.add(o)
        p.remove(o)
        assert len(p.overlays) == 0

    def test_clear(self):
        p = OverlayPipeline()
        p.add(DummyOverlay("a"))
        p.add(DummyOverlay("b"))
        p.clear()
        assert len(p.overlays) == 0
