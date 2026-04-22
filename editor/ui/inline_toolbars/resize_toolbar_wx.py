"""
ResizeToolbar - 크기 조절 인라인 툴바 (wxPython 버전)
"""
import wx
from PIL import Image
from typing import TYPE_CHECKING, Tuple, List, Optional
from ..style_constants_wx import Colors
from .base_toolbar_wx import InlineToolbarBase

if TYPE_CHECKING:
    from ..main_window import MainWindow


class ResizeToolbar(InlineToolbarBase):
    """크기 조절 인라인 툴바 (wxPython)

    너비/높이 스핀박스와 비율 유지 체크박스, 프리셋 버튼을 제공합니다.
    """

    # 리샘플링 방법
    RESAMPLE_METHODS = {
        "Nearest": Image.Resampling.NEAREST,
        "Bilinear": Image.Resampling.BILINEAR,
        "Bicubic": Image.Resampling.BICUBIC,
        "Lanczos": Image.Resampling.LANCZOS,
    }

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(main_window, parent)
        self._original_width = 0
        self._original_height = 0
        self._aspect_ratio = 1.0
        self._updating = False
        self._original_images: List[Optional[Image.Image]] = []
        self._setup_controls()

    def _setup_controls(self):
        """컨트롤 설정"""
        translations = getattr(self._main_window, '_translations', None)

        # 크기 설정
        width_height_tooltip = translations.tr("resize_width_height") if translations else "너비, 높이"
        self.add_icon_label("resize", 20, width_height_tooltip)

        self._width_spin = wx.SpinCtrl(self._controls_widget, min=1, max=10000, initial=100)
        self._width_spin.SetMinSize((80, -1))
        width_tooltip = translations.tr("resize_width") if translations else "너비"
        self._width_spin.SetToolTip(width_tooltip)
        self._width_spin.Bind(wx.EVT_SPINCTRL, self._on_width_changed)
        self.add_control(self._width_spin)

        self._height_spin = wx.SpinCtrl(self._controls_widget, min=1, max=10000, initial=100)
        self._height_spin.SetMinSize((80, -1))
        height_tooltip = translations.tr("resize_height") if translations else "높이"
        self._height_spin.SetToolTip(height_tooltip)
        self._height_spin.Bind(wx.EVT_SPINCTRL, self._on_height_changed)
        self.add_control(self._height_spin)

        # 비율 유지 체크박스
        self._keep_ratio_check = wx.CheckBox(self._controls_widget, label="비율 유지")
        self._keep_ratio_check.SetValue(True)
        keep_ratio_tooltip = translations.tr("resize_keep_ratio") if translations else "비율 유지"
        self._keep_ratio_check.SetToolTip(keep_ratio_tooltip)
        self._keep_ratio_check.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.add_control(self._keep_ratio_check)

        self.add_separator()

        # 프리셋
        self._preset_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY,
                                        choices=["50%", "75%", "100%", "150%", "200%"])
        self._preset_combo.SetSelection(2)  # 기본값 100%
        self._preset_combo.SetMinSize((80, -1))
        preset_tooltip = translations.tr("resize_preset") if translations else "크기 프리셋"
        self._preset_combo.SetToolTip(preset_tooltip)
        self._preset_combo.Bind(wx.EVT_COMBOBOX, self._on_preset_changed)
        self.add_control(self._preset_combo)

        self.add_separator()

        # 필터 설정
        filter_tooltip = translations.tr("resize_filter") if translations else "리샘플링 필터"
        self.add_icon_label("effects", 20, filter_tooltip)

        self._method_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY,
                                        choices=list(self.RESAMPLE_METHODS.keys()))
        self._method_combo.SetSelection(2)  # Bicubic 기본
        self._method_combo.SetMinSize((90, -1))
        self._method_combo.SetToolTip(filter_tooltip)
        self.add_control(self._method_combo)


    def _on_activated(self):
        """툴바 활성화"""
        frames = self.frames
        if not frames or getattr(frames, 'is_empty', False):
            return

        self._original_images = self._snapshot_original_images()

        try:
            self._original_width = getattr(frames, 'width', 1)
            self._original_height = getattr(frames, 'height', 1)
            self._aspect_ratio = self._original_width / self._original_height if self._original_height > 0 else 1.0
        except Exception:
            self._original_width = 1
            self._original_height = 1
            self._aspect_ratio = 1.0

        self._updating = True
        self._width_spin.SetValue(self._original_width)
        self._height_spin.SetValue(self._original_height)
        self._updating = False

    def _on_deactivated(self):
        """툴바 비활성화"""
        self._clear_original_images()

    def _on_width_changed(self, event):
        """너비 변경"""
        if self._updating:
            return

        if self._keep_ratio_check.GetValue():
            self._updating = True
            value = self._width_spin.GetValue()
            if self._aspect_ratio > 0:
                new_height = int(value / self._aspect_ratio)
                self._height_spin.SetValue(max(1, new_height))
            self._updating = False

        self._preview_timer.Start(150, wx.TIMER_ONE_SHOT)

    def _on_height_changed(self, event):
        """높이 변경"""
        if self._updating:
            return

        if self._keep_ratio_check.GetValue():
            self._updating = True
            value = self._height_spin.GetValue()
            new_width = int(value * self._aspect_ratio) if self._aspect_ratio > 0 else value
            self._width_spin.SetValue(max(1, new_width))
            self._updating = False

        self._preview_timer.Start(150, wx.TIMER_ONE_SHOT)

    def _on_preset_changed(self, event):
        """프리셋 드롭다운 변경"""
        scales = [0.5, 0.75, 1.0, 1.5, 2.0]
        index = self._preset_combo.GetSelection()
        if 0 <= index < len(scales):
            scale = scales[index]
            self._apply_preset(scale)

    def _apply_preset(self, scale: float):
        """프리셋 적용"""
        self._updating = True
        self._width_spin.SetValue(int(self._original_width * scale))
        self._height_spin.SetValue(int(self._original_height * scale))
        self._updating = False
        self._preview_timer.Start(50, wx.TIMER_ONE_SHOT)

    def _update_preview(self):
        """실시간 프리뷰 업데이트"""
        if not self._original_images:
            return

        new_width = self._width_spin.GetValue()
        new_height = self._height_spin.GetValue()
        resample = self.get_resample_method()

        # 크기가 변경되지 않으면 원본으로 복원
        if new_width == self._original_width and new_height == self._original_height:
            self._restore_original_images_with_size()
        else:
            self._apply_resized_images(new_width, new_height, resample)

        self._safe_canvas_update()
        self.update_preview()

    def _on_clear(self, event):
        """초기화 - 원본 크기로"""
        self._updating = True
        self._width_spin.SetValue(self._original_width)
        self._height_spin.SetValue(self._original_height)
        self._updating = False

        self._restore_original_images_with_size()
        self._safe_canvas_update()

    def _on_apply(self, event):
        """적용"""
        new_width = self._width_spin.GetValue()
        new_height = self._height_spin.GetValue()
        resample = self.get_resample_method()

        # 크기가 변경되지 않으면 원본 복원 후 종료
        if new_width == self._original_width and new_height == self._original_height:
            self._restore_original_images_with_size()
            self._finish_apply()
            return

        self._apply_resized_images(new_width, new_height, resample)
        self._finish_apply()

    def _on_cancel(self, event):
        """취소 - 원본으로 복원"""
        self._restore_original_images_with_size()
        self._finish_cancel()

    def get_new_size(self) -> Tuple[int, int]:
        """새 크기 반환"""
        return (self._width_spin.GetValue(), self._height_spin.GetValue())

    def get_resample_method(self) -> Image.Resampling:
        """리샘플링 방법 반환"""
        method_name = self._method_combo.GetStringSelection()
        return self.RESAMPLE_METHODS.get(method_name, Image.Resampling.BICUBIC)

    def reset_to_default(self):
        """기본값으로 초기화"""
        self._on_clear(None)

    def _restore_original_images_with_size(self):
        for i, frame in enumerate(self.frames):
            if i < len(self._original_images) and self._original_images[i] is not None:
                try:
                    frame._image = self._original_images[i].copy()
                    if hasattr(frame, '_image_size'):
                        frame._image_size = self._original_images[i].size
                except Exception:
                    pass

    def _apply_resized_images(self, width: int, height: int, resample: Image.Resampling):
        for i, frame in enumerate(self.frames):
            if i < len(self._original_images) and self._original_images[i] is not None:
                try:
                    resized = self._original_images[i].resize((width, height), resample)
                    frame._image = resized
                    if hasattr(frame, '_image_size'):
                        frame._image_size = resized.size
                except Exception:
                    pass
