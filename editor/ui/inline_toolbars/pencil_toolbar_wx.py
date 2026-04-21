"""
PencilToolbar - 펜슬 그리기 인라인 툴바 (wxPython 버전)

캔버스에 자유 그리기 기능을 제공하며, Auto Animation 모드를 지원합니다.
"""
import wx
from .base_toolbar_wx import InlineToolbarBase
from ..style_constants_wx import Colors


class PencilToolbar(InlineToolbarBase):
    """펜슬 그리기 인라인 툴바"""

    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)

        self._pencil_color = wx.Colour(255, 0, 0)
        self._pencil_width = 10
        self._pencil_duration = 1.0
        self._pencil_start_index = 0
        self._pencil_auto_animation = True
        self._pencil_target_mode = 1  # 0: 모두, 1: 선택, 2: 현재

        self._setup_pencil_ui()

    def _setup_pencil_ui(self):
        """펜슬 도구 UI 생성"""
        # 적용 대상
        target_label = wx.StaticText(self._controls_widget, label="대상:")
        target_label.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._controls_sizer.Add(target_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        self._target_combo = wx.ComboBox(
            self._controls_widget,
            style=wx.CB_READONLY,
            choices=["모두", "선택", "현재"]
        )
        self._target_combo.SetBackgroundColour(Colors.BG_TERTIARY)
        self._target_combo.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._target_combo.SetSelection(self._pencil_target_mode)
        self._target_combo.Bind(wx.EVT_COMBOBOX, self._on_target_changed)
        self._controls_sizer.Add(self._target_combo, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)

        self.add_separator()

        # 색상 버튼
        self._color_btn = wx.Button(self._controls_widget, size=(52, 52))
        self._color_btn.Bind(wx.EVT_BUTTON, lambda e: self._select_color())
        self._update_color_icon()
        self._controls_sizer.Add(self._color_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        # 두께 슬라이더
        self._width_slider = wx.Slider(
            self._controls_widget,
            value=self._pencil_width,
            minValue=1,
            maxValue=20,
            style=wx.SL_HORIZONTAL,
            size=(120, -1)
        )
        self._width_slider.SetBackgroundColour(self.TOOLBAR_BG_COLOR)
        self._width_slider.Bind(wx.EVT_SLIDER, self._on_width_changed)
        self._controls_sizer.Add(self._width_slider, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        self._width_label = wx.StaticText(self._controls_widget, label=f"{self._pencil_width}px")
        self._width_label.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._controls_sizer.Add(self._width_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)

        # 지속 시간
        duration_label = wx.StaticText(self._controls_widget, label="시간:")
        duration_label.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._controls_sizer.Add(duration_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        self._duration_spin = wx.SpinCtrlDouble(
            self._controls_widget,
            min=0.1,
            max=30.0,
            inc=0.1,
            size=(80, -1)
        )
        self._duration_spin.SetBackgroundColour(Colors.BG_TERTIARY)
        self._duration_spin.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._duration_spin.SetValue(self._pencil_duration)
        self._duration_spin.SetDigits(1)
        self._duration_spin.Bind(wx.EVT_SPINCTRLDOUBLE, self._on_duration_changed)
        self._controls_sizer.Add(self._duration_spin, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)

        self.add_separator()

        # Auto Animation 토글
        self._auto_anim_btn = wx.ToggleButton(self._controls_widget, label="Auto", size=(70, 36))
        self._auto_anim_btn.SetBackgroundColour(Colors.BG_TERTIARY)
        self._auto_anim_btn.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._auto_anim_btn.SetValue(self._pencil_auto_animation)
        self._auto_anim_btn.Bind(wx.EVT_TOGGLEBUTTON, self._on_auto_anim_toggled)
        self._controls_sizer.Add(self._auto_anim_btn, 0, wx.ALIGN_CENTER_VERTICAL)

    # === 활성화 / 비활성화 ===

    def _on_activated(self):
        """펜슬 도구 활성화"""
        self._pencil_start_index = self.frames.current_index if self.frames else 0
        self._target_combo.SetSelection(self._pencil_target_mode)
        self._update_color_icon()

        canvas = self._safe_get_canvas()
        if canvas and hasattr(canvas, 'start_drawing_mode'):
            canvas.start_drawing_mode(self._pencil_color, self._pencil_width)

        self._update_preview_range()

    def _on_deactivated(self):
        """펜슬 도구 비활성화"""
        canvas = self._safe_get_canvas()
        if canvas:
            if hasattr(canvas, 'stop_drawing_mode'):
                canvas.stop_drawing_mode()
            if hasattr(canvas, 'set_pencil_preview_range'):
                canvas.set_pencil_preview_range(0, 0)

    # === 적용 / 취소 / 지우기 ===

    def _on_apply(self, event):
        """그린 선을 프레임들에 적용"""
        try:
            canvas = self._safe_get_canvas()
            if not canvas or not hasattr(canvas, 'get_drawing_paths'):
                wx.MessageBox("캔버스가 초기화되지 않았습니다.", "경고", wx.OK | wx.ICON_WARNING)
                return

            paths = canvas.get_drawing_paths()
            if not paths:
                wx.MessageBox("그려진 선이 없습니다.", "경고", wx.OK | wx.ICON_WARNING)
                return

            target_indices = self._get_target_indices()
            if not target_indices:
                wx.MessageBox("적용할 프레임이 없습니다.", "경고", wx.OK | wx.ICON_WARNING)
                return

            # Auto Animation 모드
            if self._pencil_auto_animation and len(target_indices) >= 2:
                self._apply_auto_animation(paths, target_indices)
            else:
                self._apply_normal(paths, target_indices)

            self._main_window._is_modified = True
            super()._on_apply(event)

        except Exception as e:
            from ...utils.logger import get_logger
            get_logger().error(f"펜슬 선 적용 오류: {e}", exc_info=True)
            wx.MessageBox(f"펜슬 선을 적용하는 중 오류가 발생했습니다:\n{str(e)}", "오류", wx.OK | wx.ICON_ERROR)

    def _on_cancel(self, event):
        """펜슬 모드 취소"""
        super()._on_cancel(event)

    def _on_clear(self, event):
        """그린 선 지우기"""
        try:
            canvas = self._safe_get_canvas()
            if canvas and hasattr(canvas, 'clear_drawings'):
                canvas.clear_drawings()
        except Exception as e:
            from ...utils.logger import get_logger
            get_logger().error(f"그린 선 지우기 오류: {e}", exc_info=True)

    # === 내부 로직 ===

    def _get_target_indices(self):
        """적용할 프레임 인덱스 목록"""
        if not self.frames or self.frames.is_empty:
            return []

        if self._pencil_target_mode == 0:  # 모두
            return list(range(self.frames.frame_count))
        elif self._pencil_target_mode == 1:  # 선택
            target = sorted(self.frames.selected_indices)
            if not target:
                start = self._pencil_start_index
                return list(range(start, min(start + 1, self.frames.frame_count)))
            return target
        else:  # 현재
            return [self.frames.current_index]

    def _apply_normal(self, paths, target_indices):
        """일반 모드: 모든 대상 프레임에 동일한 선 적용"""
        applied_count = 0
        for i in target_indices:
            if 0 <= i < self.frames.frame_count:
                frame = self.frames[i]
                if frame and hasattr(frame, 'draw_lines'):
                    try:
                        frame.draw_lines(paths)
                        applied_count += 1
                    except Exception as e:
                        from ...utils.logger import get_logger
                        get_logger().error(f"프레임 {i}에 선 적용 오류: {e}", exc_info=True)

    def _apply_auto_animation(self, paths, target_indices):
        """Auto Animation: 선택된 프레임에 걸쳐 선이 점진적으로 그려지는 효과"""
        selected = sorted(target_indices)
        num_frames = len(selected)

        total_points = sum(len(pp) for pp, _, _ in paths)
        if total_points == 0:
            return

        for frame_idx, target_frame_idx in enumerate(selected):
            if 0 <= target_frame_idx < self.frames.frame_count:
                frame = self.frames[target_frame_idx]
                if frame and hasattr(frame, 'draw_lines'):
                    progress = (frame_idx + 1) / num_frames
                    partial_paths = []
                    points_to_show = int(total_points * progress)
                    points_shown = 0

                    for path_points, color, width in paths:
                        path_len = len(path_points)
                        if points_shown + path_len <= points_to_show:
                            partial_paths.append((path_points, color, width))
                            points_shown += path_len
                        elif points_shown < points_to_show:
                            remaining = points_to_show - points_shown
                            partial_paths.append((path_points[:remaining], color, width))
                            points_shown += remaining
                        else:
                            break

                    try:
                        frame.draw_lines(partial_paths)
                    except Exception as e:
                        from ...utils.logger import get_logger
                        get_logger().error(f"프레임 {target_frame_idx}에 Auto Animation 적용 오류: {e}", exc_info=True)

    # === UI 이벤트 핸들러 ===

    def _update_color_icon(self):
        """펜 색상 버튼 아이콘 업데이트"""
        if not hasattr(self, '_color_btn'):
            return
        self._color_btn.SetBackgroundColour(self._pencil_color)
        self._color_btn.SetLabel(f"{self._pencil_width}px")
        self._color_btn.Refresh()

    def _select_color(self):
        """펜 색상 선택"""
        try:
            data = wx.ColourData()
            data.SetColour(self._pencil_color)
            dlg = wx.ColourDialog(self, data)
            if dlg.ShowModal() == wx.ID_OK:
                self._pencil_color = dlg.GetColourData().GetColour()
                self._update_color_icon()
                canvas = self._safe_get_canvas()
                if canvas and hasattr(canvas, 'update_pencil_settings'):
                    canvas.update_pencil_settings(self._pencil_color, self._pencil_width)
            dlg.Destroy()
        except Exception as e:
            from ...utils.logger import get_logger
            get_logger().error(f"펜 색상 선택 오류: {e}", exc_info=True)

    def _on_width_changed(self, event):
        """펜 두께 변경"""
        try:
            value = self._width_slider.GetValue()
            self._pencil_width = value
            self._width_label.SetLabel(f"{value}px")
            self._update_color_icon()
            canvas = self._safe_get_canvas()
            if canvas and hasattr(canvas, 'update_pencil_settings'):
                canvas.update_pencil_settings(self._pencil_color, self._pencil_width)
        except Exception as e:
            from ...utils.logger import get_logger
            get_logger().error(f"펜 두께 변경 오류: {e}", exc_info=True)

    def _on_duration_changed(self, event):
        """지속 시간 변경"""
        self._pencil_duration = self._duration_spin.GetValue()
        self._update_preview_range()

    def _on_auto_anim_toggled(self, event):
        """Auto Animation 토글"""
        self._pencil_auto_animation = self._auto_anim_btn.GetValue()
        self._update_preview_range()

    def _on_target_changed(self, event):
        """적용 대상 변경"""
        self._pencil_target_mode = self._target_combo.GetSelection()
        self._update_preview_range()

    def _update_preview_range(self):
        """펜슬 프리뷰 범위 업데이트"""
        try:
            if not self.frames or self.frames.is_empty:
                return
            canvas = self._safe_get_canvas()
            if not canvas or not hasattr(canvas, 'set_pencil_preview_range'):
                return

            target_mode = self._pencil_target_mode

            if self._pencil_auto_animation:
                if target_mode == 0:  # 모두
                    frame_count = self.frames.frame_count
                    if frame_count > 0:
                        target_frames = list(range(frame_count))
                        canvas.set_pencil_preview_range(
                            0, len(target_frames),
                            auto_animation=True, target_frames=target_frames)
                elif target_mode == 1:  # 선택
                    selected_indices = self.frames.selected_indices
                    if selected_indices and len(selected_indices) >= 2:
                        target_frames = sorted(selected_indices)
                        canvas.set_pencil_preview_range(
                            target_frames[0], len(target_frames),
                            auto_animation=True, target_frames=target_frames)
                    else:
                        fc = 2
                        target_frames = list(range(
                            self._pencil_start_index,
                            min(self._pencil_start_index + fc, self.frames.frame_count)))
                        if target_frames:
                            canvas.set_pencil_preview_range(
                                self._pencil_start_index, len(target_frames),
                                auto_animation=True, target_frames=target_frames)
                else:  # 현재
                    current_idx = self.frames.current_index
                    if 0 <= current_idx < self.frames.frame_count:
                        canvas.set_pencil_preview_range(
                            current_idx, 1,
                            auto_animation=False, target_frames=[current_idx])
            else:
                if target_mode == 0:
                    if self.frames.frame_count > 0:
                        canvas.set_pencil_preview_range(0, self.frames.frame_count)
                elif target_mode == 1:
                    selected_indices = self.frames.selected_indices
                    if selected_indices:
                        start_idx = min(selected_indices)
                        end_idx = max(selected_indices) + 1
                        canvas.set_pencil_preview_range(start_idx, end_idx - start_idx)
                    else:
                        canvas.set_pencil_preview_range(self._pencil_start_index, 1)
                else:
                    current_idx = self.frames.current_index
                    if 0 <= current_idx < self.frames.frame_count:
                        canvas.set_pencil_preview_range(current_idx, 1)

        except Exception as e:
            from ...utils.logger import get_logger
            get_logger().error(f"펜슬 프리뷰 범위 업데이트 오류: {e}", exc_info=True)

    def update_texts(self, translations):
        """텍스트 업데이트"""
        pass
