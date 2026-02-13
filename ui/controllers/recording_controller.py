"""녹화 시작/중지/일시정지 컨트롤러."""

import logging
from typing import TYPE_CHECKING

import wx

from core.utils import safe_delete_timer
from ui.i18n import tr

if TYPE_CHECKING:
    from ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class RecordingController:
    """녹화 라이프사이클 제어 — 상태 전환, 프레임 수집, 오디오."""

    def __init__(self, window: "MainWindow") -> None:
        self._w = window

    # ─── 공개 액션 ───

    def on_rec_clicked(self) -> None:
        """REC/STOP 토글 버튼 클릭."""
        w = self._w
        try:
            if w.record_state == w.STATE_READY:
                self.start_recording()
            elif w.record_state == w.STATE_RECORDING:
                self.stop_recording()
            elif w.record_state == w.STATE_PAUSED:
                self.resume_recording()
        except Exception as e:
            wx.MessageBox(tr("start_failed").format(str(e)), tr("error"),
                          wx.OK | wx.ICON_ERROR)
            logger.warning("REC 버튼 클릭 오류: %s", e)

    def on_pause_clicked(self) -> None:
        w = self._w
        if w.record_state == w.STATE_RECORDING:
            self.pause_recording()

    def on_stop_clicked(self) -> None:
        w = self._w
        if w.record_state != w.STATE_READY:
            w.status_msg_label.SetLabel(tr("recording"))
            self.stop_recording()

    # ─── 녹화 시작 ───

    def start_recording(self) -> None:
        w = self._w
        if w.record_state != w.STATE_READY:
            logger.warning("Cannot start recording: already recording")
            return

        if w.recorder is None:
            logger.error("Recorder not initialized")
            wx.MessageBox(tr("recorder_not_init"), tr("warning"), wx.OK | wx.ICON_WARNING)
            return

        # MP4 FFmpeg 체크
        if hasattr(w, "capture_control_bar") and w.capture_control_bar:
            fmt = w.capture_control_bar.get_format()
            if fmt == "MP4":
                from core.ffmpeg_installer import FFmpegManager
                if not FFmpegManager.is_available():
                    available = w._check_dep_for_feature(
                        "FFmpeg", "skip_ffmpeg_check",
                        tr("dep_ffmpeg_required_for_record"),
                        disable_label=tr("dep_use_gif_instead"),
                    )
                    if not available:
                        wx.CallAfter(w.capture_control_bar.set_format, "GIF")
                        return
                    elif w.encoder:
                        w.encoder.refresh_ffmpeg_path()

        # 캡처 영역
        if w.capture_overlay is None:
            logger.error("Capture overlay not initialized")
            wx.MessageBox(tr("region_not_set"), tr("warning"), wx.OK | wx.ICON_WARNING)
            return

        x, y, rw, rh = w.capture_overlay.get_capture_region()
        w.recorder.set_region(x, y, rw, rh)
        logger.info("Capture region set to: (%d, %d, %dx%d)", x, y, rw, rh)

        try:
            region = w.recorder.region
            if not region or len(region) != 4:
                raise ValueError("Invalid region format")
            x, y, rw, rh = region
            if rw <= 0 or rh <= 0:
                raise ValueError(f"Invalid region size: {rw}x{rh}")
        except (ValueError, TypeError) as e:
            logger.error("Invalid capture region: %s", e)
            wx.MessageBox("캡처 영역이 유효하지 않습니다.", tr("warning"), wx.OK | wx.ICON_WARNING)
            return

        # 컨트롤 바 설정
        if hasattr(w, "capture_control_bar") and w.capture_control_bar:
            fps = w.capture_control_bar.get_fps()
            include_cursor = w.capture_control_bar.cursor_toggle.IsChecked()
            show_click_highlight = w.capture_control_bar.region_toggle.IsChecked()
        else:
            fps, include_cursor, show_click_highlight = 15, True, False

        w.recorder.fps = fps
        w.recorder.include_cursor = include_cursor
        w.recorder.show_click_highlight = show_click_highlight

        w._memory_warned = False
        w._system_memory_warned = False
        w._zero_frame_warned = False
        w._cached_frame_size = None
        w.frames = []

        w.record_state = w.STATE_RECORDING
        w._update_button_states()

        if hasattr(w, "include_cursor_cb") and w.include_cursor_cb:
            w.include_cursor_cb.Enable(False)

        if w.capture_overlay:
            w.capture_overlay.set_recording_mode(True)
            w.capture_overlay.set_movable(False)

        wx.CallLater(50, self._do_start_recording)

    def _do_start_recording(self) -> None:
        """실제 녹화 시작."""
        w = self._w

        # 백엔드 적용
        user_backend = str(w.settings.get("capture_backend", "gdi"))
        if w.recorder:
            if user_backend == "auto":
                from core.hdr_utils import is_hdr_active
                hdr_active = is_hdr_active()
                backend = "gdi" if hdr_active else "dxcam"
                w.recorder.set_capture_backend(backend)
                logger.info("[Auto] HDR %s → %s", "ON" if hdr_active else "OFF", backend)
            elif user_backend in ("dxcam", "gdi"):
                w.recorder.set_capture_backend(user_backend)
                logger.info("[Manual] 백엔드: %s", user_backend)

        # 워터마크/키보드
        try:
            if w.recorder and w.recorder.watermark:
                enabled = w.settings.get("watermark", "false") == "true"
                w.recorder.watermark.set_enabled(enabled)
        except (AttributeError, RuntimeError) as e:
            logger.error("Watermark setup failed: %s", e)

        try:
            if w.recorder and w.recorder.keyboard_display:
                kbd = w.settings.get("keyboard_display", "false") == "true"
                if kbd and not w.recorder.keyboard_display.is_available():
                    wx.MessageBox(tr("keyboard_unavailable"), tr("warning"), wx.OK | wx.ICON_WARNING)
                    w.settings.set("keyboard_display", "false")
                    kbd = False
                w.recorder.keyboard_display.set_enabled(kbd)
        except (AttributeError, RuntimeError) as e:
            logger.error("Keyboard display setup failed: %s", e)

        try:
            w.recorder.start_recording()
            if not w.recorder.is_recording:
                raise RuntimeError("녹화 시작 실패: recorder.is_recording = False")

            backend_ready = getattr(w.recorder, "_backend_warmed_up", False)
            if backend_ready:
                w.status_msg_label.SetLabel(tr("recording"))
                logger.info("Backend pre-warmed, recording ready immediately")
            else:
                w.status_msg_label.SetLabel(tr("recording") + " - 초기화 중...")

                def _on_backend_ready():
                    if w.record_state == w.STATE_RECORDING:
                        w.status_msg_label.SetLabel(tr("recording"))
                wx.CallLater(500, _on_backend_ready)
                logger.info("Backend not pre-warmed, using 500ms delay")

            if w.record_timer is not None:
                safe_delete_timer(w.record_timer)
            w.record_timer = wx.Timer(w)
            w.record_elapsed = 0
            w.Bind(wx.EVT_TIMER, lambda e: w._update_record_time(), w.record_timer)
            w.record_timer.Start(1000)
        except Exception as e:
            self._restore_after_fail(e)

    def _restore_after_fail(self, error: Exception) -> None:
        w = self._w
        w.record_state = w.STATE_READY
        w._update_button_states()
        if hasattr(w, "include_cursor_cb") and w.include_cursor_cb:
            w.include_cursor_cb.Enable(True)
        if hasattr(w, "audio_recorder") and w.audio_recorder and w.audio_recorder.is_recording():
            w.audio_recorder.stop()
            w.audio_recorder.cleanup()
        if w.capture_overlay:
            w.capture_overlay.set_recording_mode(False)
            w.capture_overlay.set_movable(True)
        wx.MessageBox(tr("start_failed").format(str(error)), tr("error"), wx.OK | wx.ICON_ERROR)
        w.status_msg_label.SetLabel(tr("save_failed"))
        logger.warning("녹화 시작 오류: %s", error)

    # ─── 일시정지/재개 ───

    def pause_recording(self) -> None:
        w = self._w
        if w.recorder is None:
            return
        w.recorder.pause_recording()
        w.record_state = w.STATE_PAUSED
        w._update_button_states()
        if w.capture_overlay:
            w.capture_overlay.set_recording_mode(False)
            w.capture_overlay.set_movable(True, allow_resize=False)
            w.capture_overlay.Show()
            w.capture_overlay.Raise()
        w.status_msg_label.SetLabel(tr("paused"))

    def resume_recording(self) -> None:
        w = self._w
        w.record_state = w.STATE_RECORDING
        w._update_button_states()
        if w.capture_overlay:
            w.capture_overlay.set_recording_mode(True)
            w.capture_overlay.set_movable(False)
        wx.CallLater(50, self._do_resume_recording)

    def _do_resume_recording(self) -> None:
        w = self._w
        if w.recorder is None:
            return
        w.recorder.resume_recording()
        w.status_msg_label.SetLabel(tr("recording"))

    # ─── 녹화 중지 ───

    def stop_recording(self) -> None:
        w = self._w
        if w.record_state == w.STATE_READY:
            return

        if w.record_timer is not None:
            safe_delete_timer(w.record_timer)
            w.record_timer = None

        w.record_state = w.STATE_READY
        w._update_button_states()

        # 오디오
        w.audio_file_path = None
        try:
            if w.audio_recorder and w.audio_recorder.is_recording():
                w.audio_file_path = w.audio_recorder.stop()
        except (AttributeError, RuntimeError) as e:
            logger.error("Audio recording stop failed: %s", e)

        if w.recorder is not None:
            w.frames = w.recorder.stop_recording()
        else:
            w.frames = []

        if w.capture_overlay:
            w.capture_overlay.set_recording_mode(False)
            w.capture_overlay.set_movable(True, allow_resize=True)
            w.capture_overlay.Show()
            w.capture_overlay.Raise()

        frame_count = len(w.frames) if w.frames else 0
        logger.info("Recording stopped with %d frames", frame_count)

        # 성능 경고
        if frame_count > 0 and hasattr(w.recorder, "actual_fps") and w.recorder.actual_fps:
            target_fps = w.recorder.fps
            actual_fps = w.recorder.actual_fps
            if actual_fps < target_fps * 0.7:
                wx.MessageBox(
                    tr("low_fps_warning_msg").format(actual_fps=actual_fps, target_fps=target_fps),
                    tr("low_fps_warning_title"),
                    wx.OK | wx.ICON_WARNING,
                )

        if frame_count > 0:
            output_format = (
                w.capture_control_bar.get_format()
                if hasattr(w, "capture_control_bar")
                else "GIF"
            )
            if output_format == "MP4":
                w._save_gif()
            else:
                w._show_save_edit_dialog(frame_count)
        else:
            logger.warning("No frames captured during recording")
            wx.MessageBox(
                tr("no_frames") + "\n\n"
                + "녹화 시간이 너무 짧았거나 캡처 프로세스 초기화가 늦어졌을 수 있습니다.\n"
                + "최소 1초 이상 녹화를 유지해주세요.",
                tr("warning"),
                wx.OK | wx.ICON_WARNING,
            )
            w._reset_ui()
