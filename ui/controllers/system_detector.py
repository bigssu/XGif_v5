"""시스템 능력 감지 컨트롤러 — GPU, FFmpeg, 백엔드 등"""

import logging
import threading
from typing import TYPE_CHECKING

import wx

from core.gpu_utils import detect_gpu, GpuInfo
from core.hdr_utils import is_hdr_active
from ui.i18n import tr

if TYPE_CHECKING:
    from ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class SystemDetector:
    """GPU/FFmpeg/백엔드 감지 및 UI 반영."""

    def __init__(self, window: "MainWindow") -> None:
        self._w = window
        self._gpu_initialized = False

    # ─── 비동기 시스템 감지 ───

    def detect_system_capabilities(self) -> None:
        """시스템 능력 감지 및 최적 파이프라인 적용 (비동기 시작)."""
        cap_mgr = self._w._capability_manager

        def _worker():
            try:
                caps = cap_mgr.detect_capabilities()
            except Exception as e:
                logger.warning("[SystemDetector] 시스템 능력 감지 실패: %s", e)
                return
            wx.CallAfter(self._apply_detected_capabilities, caps)

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_detected_capabilities(self, caps) -> None:
        """감지된 시스템 능력을 UI에 적용 (메인 스레드)."""
        w = self._w
        try:
            pipeline = caps.optimal_pipeline
            if pipeline:
                user_backend = w.settings.get("capture_backend", "gdi")
                if w.recorder:
                    if user_backend == "auto":
                        hdr_active = is_hdr_active()
                        actual_backend = "gdi" if hdr_active else "dxcam"
                        logger.info("[SystemDetector] Auto: HDR %s → %s",
                                    "ON" if hdr_active else "OFF", actual_backend)
                        w.recorder.set_capture_backend(actual_backend)
                    elif user_backend in ("dxcam", "gdi"):
                        logger.info("[SystemDetector] 사용자 설정 백엔드 유지: %s", user_backend)
                        w.recorder.set_capture_backend(user_backend)
                    else:
                        w.recorder.set_capture_backend(pipeline.capture_backend)

                if w.encoder:
                    w.encoder.set_codec(pipeline.codec)
                    encoder_type = "auto"
                    if "nvenc" in pipeline.encoder:
                        encoder_type = "nvenc"
                    elif "qsv" in pipeline.encoder:
                        encoder_type = "qsv"
                    elif "amf" in pipeline.encoder:
                        encoder_type = "amf"
                    elif "lib" in pipeline.encoder:
                        encoder_type = "cpu"
                    w.encoder.set_preferred_encoder(encoder_type)

                logger.info("[SystemDetector] 최적 파이프라인 적용: %s", pipeline.name)

            if caps.has_nvidia_gpu:
                def _detect_cupy_bg():
                    try:
                        info = detect_gpu(skip_cupy=False)
                    except Exception:
                        info = GpuInfo()
                    wx.CallAfter(self._on_auto_gpu_detect_done, info)
                threading.Thread(target=_detect_cupy_bg, daemon=True).start()

        except Exception as e:
            logger.warning("[SystemDetector] 시스템 능력 적용 실패: %s", e)

    def _on_auto_gpu_detect_done(self, gpu_info: GpuInfo) -> None:
        self._gpu_initialized = True
        has_gpu = gpu_info.has_cupy
        self._w.capture_control_bar.set_gpu_status(has_gpu)
        if has_gpu:
            logger.info("[SystemDetector] GPU 자동 활성화: CuPy 사용 가능")
        else:
            logger.info("[SystemDetector] GPU 자동 감지 완료: CuPy 미사용")

    # ─── GPU 버튼 ───

    def on_gpu_button_click(self) -> None:
        """GPU 버튼 클릭 — 비동기 GPU 감지 후 정보 표시."""
        if self._gpu_initialized:
            self._show_gpu_info_dialog()
            return

        bar = self._w.capture_control_bar
        bar.gpu_status_button.SetLabel(tr("gpu_initializing"))
        bar.gpu_status_button.Enable(False)

        def _detect_in_bg():
            try:
                info = detect_gpu()
            except Exception:
                info = GpuInfo()
            wx.CallAfter(self._on_gpu_detect_done, info)

        threading.Thread(target=_detect_in_bg, daemon=True).start()

    def _on_gpu_detect_done(self, gpu_info: GpuInfo) -> None:
        self._gpu_initialized = True
        bar = self._w.capture_control_bar
        bar.gpu_status_button.Enable(True)
        bar.set_gpu_status(gpu_info.has_cuda)
        self._show_gpu_info_dialog()

    def _show_gpu_info_dialog(self) -> None:
        try:
            gpu_info = detect_gpu(skip_cupy=True)
        except Exception:
            gpu_info = GpuInfo()

        if not gpu_info.has_cuda:
            wx.MessageBox(tr("gpu_not_found_msg"), tr("gpu_info_title"),
                          wx.OK | wx.ICON_INFORMATION, self._w)
            return

        msg = tr("gpu_info_msg",
                 name=gpu_info.gpu_name or "Unknown",
                 memory=gpu_info.gpu_memory_mb,
                 cupy="O" if gpu_info.has_cupy else "X",
                 nvenc="O" if gpu_info.ffmpeg_nvenc else "X",
                 driver=gpu_info.driver_version or "N/A")
        wx.MessageBox(msg, tr("gpu_info_title"),
                      wx.OK | wx.ICON_INFORMATION, self._w)

    # ─── HDR ───

    def update_hdr_label(self) -> None:
        """HDR 모드 레이블 업데이트."""
        w = self._w
        try:
            hdr_force = bool(w.recorder and getattr(w.recorder, "hdr_correction_force", False))
            if is_hdr_active() or hdr_force:
                hdr_text = "HDR"
            else:
                hdr_text = ""
            if hasattr(w, "hdr_label") and w.hdr_label is not None:
                w.hdr_label.SetLabel(hdr_text)
                if hdr_text:
                    w.hdr_label.Show()
                else:
                    w.hdr_label.Hide()
        except (RuntimeError, AttributeError) as e:
            logger.debug("HDR label update failed: %s", e)
