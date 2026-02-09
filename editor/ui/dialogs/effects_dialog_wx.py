"""
EffectsDialog - 효과/필터 다이얼로그 (wxPython 버전)

PyQt6 QDialog를 wx.Dialog로 마이그레이션
"""
import wx
from PIL import Image
from typing import TYPE_CHECKING, Dict, Any, Optional
from ...core.image_effects import ImageEffects
from ...utils.image_utils import pil_to_wx_bitmap
from ..style_constants_wx import Colors

if TYPE_CHECKING:
    from ..main_window import MainWindow


class EffectSlider(wx.Panel):
    """효과 슬라이더 위젯"""

    def __init__(self, parent, name: str, min_val: int, max_val: int,
                 default: int, suffix: str = ""):
        super().__init__(parent)
        self.SetBackgroundColour(Colors.BG_PRIMARY)
        self._name = name
        self._default = default
        self._suffix = suffix
        self._callback = None

        sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 라벨
        self._label = wx.StaticText(self, label=f"{name}:")
        self._label.SetMinSize((80, -1))
        self._label.SetForegroundColour(Colors.TEXT_SECONDARY)
        sizer.Add(self._label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # 슬라이더
        self._slider = wx.Slider(self, value=default, minValue=min_val,
                                maxValue=max_val, style=wx.SL_HORIZONTAL)
        self._slider.SetMinSize((100, 20))
        self._slider.Bind(wx.EVT_SLIDER, self._on_value_changed)
        sizer.Add(self._slider, 1, wx.ALIGN_CENTER_VERTICAL)

        # 값 표시
        self._value_label = wx.StaticText(self, label=f"{default}{suffix}")
        self._value_label.SetMinSize((50, -1))
        self._value_label.SetForegroundColour(Colors.TEXT_MUTED)
        sizer.Add(self._value_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)

        self.SetSizer(sizer)

    def _on_value_changed(self, event):
        """값 변경"""
        value = self._slider.GetValue()
        self._value_label.SetLabel(f"{value}{self._suffix}")
        if self._callback:
            self._callback()

    def value(self) -> int:
        return self._slider.GetValue()

    def set_value(self, value: int):
        self._slider.SetValue(value)
        self._value_label.SetLabel(f"{value}{self._suffix}")

    def reset(self):
        self.set_value(self._default)

    def set_callback(self, callback):
        """값 변경 콜백 설정"""
        self._callback = callback


class FilterButton(wx.Button):
    """필터 버튼"""

    def __init__(self, parent, name: str, filter_type: str):
        super().__init__(parent, label=name)
        self._filter_type = filter_type
        self.SetMinSize((100, 80))

        self.SetBackgroundColour(Colors.BG_TERTIARY)
        self.SetForegroundColour(Colors.TEXT_PRIMARY)

    @property
    def filter_type(self) -> str:
        return self._filter_type

    def set_selected(self, selected: bool):
        """선택 상태 설정"""
        if selected:
            self.SetBackgroundColour(Colors.ACCENT)
        else:
            self.SetBackgroundColour(Colors.BG_TERTIARY)
        self.Refresh()


class EffectsDialog(wx.Dialog):
    """효과/필터 다이얼로그 (wxPython)"""

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(parent or main_window, title="효과/필터", size=(700, 550))
        self._main_window = main_window
        self._original_image: Optional[Image.Image] = None
        self._current_filter: Optional[str] = None
        self._filter_buttons: list = []

        # 프리뷰 업데이트 타이머
        self._preview_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_preview_timer, self._preview_timer)

        self._setup_ui()
        self._load_current_frame()

    def _setup_ui(self):
        """UI 초기화"""
        self.SetBackgroundColour(Colors.BG_PRIMARY)

        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer.AddSpacer(15)

        # === 왼쪽: 프리뷰 ===
        preview_sizer = wx.BoxSizer(wx.VERTICAL)
        preview_sizer.AddSpacer(15)

        self._preview_label = wx.StaticBitmap(self)
        self._preview_label.SetMinSize((300, 300))
        self._preview_label.SetBackgroundColour(Colors.BG_SECONDARY)
        preview_sizer.Add(self._preview_label, 1, wx.EXPAND)

        main_sizer.Add(preview_sizer, 1, wx.EXPAND | wx.RIGHT, 15)

        # === 오른쪽: 설정 ===
        settings_sizer = wx.BoxSizer(wx.VERTICAL)
        settings_sizer.AddSpacer(15)

        # 탭 위젯
        tabs = wx.Notebook(self)
        tabs.SetBackgroundColour(Colors.BG_PRIMARY)
        tabs.SetForegroundColour(Colors.TEXT_PRIMARY)

        # === 조정 탭 ===
        adjust_panel = wx.Panel(tabs)
        adjust_panel.SetBackgroundColour(Colors.BG_PRIMARY)
        adjust_sizer = wx.BoxSizer(wx.VERTICAL)
        adjust_sizer.AddSpacer(10)

        self._brightness_slider = EffectSlider(adjust_panel, "밝기", 0, 200, 100, "%")
        self._brightness_slider.set_callback(self._on_effect_changed)
        adjust_sizer.Add(self._brightness_slider, 0, wx.EXPAND | wx.ALL, 5)

        self._contrast_slider = EffectSlider(adjust_panel, "대비", 0, 200, 100, "%")
        self._contrast_slider.set_callback(self._on_effect_changed)
        adjust_sizer.Add(self._contrast_slider, 0, wx.EXPAND | wx.ALL, 5)

        self._saturation_slider = EffectSlider(adjust_panel, "채도", 0, 200, 100, "%")
        self._saturation_slider.set_callback(self._on_effect_changed)
        adjust_sizer.Add(self._saturation_slider, 0, wx.EXPAND | wx.ALL, 5)

        self._sharpness_slider = EffectSlider(adjust_panel, "선명도", 0, 200, 100, "%")
        self._sharpness_slider.set_callback(self._on_effect_changed)
        adjust_sizer.Add(self._sharpness_slider, 0, wx.EXPAND | wx.ALL, 5)

        self._gamma_slider = EffectSlider(adjust_panel, "감마", 10, 300, 100, "%")
        self._gamma_slider.set_callback(self._on_effect_changed)
        adjust_sizer.Add(self._gamma_slider, 0, wx.EXPAND | wx.ALL, 5)

        adjust_sizer.AddStretchSpacer()
        adjust_panel.SetSizer(adjust_sizer)
        tabs.AddPage(adjust_panel, "조정")

        # === 필터 탭 ===
        filter_panel = wx.Panel(tabs)
        filter_panel.SetBackgroundColour(Colors.BG_PRIMARY)
        filter_layout = wx.BoxSizer(wx.VERTICAL)
        filter_layout.AddSpacer(10)

        filter_grid = wx.GridSizer(3, 4, 10, 10)

        filters = [
            ("원본", "none"),
            ("흑백", "grayscale"),
            ("세피아", "sepia"),
            ("반전", "invert"),
            ("블러", "blur"),
            ("샤픈", "sharpen"),
            ("엠보스", "emboss"),
            ("윤곽선", "contour"),
            ("포스터", "posterize"),
            ("솔라라이즈", "solarize"),
            ("엣지 강조", "edge"),
            ("비네트", "vignette"),
        ]

        for name, filter_type in filters:
            btn = FilterButton(filter_panel, name, filter_type)
            btn.Bind(wx.EVT_BUTTON, self._on_filter_clicked)
            filter_grid.Add(btn, 0, wx.EXPAND)
            self._filter_buttons.append(btn)

            if filter_type == "none":
                btn.set_selected(True)

        filter_layout.Add(filter_grid, 0, wx.EXPAND | wx.ALL, 10)
        filter_layout.AddStretchSpacer()
        filter_panel.SetSizer(filter_layout)
        tabs.AddPage(filter_panel, "필터")

        settings_sizer.Add(tabs, 1, wx.EXPAND)
        settings_sizer.AddSpacer(10)

        # 적용 대상
        target_box = wx.StaticBox(self, label="적용 대상")
        target_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        target_sizer = wx.StaticBoxSizer(target_box, wx.HORIZONTAL)

        self._target_combo = wx.ComboBox(self, style=wx.CB_READONLY,
                                        choices=["현재 프레임만", "선택한 프레임", "모든 프레임"])
        self._target_combo.SetBackgroundColour(Colors.BG_TERTIARY)
        self._target_combo.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._target_combo.SetSelection(1)
        target_sizer.Add(self._target_combo, 1, wx.ALL, 10)

        settings_sizer.Add(target_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        settings_sizer.AddSpacer(10)

        # 버튼
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        reset_btn = wx.Button(self, label="초기화")
        reset_btn.SetBackgroundColour(Colors.BG_TERTIARY)
        reset_btn.SetForegroundColour(Colors.TEXT_PRIMARY)
        reset_btn.Bind(wx.EVT_BUTTON, self._reset_effects)
        button_sizer.Add(reset_btn, 0, wx.ALL, 5)

        button_sizer.AddStretchSpacer()

        apply_btn = wx.Button(self, wx.ID_OK, label="적용")
        apply_btn.SetBackgroundColour(Colors.ACCENT)
        apply_btn.SetForegroundColour(Colors.TEXT_PRIMARY)
        apply_btn.SetMinSize((80, 32))
        button_sizer.Add(apply_btn, 0, wx.ALL, 5)

        cancel_btn = wx.Button(self, wx.ID_CANCEL, label="취소")
        cancel_btn.SetBackgroundColour(Colors.BG_TERTIARY)
        cancel_btn.SetForegroundColour(Colors.TEXT_PRIMARY)
        cancel_btn.SetMinSize((80, 32))
        button_sizer.Add(cancel_btn, 0, wx.ALL, 5)

        settings_sizer.Add(button_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        settings_sizer.AddSpacer(15)

        main_sizer.Add(settings_sizer, 1, wx.EXPAND | wx.RIGHT, 15)

        self.SetSizer(main_sizer)

    def _load_current_frame(self):
        """현재 프레임 로드"""
        try:
            frames = getattr(self._main_window, 'frames', None)
            if not frames or getattr(frames, 'is_empty', True):
                return

            current_frame = getattr(frames, 'current_frame', None)
            if current_frame:
                self._original_image = current_frame.image.copy()
                self._update_preview()
        except Exception:
            pass

    def _on_effect_changed(self):
        """효과 변경됨"""
        self._preview_timer.Start(100, wx.TIMER_ONE_SHOT)

    def _on_filter_clicked(self, event):
        """필터 버튼 클릭"""
        btn = event.GetEventObject()
        if not isinstance(btn, FilterButton):
            return

        # 다른 버튼 해제
        for b in self._filter_buttons:
            b.set_selected(b == btn)

        self._current_filter = btn.filter_type
        self._update_preview()

    def _on_preview_timer(self, event):
        """프리뷰 타이머"""
        self._update_preview()

    def _update_preview(self):
        """프리뷰 업데이트"""
        if not self._original_image:
            return

        try:
            # 효과 적용
            result = self._apply_current_effects(self._original_image)

            # PIL -> wx.Bitmap
            bitmap = pil_to_wx_bitmap(result)

            # 스케일
            lbl_w = max(1, self._preview_label.GetSize().width)
            lbl_h = max(1, self._preview_label.GetSize().height)

            img = bitmap.ConvertToImage()
            img_w, img_h = img.GetWidth(), img.GetHeight()

            # 종횡비 유지하면서 스케일
            scale_w = (lbl_w - 10) / img_w
            scale_h = (lbl_h - 10) / img_h
            scale = min(scale_w, scale_h)

            new_w = int(img_w * scale)
            new_h = int(img_h * scale)

            scaled_img = img.Scale(new_w, new_h, wx.IMAGE_QUALITY_HIGH)
            self._preview_label.SetBitmap(wx.Bitmap(scaled_img))

        except Exception:
            pass

    def _apply_current_effects(self, image: Image.Image) -> Image.Image:
        """현재 설정된 효과 적용"""
        result = image.copy()

        # 조정 효과
        brightness = self._brightness_slider.value() / 100.0
        contrast = self._contrast_slider.value() / 100.0
        saturation = self._saturation_slider.value() / 100.0
        sharpness = self._sharpness_slider.value() / 100.0
        gamma = self._gamma_slider.value() / 100.0

        result = ImageEffects.apply_all_effects(
            result,
            brightness=brightness,
            contrast=contrast,
            saturation=saturation,
            sharpness=sharpness,
            gamma=gamma
        )

        # 필터 효과
        if self._current_filter and self._current_filter != "none":
            filter_map = {
                "grayscale": ImageEffects.apply_grayscale,
                "sepia": ImageEffects.apply_sepia,
                "invert": ImageEffects.apply_invert,
                "blur": lambda img: ImageEffects.apply_blur(img, 3),
                "sharpen": ImageEffects.apply_sharpen,
                "emboss": ImageEffects.apply_emboss,
                "contour": ImageEffects.apply_contour,
                "posterize": ImageEffects.apply_posterize,
                "solarize": ImageEffects.apply_solarize,
                "edge": ImageEffects.apply_edge_enhance,
                "vignette": ImageEffects.apply_vignette,
            }

            if self._current_filter in filter_map:
                result = filter_map[self._current_filter](result)

        return result

    def _reset_effects(self, event):
        """효과 초기화"""
        self._brightness_slider.reset()
        self._contrast_slider.reset()
        self._saturation_slider.reset()
        self._sharpness_slider.reset()
        self._gamma_slider.reset()

        for btn in self._filter_buttons:
            btn.set_selected(btn.filter_type == "none")

        self._current_filter = None
        self._update_preview()

    def get_effect_settings(self) -> Dict[str, Any]:
        """현재 효과 설정 반환"""
        return {
            "brightness": self._brightness_slider.value() / 100.0,
            "contrast": self._contrast_slider.value() / 100.0,
            "saturation": self._saturation_slider.value() / 100.0,
            "sharpness": self._sharpness_slider.value() / 100.0,
            "gamma": self._gamma_slider.value() / 100.0,
            "filter": self._current_filter,
        }

    def get_target(self) -> str:
        """적용 대상 반환"""
        index = self._target_combo.GetSelection()
        return ["current", "selected", "all"][index]

    def apply_to_image(self, image: Image.Image) -> Image.Image:
        """이미지에 효과 적용"""
        return self._apply_current_effects(image)

    def Destroy(self):
        """리소스 정리"""
        self._preview_timer.Stop()
        self._original_image = None
        super().Destroy()
