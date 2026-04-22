"""
EffectsToolbar - 효과/필터 인라인 툴바 (wxPython 버전)
"""
import wx
from PIL import Image
from typing import TYPE_CHECKING, Optional, Dict, Any, List
from .base_toolbar_wx import InlineToolbarBase

if TYPE_CHECKING:
    from ..main_window import MainWindow

try:
    from ...core.image_effects import ImageEffects
except ImportError:
    ImageEffects = None


class EffectsToolbar(InlineToolbarBase):
    """효과/필터 인라인 툴바 (wxPython)

    밝기/대비/채도 슬라이더와 필터 드롭다운을 제공합니다.
    """

    # 필터 목록
    FILTERS = [
        ("none", "none"),
        ("grayscale", "grayscale"),
        ("sepia", "sepia"),
        ("invert", "invert"),
        ("blur", "blur"),
        ("sharpen", "sharpen"),
        ("emboss", "emboss"),
        ("contour", "contour"),
        ("posterize", "posterize"),
        ("vignette", "vignette"),
    ]

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(main_window, parent)
        self._original_images: List[Optional[Image.Image]] = []
        self._setup_controls()

    def _setup_controls(self):
        """컨트롤 설정"""
        translations = getattr(self._main_window, '_translations', None)

        # 적용 대상
        target_tooltip = translations.tr("target_tooltip") if translations else "적용 대상 프레임"
        self._target_combo = self.add_target_combo(self._on_effect_changed, tooltip=target_tooltip)

        self.add_separator()

        # 밝기/대비/채도
        self.add_icon_label("effects", 28, "밝기/대비/채도")

        # 밝기
        self._brightness_slider = self._create_slider(-50, 50, 0)
        brightness_tooltip = translations.tr("effects_brightness") if translations else "밝기"
        self._brightness_slider.SetToolTip(brightness_tooltip)
        self._brightness_slider.Bind(wx.EVT_SLIDER, lambda e: self._on_effect_changed())
        self.add_control(self._brightness_slider)

        self._brightness_label = wx.StaticText(self._controls_widget, label="0")
        self._brightness_label.SetMinSize((22, -1))
        self.add_control(self._brightness_label)

        # 대비
        self._contrast_slider = self._create_slider(-50, 50, 0)
        contrast_tooltip = translations.tr("effects_contrast") if translations else "대비"
        self._contrast_slider.SetToolTip(contrast_tooltip)
        self._contrast_slider.Bind(wx.EVT_SLIDER, lambda e: self._on_effect_changed())
        self.add_control(self._contrast_slider)

        self._contrast_label = wx.StaticText(self._controls_widget, label="0")
        self._contrast_label.SetMinSize((22, -1))
        self.add_control(self._contrast_label)

        # 채도
        self._saturation_slider = self._create_slider(-50, 50, 0)
        saturation_tooltip = translations.tr("effects_saturation") if translations else "채도"
        self._saturation_slider.SetToolTip(saturation_tooltip)
        self._saturation_slider.Bind(wx.EVT_SLIDER, lambda e: self._on_effect_changed())
        self.add_control(self._saturation_slider)

        self._saturation_label = wx.StaticText(self._controls_widget, label="0")
        self._saturation_label.SetMinSize((22, -1))
        self.add_control(self._saturation_label)

        self.add_separator()

        # 필터
        self.add_icon_label("color_palette", 20, "색상 필터")

        filter_choices = []
        if translations:
            filter_keys = ["effects_filter_none", "effects_filter_grayscale", "effects_filter_sepia",
                          "effects_filter_invert", "effects_filter_blur", "effects_filter_sharpen",
                          "effects_filter_emboss", "effects_filter_contour", "effects_filter_posterize",
                          "effects_filter_vignette"]
            for key in filter_keys:
                filter_choices.append(translations.tr(key))
        else:
            filter_choices = ["없음", "흑백", "세피아", "반전", "블러", "샤픈", "엠보스", "윤곽선", "포스터", "비네트"]

        self._filter_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY, choices=filter_choices)
        self._filter_combo.SetSelection(0)
        self._filter_combo.SetMinSize((90, -1))
        filter_tooltip = translations.tr("effects_filter") if translations else "필터"
        self._filter_combo.SetToolTip(filter_tooltip)
        self._filter_combo.Bind(wx.EVT_COMBOBOX, lambda e: self._on_effect_changed())
        self.add_control(self._filter_combo)

    def _create_slider(self, min_val: int, max_val: int, default: int) -> wx.Slider:
        """슬라이더 생성"""
        slider = wx.Slider(self._controls_widget, minValue=min_val, maxValue=max_val, value=default,
                          style=wx.SL_HORIZONTAL)
        slider.SetMinSize((100, 20))
        return slider

    def _on_activated(self):
        """툴바 활성화"""
        if not self.frames or getattr(self.frames, 'is_empty', False):
            return

        # 다른 캔버스 모드 종료
        canvas = self._safe_get_canvas()
        if canvas:
            try:
                if hasattr(canvas, 'stop_text_edit_mode'):
                    canvas.stop_text_edit_mode()
                if hasattr(canvas, 'stop_sticker_mode'):
                    canvas.stop_sticker_mode()
                if hasattr(canvas, 'stop_speech_bubble_mode'):
                    canvas.stop_speech_bubble_mode()
                if hasattr(canvas, 'stop_mosaic_mode'):
                    canvas.stop_mosaic_mode()
                if hasattr(canvas, 'stop_crop_mode'):
                    canvas.stop_crop_mode()
            except Exception:
                pass

        # 원본 이미지 저장
        self._original_images = self._snapshot_original_images()

    def _on_deactivated(self):
        """툴바 비활성화"""
        self._clear_original_images()

    def _on_effect_changed(self):
        """효과 변경됨"""
        self._brightness_label.SetLabel(str(self._brightness_slider.GetValue()))
        self._contrast_label.SetLabel(str(self._contrast_slider.GetValue()))
        self._saturation_label.SetLabel(str(self._saturation_slider.GetValue()))

        self._preview_timer.Start(150, wx.TIMER_ONE_SHOT)

    def _update_preview(self):
        """미리보기 업데이트"""
        if not self._original_images:
            return

        self._apply_frame_processor(
            self._target_combo.GetSelection(),
            self._process_effect_frame,
            preview_current=True,
        )

        self._safe_canvas_update()
        self.update_preview()

    def _process_effect_frame(self, original: Image.Image, _index: int, _should_apply: bool) -> Image.Image:
        return self._apply_effects(original)

    def _apply_effects(self, image: Image.Image) -> Image.Image:
        """이미지에 효과 적용"""
        if not ImageEffects:
            return image.copy()

        result = image.copy()

        brightness = 1.0 + (self._brightness_slider.GetValue() / 100.0)
        contrast = 1.0 + (self._contrast_slider.GetValue() / 100.0)
        saturation = 1.0 + (self._saturation_slider.GetValue() / 100.0)

        result = ImageEffects.apply_all_effects(
            result,
            brightness=brightness,
            contrast=contrast,
            saturation=saturation,
            sharpness=1.0,
            gamma=1.0
        )

        filter_idx = self._filter_combo.GetSelection()
        if filter_idx > 0:
            filter_type = self.FILTERS[filter_idx][1]
            result = self._apply_filter(result, filter_type)

        return result

    def _apply_filter(self, image: Image.Image, filter_type: str) -> Image.Image:
        """필터 적용"""
        if not ImageEffects:
            return image

        filter_map = {
            "grayscale": ImageEffects.apply_grayscale,
            "sepia": ImageEffects.apply_sepia,
            "invert": ImageEffects.apply_invert,
            "blur": lambda img: ImageEffects.apply_blur(img, 3),
            "sharpen": ImageEffects.apply_sharpen,
            "emboss": ImageEffects.apply_emboss,
            "contour": ImageEffects.apply_contour,
            "posterize": ImageEffects.apply_posterize,
            "vignette": ImageEffects.apply_vignette,
        }

        if filter_type in filter_map:
            return filter_map[filter_type](image)
        return image

    def _on_clear(self, event):
        """초기화"""
        self._brightness_slider.SetValue(0)
        self._contrast_slider.SetValue(0)
        self._saturation_slider.SetValue(0)
        self._filter_combo.SetSelection(0)

        self._restore_original_images()
        self._safe_canvas_update()

    def _on_apply(self, event):
        """적용"""
        self._apply_frame_processor(
            self._target_combo.GetSelection(),
            self._process_effect_frame,
        )
        self._finish_apply()

    def _on_cancel(self, event):
        """취소"""
        self._restore_original_images()
        self._finish_cancel()

    def reset_to_default(self):
        """기본값으로 초기화"""
        self._on_clear(None)

    def get_effect_settings(self) -> Dict[str, Any]:
        """현재 효과 설정 반환"""
        filter_idx = self._filter_combo.GetSelection()
        return {
            "brightness": 1.0 + (self._brightness_slider.GetValue() / 100.0),
            "contrast": 1.0 + (self._contrast_slider.GetValue() / 100.0),
            "saturation": 1.0 + (self._saturation_slider.GetValue() / 100.0),
            "filter": self.FILTERS[filter_idx][1] if filter_idx > 0 else None,
        }
