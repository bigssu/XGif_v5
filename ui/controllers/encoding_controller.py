"""인코딩 (GIF/MP4 저장) 컨트롤러."""

import logging
import os
import threading
from typing import TYPE_CHECKING

import wx

from ui.i18n import tr
from ui.theme import Colors
from ui.constants import ENCODING_STATUS_CLEAR_DELAY_MS

if TYPE_CHECKING:
    from ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class EncodingThread(threading.Thread):
    """GIF/MP4 인코딩을 위한 별도 스레드."""

    def __init__(self, encoder, frames, fps, output_path, output_format="gif",
                 audio_path=None, progress_callback=None,
                 finished_callback=None, error_callback=None):
        threading.Thread.__init__(self, daemon=True)
        self.encoder = encoder
        self.frames = frames
        self.fps = fps
        self.output_path = output_path
        self.output_format = output_format.lower()
        self.audio_path = audio_path
        self._progress_callback = progress_callback
        self._finished_callback = finished_callback
        self._error_callback = error_callback

        if self.encoder:
            self.encoder.set_progress_callback(self._on_progress)
            self.encoder.set_finished_callback(self._on_finished)
            self.encoder.set_error_callback(self._on_error)

    def _on_progress(self, current, total):
        if self._progress_callback:
            wx.CallAfter(self._progress_callback, current, total)

    def _on_finished(self, path):
        if self._finished_callback:
            wx.CallAfter(self._finished_callback, path)

    def _on_error(self, msg):
        if self._error_callback:
            wx.CallAfter(self._error_callback, msg)

    def run(self):
        try:
            if self.output_format == "mp4":
                self.encoder.encode_mp4(self.frames, self.fps, self.output_path, self.audio_path)
            else:
                self.encoder.encode(self.frames, self.fps, self.output_path)
        except Exception as e:
            if self._error_callback:
                wx.CallAfter(self._error_callback, str(e))


class EncodingController:
    """인코딩 스레드, 저장 다이얼로그, 에디터 연동 관리."""

    def __init__(self, window: "MainWindow") -> None:
        self._w = window

    def save_gif(self) -> None:
        """GIF 또는 MP4 저장 플로우 시작."""
        w = self._w

        if w.encoding_thread is not None and w.encoding_thread.is_alive():
            wx.MessageBox(tr("encoding") + "...", tr("warning"), wx.OK | wx.ICON_WARNING)
            return

        if not w.frames or len(w.frames) == 0:
            logger.error("No frames to encode")
            wx.MessageBox("인코딩할 프레임이 없습니다.", tr("warning"), wx.OK | wx.ICON_WARNING)
            w._reset_ui()
            return

        frames_snapshot = list(w.frames)

        if w.encoder is None:
            logger.error("Encoder not initialized")
            wx.MessageBox("인코더가 초기화되지 않았습니다.", tr("error"), wx.OK | wx.ICON_ERROR)
            w._reset_ui()
            return

        # 포맷
        if hasattr(w, "capture_control_bar") and w.capture_control_bar:
            output_format = w.capture_control_bar.get_format().lower()
        else:
            output_format = "gif"

        last_dir = w.settings.get("last_save_dir", "")

        if output_format == "mp4":
            file_filter = "MP4 " + tr("file") + " (*.mp4)|*.mp4"
            file_ext = ".mp4"
            dialog_title = tr("save_mp4")
        else:
            file_filter = "GIF " + tr("file") + " (*.gif)|*.gif"
            file_ext = ".gif"
            dialog_title = tr("save_gif")

        with wx.FileDialog(w, dialog_title, last_dir, "", file_filter,
                           wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                w._reset_ui()
                return
            file_path = dlg.GetPath()

        if not file_path:
            w._reset_ui()
            return

        base_path = file_path
        for ext in (".gif", ".mp4", ".GIF", ".MP4"):
            if file_path.endswith(ext):
                base_path = file_path[: -len(ext)]
                break
        file_path = base_path + file_ext

        w.settings.set("last_save_dir", os.path.dirname(file_path))

        # 품질
        if hasattr(w, "capture_control_bar") and w.capture_control_bar:
            quality = w.capture_control_bar.get_quality()
        else:
            quality = 0
        quality_map = ["high", "medium", "low"]
        w.encoder.set_quality(quality_map[quality])

        # 프로그레스 UI
        format_name = output_format.upper()
        if w.encoding_progress_bar:
            w.encoding_progress_bar.SetValue(0)
            w.encoding_progress_bar.Show()
        if w.encoding_status_label:
            w.encoding_status_label.SetLabel(tr("encoding").format(format_name))
            w.encoding_status_label.SetForegroundColour(Colors.ENCODING_PROGRESS)
        w.status_msg_label.SetLabel(tr("encoding").format(format_name))
        if getattr(w, "_progress_panel", None):
            w._progress_panel.Layout()
            w._progress_panel.Refresh()

        # FPS 결정
        if output_format == "mp4" and hasattr(w.recorder, "actual_fps") and w.recorder.actual_fps:
            fps = round(w.recorder.actual_fps)
            logger.info("[MP4] Using actual FPS: %d (target %d)", fps, w.recorder.fps)
        else:
            fps = (
                w.capture_control_bar.get_fps()
                if hasattr(w, "capture_control_bar") and w.capture_control_bar
                else 15
            )

        audio_path = w.audio_file_path if output_format == "mp4" else None

        if w.encoding_thread is not None:
            if w.encoding_thread.is_alive():
                logger.warning("Previous encoding thread still running")
            w.encoding_thread = None

        w.encoding_thread = EncodingThread(
            w.encoder, frames_snapshot, fps, file_path, output_format, audio_path,
            progress_callback=self.on_encoding_progress,
            finished_callback=self.on_encoding_finished,
            error_callback=self.on_encoding_error,
        )
        w.encoding_thread.start()

    # ─── 콜백 ───

    def on_encoding_progress(self, current: int, total: int) -> None:
        w = self._w
        try:
            percent = min(100, max(0, int((current / total) * 100))) if total > 0 else 0
        except (ZeroDivisionError, ValueError, TypeError):
            percent = 0

        if w.encoding_progress_bar:
            w.encoding_progress_bar.SetValue(percent)
        format_name = (
            w.capture_control_bar.get_format()
            if hasattr(w, "capture_control_bar") and w.capture_control_bar
            else "GIF"
        )
        if w.encoding_status_label:
            w.encoding_status_label.SetLabel(tr("encoding_percent").format(format_name, percent))
        w.status_msg_label.SetLabel(tr("encoding_percent").format(format_name, percent))
        if getattr(w, "_progress_panel", None):
            w._progress_panel.Refresh()

    def on_encoding_finished(self, output_path: str) -> None:
        w = self._w
        try:
            w.frames = []
            if w.recorder:
                w.recorder.clear_frames()
            if hasattr(w, "audio_recorder") and w.audio_recorder:
                w.audio_recorder.cleanup()
            w.audio_file_path = None

            # 파일 크기
            file_size_str = ""
            try:
                if os.path.exists(output_path):
                    sz = os.path.getsize(output_path)
                    if sz < 1024:
                        file_size_str = f" ({sz} B)"
                    elif sz < 1024 * 1024:
                        file_size_str = f" ({sz / 1024:.1f} KB)"
                    else:
                        file_size_str = f" ({sz / (1024 * 1024):.1f} MB)"
            except Exception:
                pass

            if w.encoding_progress_bar:
                w.encoding_progress_bar.SetValue(100)
                bar = w.encoding_progress_bar

                def _hide():
                    try:
                        if bar:
                            bar.Hide()
                    except (RuntimeError, AttributeError):
                        pass
                wx.CallLater(300, _hide)

            if w.encoding_status_label:
                w.encoding_status_label.SetLabel("✓ " + tr("save_complete") + file_size_str)
                w.encoding_status_label.SetForegroundColour(Colors.ENCODING_COMPLETE)
            if getattr(w, "_progress_panel", None):
                w._progress_panel.Layout()
                w._progress_panel.Refresh()

            filename = os.path.basename(output_path)
            w.status_msg_label.SetLabel(tr("saved_to").format(filename) + file_size_str)

            wx.CallLater(ENCODING_STATUS_CLEAR_DELAY_MS, self._clear_encoding_status)

            try:
                folder = os.path.dirname(output_path)
                if folder and os.path.exists(folder) and os.path.isdir(folder):
                    try:
                        os.startfile(folder)
                    except (OSError, AttributeError) as e:
                        logger.warning("폴더 열기 실패: %s", e)
                        wx.MessageBox(
                            tr("saved_to_path").format(output_path),
                            tr("save_complete"),
                            wx.OK | wx.ICON_INFORMATION,
                        )
            except (OSError, ValueError) as e:
                logger.error("Path processing error: %s", e)

            w._reset_ui()
        except Exception as e:
            logger.warning("인코딩 완료 후처리 중 에러: %s", e)
            w._reset_ui()

    def on_encoding_error(self, error_msg: str) -> None:
        w = self._w
        w.frames = []
        if w.recorder:
            w.recorder.clear_frames()

        if w.encoding_progress_bar:
            w.encoding_progress_bar.SetValue(0)
            w.encoding_progress_bar.Hide()
        if w.encoding_status_label:
            w.encoding_status_label.SetLabel("✗ " + tr("encoding_failed"))
            w.encoding_status_label.SetForegroundColour(Colors.ENCODING_ERROR)
        if getattr(w, "_progress_panel", None):
            w._progress_panel.Layout()
            w._progress_panel.Refresh()

        wx.MessageBox(tr("encoding_failed") + f":\n{error_msg}", tr("error"),
                      wx.OK | wx.ICON_ERROR)
        wx.CallLater(ENCODING_STATUS_CLEAR_DELAY_MS, self._clear_encoding_status)
        w._reset_ui()

    def _clear_encoding_status(self) -> None:
        w = self._w
        w.status_msg_label.SetLabel(tr("ready"))
        if w.encoding_status_label:
            w.encoding_status_label.SetLabel("")

    # ─── 에디터 연동 ───

    def open_editor_with_frames(self) -> None:
        """녹화된 프레임으로 GifEditor 열기."""
        from PIL import Image
        import tempfile

        w = self._w
        try:
            w.status_msg_label.SetLabel(tr("opening_editor"))

            try:
                fps = (
                    w.capture_control_bar.get_fps()
                    if hasattr(w, "capture_control_bar") and w.capture_control_bar
                    else 15
                )
            except (ValueError, TypeError):
                fps = 15

            delay_ms = int(1000 / fps)
            frame_count = len(w.frames) if w.frames else 0
            if frame_count == 0:
                wx.MessageBox(tr("no_frames"), tr("warning"), wx.OK | wx.ICON_WARNING)
                w._reset_ui()
                return

            pil_frames = []
            for i, np_frame in enumerate(w.frames):
                if np_frame is None or np_frame.size == 0:
                    continue
                if len(np_frame.shape) == 3 and np_frame.shape[2] == 3:
                    pil_frames.append(Image.fromarray(np_frame[:, :, ::-1], "RGB"))
                elif len(np_frame.shape) == 3 and np_frame.shape[2] == 4:
                    pil_frames.append(
                        Image.fromarray(np_frame[:, :, [2, 1, 0, 3]], "RGBA").convert("RGB")
                    )

            if not pil_frames:
                wx.MessageBox(tr("no_frames"), tr("warning"), wx.OK | wx.ICON_WARNING)
                w._reset_ui()
                return

            temp_path = os.path.join(tempfile.gettempdir(), "xgif_temp_edit.gif")
            pil_frames[0].save(
                temp_path, save_all=True, append_images=pil_frames[1:],
                duration=delay_ms, loop=0,
            )
            logger.info("Temp GIF saved to: %s", temp_path)

            w.frames = []
            if w.recorder:
                w.recorder.clear_frames()

            try:
                from editor.ui.editor_main_window_wx import MainWindow as EditorMainWindow
                editor_window = EditorMainWindow()
                editor_window.open_file(temp_path)
                editor_window.Show()
                logger.info("Editor launched with %d frames", frame_count)
                w._editor_mode = True
                w.Close()
                return
            except Exception as e:
                logger.error("Failed to launch editor: %s", e)
                wx.MessageBox(
                    f"편집기 실행에 실패했습니다.\n\n임시 파일 위치:\n{temp_path}",
                    tr("error"),
                    wx.OK | wx.ICON_ERROR,
                )
                self.save_gif()
        except Exception as e:
            logger.error("Editor open failed: %s", e)
            wx.MessageBox(str(e), tr("error"), wx.OK | wx.ICON_ERROR)
            self.save_gif()
