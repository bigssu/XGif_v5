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

    _has_clear_button = False

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(main_window, parent)
        self._setup_controls()

    def _setup_controls(self):
        """컨트롤 설정"""
        translations = getattr(self._main_window, '_translations', None)

        # 적용 대상 프레임
        target_tooltip = translations.tr("target_tooltip") if translations else "적용 대상 프레임"
        self.add_icon_label("target", 20, target_tooltip)

        self._target_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY,
                                        choices=[
                                            translations.tr("target_all_short") if translations else "모두",
                                            translations.tr("target_selected_short") if translations else "선택",
                                            translations.tr("target_current_short") if translations else "현재",
                                        ])
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
        """적용 버튼 클릭 — 메인 윈도우의 표준 ProgressDialog helper 위임."""
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

        before_count = getattr(self.frames, 'frame_count', 0)
        removed_box = {'count': 0}

        def _work(progress):
            removed = self.frames.reduce_frames(
                keep_every_n, target_indices,
                progress_callback=lambda c, t: progress(
                    c, t,
                    translations.tr("prog_general_msg_detail", current=c, total=t)
                    if translations else f"{c}/{t}",
                ),
            )
            removed_box['count'] = removed if removed is not None else 0

        # 메인 윈도우의 표준 helper 위임 — 이전엔 execute_lambda 동기 호출이 700→350
        # 케이스에서 6~8초 UI 블록을 유발했다. helper 는 background thread +
        # ProgressDialog 표시 + 100MB+ undo 가드 + push_executed history 등록까지
        # 모두 처리.
        runner = getattr(self._main_window, '_run_undoable_with_progress', None)
        if runner is None:
            # 폴백 — 메인이 helper 미보유 환경 (예: 단위 테스트)
            self.frames.reduce_frames(keep_every_n, target_indices)
            removed_box['count'] = before_count - getattr(self.frames, 'frame_count', before_count)
            if hasattr(self._main_window, '_refresh_all'):
                self._main_window._refresh_all()
        else:
            runner(
                title_key="prog_reduce_title",
                description=f"프레임 줄이기 ({keep_every_n}개마다 1개 유지)",
                work_fn=_work,
                no_undo_msg_key="msg_reduce_no_undo",
                error_key="msg_frame_reduce_error",
            )

        if hasattr(self._main_window, '_is_modified'):
            self._main_window._is_modified = True

        removed = removed_box['count']
        msg1 = translations.tr('msg_frames_reduced', removed=removed) if translations else f'{removed}개 프레임이 제거되었습니다.'
        msg2 = translations.tr('msg_frames_remaining', count=getattr(self.frames, 'frame_count', 0)) if translations else f'남은 프레임: {getattr(self.frames, "frame_count", 0)}개'
        wx.MessageBox(
            f"{msg1}\n{msg2}",
            translations.tr("msg_complete") if translations else "완료",
            wx.OK | wx.ICON_INFORMATION,
        )

        # 적용 완료 후 이벤트 발생 (툴바 닫힘)
        super()._on_apply(event)
