"""
ReduceToolbar - 프레임 줄이기 인라인 툴바 (wxPython 버전)
"""
import wx
from typing import TYPE_CHECKING
from .base_toolbar_wx import InlineToolbarBase

if TYPE_CHECKING:
    from ..main_window import MainWindow


class ReduceToolbar(InlineToolbarBase):
    """프레임 줄이기 인라인 툴바 (wxPython)

    N개마다 1개만 유지하여 프레임 수를 줄입니다.
    """

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(main_window, parent)
        self._setup_controls()
        self.set_clear_button_visible(False)  # 프레임 줄이기는 Clear 버튼 불필요

    def _setup_controls(self):
        """컨트롤 설정"""
        translations = getattr(self._main_window, '_translations', None)

        # 적용 대상 프레임
        target_tooltip = translations.tr("target_tooltip") if translations else "적용 대상 프레임"
        self.add_icon_label("target", 20, target_tooltip)

        self._target_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY,
                                        choices=["모두", "선택", "현재"])
        self._target_combo.SetSelection(0)  # 기본값: "모두"
        self._target_combo.SetMinSize((70, -1))
        self._target_combo.SetToolTip(target_tooltip)
        self.add_control(self._target_combo)

        self.add_separator()

        # 줄이기 설정
        reduce_tooltip = translations.tr("reduce_keep") if translations else "N개마다 1개 유지"
        self.add_icon_label("reduce", 20, reduce_tooltip)

        self._reduce_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY,
                                        choices=["2", "3", "4", "5"])
        self._reduce_combo.SetSelection(0)  # 기본값: 2
        self._reduce_combo.SetMinSize((70, -1))
        reduce_detail_tooltip = translations.tr("reduce_tooltip") if translations else "N개마다 1개만 유지 (예: 2 = 2개 중 1개만 유지)"
        self._reduce_combo.SetToolTip(reduce_detail_tooltip)
        self.add_control(self._reduce_combo)

    def _on_apply(self, event):
        """적용 버튼 클릭"""
        if not self.frames or getattr(self.frames, 'is_empty', False):
            return

        translations = getattr(self._main_window, '_translations', None)

        # 선택된 값 가져오기
        keep_every_n = int(self._reduce_combo.GetStringSelection())
        target_index = self._target_combo.GetSelection()

        # 적용 대상 프레임 결정
        target_indices = None
        if target_index == 1:  # 선택
            selected = list(getattr(self.frames, 'selected_indices', []))
            if not selected:
                wx.MessageBox(
                    translations.tr("msg_select_frames") if translations else "적용할 프레임을 선택하세요.",
                    translations.tr("msg_warning") if translations else "경고",
                    wx.OK | wx.ICON_WARNING
                )
                return
            target_indices = selected
        elif target_index == 2:  # 현재
            # 현재 프레임만으로는 줄이기를 할 수 없음
            msg1 = translations.tr('msg_current_frame_only') if translations else '현재 프레임만으로는 줄이기를 할 수 없습니다.'
            msg2 = translations.tr('msg_use_all_or_selected') if translations else "'모두' 또는 '선택' 옵션을 사용하세요."
            wx.MessageBox(
                f"{msg1}\n{msg2}",
                translations.tr("msg_warning") if translations else "경고",
                wx.OK | wx.ICON_WARNING
            )
            return

        # Undo 등록
        old_frames = None
        if hasattr(self.frames, 'clone'):
            old_frames = self.frames.clone()
        memory_usage = old_frames.get_memory_usage() if old_frames and hasattr(old_frames, 'get_memory_usage') else 0

        def undo():
            try:
                if old_frames:
                    self.frames._frames = old_frames._frames
                    self.frames._current_index = old_frames._current_index
                    self.frames._selected_indices = old_frames._selected_indices.copy()
                    if hasattr(self._main_window, '_refresh_all'):
                        self._main_window._refresh_all()
            except Exception as e:
                wx.MessageBox(
                    f"{translations.tr('msg_frame_duplicate_undo_error') if translations else '실행 취소 실패'}:\n{str(e)}",
                    translations.tr("msg_error") if translations else "오류",
                    wx.OK | wx.ICON_ERROR
                )
                raise

        try:
            # Undo 등록
            removed_count = [0]  # 클로저를 위한 리스트 사용

            def execute_with_result():
                if hasattr(self.frames, 'reduce_frames'):
                    removed = self.frames.reduce_frames(keep_every_n, target_indices)
                    removed_count[0] = removed
                    if hasattr(self._main_window, '_refresh_all'):
                        self._main_window._refresh_all()

            if hasattr(self._main_window, 'undo_manager'):
                self._main_window.undo_manager.execute_lambda(
                    f"프레임 줄이기 ({keep_every_n}개마다 1개 유지)",
                    execute_with_result, undo, memory_usage
                )
            else:
                execute_with_result()

            # 제거된 프레임 수 가져오기
            removed = removed_count[0]
            if hasattr(self._main_window, '_is_modified'):
                self._main_window._is_modified = True
            if hasattr(self._main_window, '_refresh_all'):
                self._main_window._refresh_all()

            msg1 = translations.tr('msg_frames_reduced', removed=removed) if translations else f'{removed}개 프레임이 제거되었습니다.'
            msg2 = translations.tr('msg_frames_remaining', count=getattr(self.frames, 'frame_count', 0)) if translations else f'남은 프레임: {getattr(self.frames, "frame_count", 0)}개'
            wx.MessageBox(
                f"{msg1}\n{msg2}",
                translations.tr("msg_complete") if translations else "완료",
                wx.OK | wx.ICON_INFORMATION
            )

            # 적용 완료 후 툴바 숨김
            self.hide_from_canvas()
        except MemoryError:
            wx.MessageBox(
                translations.tr("msg_memory_error") if translations else "메모리가 부족하여 작업을 수행할 수 없습니다.",
                translations.tr("msg_warning") if translations else "경고",
                wx.OK | wx.ICON_WARNING
            )
        except Exception as e:
            err_title = translations.tr("msg_error") if translations else "오류"
            err_msg = translations.tr('msg_frame_reduce_error2') if translations else '프레임 줄이기 중 오류가 발생했습니다'
            wx.MessageBox(
                f"{err_msg}:\n{str(e)}",
                err_title,
                wx.OK | wx.ICON_ERROR
            )
