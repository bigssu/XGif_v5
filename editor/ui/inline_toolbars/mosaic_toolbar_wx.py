"""
MosaicToolbar - 모자이크/검열 효과 인라인 툴바 (wxPython 버전)
"""
import wx
from PIL import Image
from typing import TYPE_CHECKING, Optional, List
from .base_toolbar_wx import InlineToolbarBase
from ...core.image_effects import ImageEffects

if TYPE_CHECKING:
    from ..main_window import MainWindow


class MosaicToolbar(InlineToolbarBase):
    """모자이크/검열 효과 인라인 툴바 (wxPython)

    마우스로 영역을 선택하여 모자이크, 블러, 검정 바를 적용합니다.
    """

    # 검열 타입
    CENSOR_TYPES = [
        ("모자이크", "mosaic"),
        ("블러", "blur"),
        ("검정 바", "black_bar"),
    ]

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(main_window, parent)
        self._original_images: List[Optional[Image.Image]] = []
        self._bar_color = wx.Colour(0, 0, 0)
        self._region_x1 = 50
        self._region_y1 = 50
        self._region_x2 = 150
        self._region_y2 = 100
        self._updating_from_canvas = False
        self._setup_controls()
        self.set_clear_button_visible(True)

    def _setup_controls(self):
        """컨트롤 설정"""
        translations = getattr(self._main_window, '_translations', None)

        # 적용 대상
        target_tooltip = translations.tr("target_tooltip") if translations else "적용 대상 프레임"
        self.add_icon_label("target", 20, target_tooltip)

        self._target_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY,
                                        choices=["모두", "선택", "현재"])
        self._target_combo.SetSelection(1)  # 기본값: "선택"
        self._target_combo.SetMinSize((70, -1))
        self._target_combo.SetToolTip(target_tooltip)
        self._target_combo.Bind(wx.EVT_COMBOBOX, self._on_setting_changed)
        self.add_control(self._target_combo)

        self.add_separator()

        # 타입 설정
        type_tooltip = translations.tr("mosaic_type") if translations else "모자이크/블러 타입"
        self.add_icon_label("effects", 20, type_tooltip)

        self._type_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY,
                                      choices=[name for name, _ in self.CENSOR_TYPES])
        self._type_combo.SetSelection(0)
        self._type_combo.SetMinSize((90, -1))
        self._type_combo.SetToolTip(type_tooltip)
        self._type_combo.Bind(wx.EVT_COMBOBOX, self._on_type_changed)
        self.add_control(self._type_combo)

        # 강도 설정
        strength_tooltip = translations.tr("mosaic_strength") if translations else "블록 크기/강도"
        self.add_icon_label("width", 20, strength_tooltip)

        self._strength_spin = wx.SpinCtrl(self._controls_widget, min=2, max=50, initial=10)
        self._strength_spin.SetMinSize((70, -1))
        self._strength_spin.SetToolTip(strength_tooltip)
        self._strength_spin.Bind(wx.EVT_SPINCTRL, self._on_setting_changed)
        self.add_control(self._strength_spin)

        # 색상 버튼 (검정 바용)
        self._color_btn = wx.ColourPickerCtrl(self._controls_widget, colour=self._bar_color)
        self._color_btn.SetMinSize((40, 30))
        color_tooltip = translations.tr("mosaic_color") if translations else "검열 바 색상"
        self._color_btn.SetToolTip(color_tooltip)
        self._color_btn.Bind(wx.EVT_COLOURPICKER_CHANGED, self._on_color_changed)
        self._color_btn.Hide()  # 기본적으로 숨김
        self.add_control(self._color_btn)

    def _on_activated(self):
        """툴바 활성화"""
        if not self.frames or getattr(self.frames, 'is_empty', False):
            return

        # 원본 이미지 저장
        self._original_images = []
        try:
            for f in self.frames:
                if f and hasattr(f, 'image') and f.image:
                    self._original_images.append(f.image.copy())
                else:
                    self._original_images.append(None)
        except Exception:
            self._original_images = []

        # 기본 영역 설정
        w = getattr(self.frames, 'width', 100)
        h = getattr(self.frames, 'height', 100)
        self._region_x1 = w // 4
        self._region_y1 = h // 4
        self._region_x2 = w * 3 // 4
        self._region_y2 = h * 3 // 4

        # 캔버스 모자이크 모드 시작
        canvas = self._safe_get_canvas()
        if canvas:
            try:
                if hasattr(canvas, 'mosaic_region_changed'):
                    canvas.mosaic_region_changed.connect(self._on_canvas_region_changed)
                if hasattr(canvas, 'start_mosaic_mode'):
                    canvas.start_mosaic_mode(
                        self._region_x1, self._region_y1,
                        self._region_x2, self._region_y2
                    )
            except Exception:
                pass

        self._update_preview()

    def _on_deactivated(self):
        """툴바 비활성화"""
        self._original_images = []  # 메모리 해제
        self._preview_timer.Stop()

        canvas = self._safe_get_canvas()
        if canvas:
            try:
                if hasattr(canvas, 'mosaic_region_changed'):
                    canvas.mosaic_region_changed.disconnect(self._on_canvas_region_changed)
            except Exception:
                pass
            try:
                if hasattr(canvas, 'stop_mosaic_mode'):
                    canvas.stop_mosaic_mode()
            except Exception:
                pass

    def _on_type_changed(self, event):
        """검열 타입 변경"""
        index = self._type_combo.GetSelection()
        if 0 <= index < len(self.CENSOR_TYPES):
            censor_type = self.CENSOR_TYPES[index][1]
            # 검정 바일 때만 색상 버튼 표시
            if censor_type == "black_bar":
                self._color_btn.Show()
            else:
                self._color_btn.Hide()
            # 강도 컨트롤 활성화/비활성화
            self._strength_spin.Enable(censor_type != "black_bar")
            self._controls_sizer.Layout()

        self._preview_timer.Start(50, wx.TIMER_ONE_SHOT)

    def _on_setting_changed(self, event):
        """설정 변경됨"""
        self._preview_timer.Start(100, wx.TIMER_ONE_SHOT)

    def _on_color_changed(self, event):
        """색상 변경"""
        self._bar_color = event.GetColour()
        self._on_setting_changed(event)

    def _on_canvas_region_changed(self, x1: int, y1: int, x2: int, y2: int):
        """캔버스에서 영역이 변경됨"""
        self._updating_from_canvas = True
        self._region_x1 = x1
        self._region_y1 = y1
        self._region_x2 = x2
        self._region_y2 = y2
        self._updating_from_canvas = False
        self._preview_timer.Start(100, wx.TIMER_ONE_SHOT)

    def _update_preview(self):
        """미리보기 업데이트"""
        if not self._original_images:
            return

        target = self._target_combo.GetSelection()
        selected_indices = getattr(self.frames, 'selected_indices', set())
        current_idx = getattr(self.frames, 'current_index', 0)

        for i, frame in enumerate(self.frames):
            if i >= len(self._original_images) or self._original_images[i] is None:
                continue

            # 적용 대상 확인
            should_apply = False
            if target == 0:  # 모든 프레임
                should_apply = True
            elif target == 1:  # 선택한 프레임
                should_apply = i in selected_indices
            elif target == 2:  # 현재 프레임만
                should_apply = i == current_idx

            # 현재 보고 있는 프레임은 항상 프리뷰 표시
            show_preview = should_apply or (i == current_idx)

            try:
                if show_preview:
                    processed = self._apply_censor(self._original_images[i])
                    frame._image = processed
                else:
                    frame._image = self._original_images[i].copy()
            except Exception:
                pass

        self._safe_canvas_update()
        self.update_preview()

    def _apply_censor(self, image: Image.Image) -> Image.Image:
        """검열 효과 적용"""
        region = (
            self._region_x1,
            self._region_y1,
            self._region_x2,
            self._region_y2
        )

        index = self._type_combo.GetSelection()
        if 0 <= index < len(self.CENSOR_TYPES):
            censor_type = self.CENSOR_TYPES[index][1]
        else:
            censor_type = "mosaic"

        strength = self._strength_spin.GetValue()

        if censor_type == "mosaic":
            return ImageEffects.apply_mosaic(image, region, strength)
        elif censor_type == "blur":
            return ImageEffects.apply_blur_region(image, region, strength)
        elif censor_type == "black_bar":
            color = (
                self._bar_color.Red(),
                self._bar_color.Green(),
                self._bar_color.Blue()
            )
            return ImageEffects.apply_black_bar(image, region, color)

        return image.copy()

    def _on_clear(self, event):
        """초기화"""
        # 영역 초기화
        w = getattr(self.frames, 'width', 100)
        h = getattr(self.frames, 'height', 100)
        self._region_x1 = w // 4
        self._region_y1 = h // 4
        self._region_x2 = w * 3 // 4
        self._region_y2 = h * 3 // 4

        # 원본으로 복원
        for i, frame in enumerate(self.frames):
            if i < len(self._original_images) and self._original_images[i] is not None:
                try:
                    frame._image = self._original_images[i].copy()
                except Exception:
                    pass

        self._safe_canvas_update()

    def _on_apply(self, event):
        """적용"""
        target = self._target_combo.GetSelection()
        selected_indices = getattr(self.frames, 'selected_indices', set())
        current_idx = getattr(self.frames, 'current_index', 0)

        for i, frame in enumerate(self.frames):
            if i >= len(self._original_images) or self._original_images[i] is None:
                continue

            # 적용 대상 확인
            should_apply = False
            if target == 0:  # 모든 프레임
                should_apply = True
            elif target == 1:  # 선택한 프레임
                should_apply = i in selected_indices
            elif target == 2:  # 현재 프레임만
                should_apply = i == current_idx

            if should_apply:
                try:
                    processed = self._apply_censor(self._original_images[i])
                    frame._image = processed
                except Exception:
                    pass
            else:
                try:
                    frame._image = self._original_images[i].copy()
                except Exception:
                    pass

        self._on_deactivated()
        if hasattr(self._main_window, '_is_modified'):
            self._main_window._is_modified = True
        if hasattr(self._main_window, '_update_info_bar'):
            self._main_window._update_info_bar()
        self._safe_canvas_update()
        super()._on_apply(event)
        self.hide_from_canvas()

    def _on_cancel(self, event):
        """취소 - 원본으로 복원"""
        for i, frame in enumerate(self.frames):
            if i < len(self._original_images) and self._original_images[i] is not None:
                try:
                    frame._image = self._original_images[i].copy()
                except Exception:
                    pass

        self._safe_canvas_update()
        super()._on_cancel(event)

    def reset_to_default(self):
        """기본값으로 초기화"""
        self._type_combo.SetSelection(0)
        self._strength_spin.SetValue(10)
        self._bar_color = wx.Colour(0, 0, 0)
        self._target_combo.SetSelection(1)
