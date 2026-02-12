"""
StickerDialog - 스티커/도형 추가 다이얼로그 (wxPython 버전)

PyQt6 QDialog를 wx.Dialog로 마이그레이션
"""
import wx
import math
from PIL import Image, ImageDraw
from typing import TYPE_CHECKING, Optional
from ...utils.image_utils import pil_to_wx_bitmap
from ..style_constants_wx import Colors, ThemedDialog

if TYPE_CHECKING:
    from ..main_window import MainWindow


class ShapeButton(wx.Button):
    """도형 선택 버튼"""

    def __init__(self, parent, name: str, shape_type: str):
        super().__init__(parent, label=name)
        self._shape_type = shape_type
        self.SetMinSize((80, 60))

        self.SetBackgroundColour(Colors.BG_TERTIARY)
        self.SetForegroundColour(Colors.TEXT_PRIMARY)

    @property
    def shape_type(self) -> str:
        return self._shape_type

    def set_selected(self, selected: bool):
        """선택 상태 설정"""
        if selected:
            self.SetBackgroundColour(Colors.ACCENT)
        else:
            self.SetBackgroundColour(Colors.BG_TERTIARY)
        self.Refresh()


class StickerDialog(ThemedDialog):
    """스티커/도형 추가 다이얼로그 (wxPython)"""

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(parent or main_window, title="스티커/도형 추가",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._main_window = main_window
        self._original_image: Optional[Image.Image] = None
        self._fill_color = wx.Colour(255, 107, 107)
        self._stroke_color = wx.Colour(255, 255, 255)
        self._current_shape = "rectangle"
        self._shape_buttons: list = []

        # 프리뷰 업데이트 타이머
        self._preview_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_preview_timer, self._preview_timer)

        self._setup_ui()
        self._load_current_frame()

    def _setup_ui(self):
        """UI 초기화"""
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

        # 도형 선택
        shape_box = wx.StaticBox(self, label="도형 선택")
        shape_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        shape_sizer = wx.StaticBoxSizer(shape_box, wx.VERTICAL)
        shape_sizer.AddSpacer(10)

        shape_grid = wx.GridSizer(2, 3, 10, 10)

        shapes = [
            ("사각형", "rectangle"),
            ("원", "ellipse"),
            ("삼각형", "triangle"),
            ("별", "star"),
            ("화살표", "arrow"),
            ("하트", "heart"),
        ]

        for name, shape_type in shapes:
            btn = ShapeButton(self, name, shape_type)
            btn.Bind(wx.EVT_BUTTON, self._on_shape_clicked)
            shape_grid.Add(btn, 0, wx.EXPAND)
            self._shape_buttons.append(btn)

            if shape_type == "rectangle":
                btn.set_selected(True)

        shape_sizer.Add(shape_grid, 0, wx.EXPAND | wx.ALL, 10)
        settings_sizer.Add(shape_sizer, 0, wx.EXPAND)
        settings_sizer.AddSpacer(10)

        # 크기/위치
        pos_box = wx.StaticBox(self, label="크기 및 위치")
        pos_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        pos_sizer = wx.StaticBoxSizer(pos_box, wx.VERTICAL)
        pos_sizer.AddSpacer(10)

        # 위치
        pos_row = wx.BoxSizer(wx.HORIZONTAL)
        x_label = wx.StaticText(self, label="X:")
        x_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        pos_row.Add(x_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self._x_spin = wx.SpinCtrl(self, min=0, max=10000, initial=50)
        self._x_spin.SetBackgroundColour(Colors.BG_TERTIARY)
        self._x_spin.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._x_spin.Bind(wx.EVT_SPINCTRL, self._on_setting_changed)
        pos_row.Add(self._x_spin, 1)

        pos_row.AddSpacer(10)

        y_label = wx.StaticText(self, label="Y:")
        y_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        pos_row.Add(y_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self._y_spin = wx.SpinCtrl(self, min=0, max=10000, initial=50)
        self._y_spin.SetBackgroundColour(Colors.BG_TERTIARY)
        self._y_spin.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._y_spin.Bind(wx.EVT_SPINCTRL, self._on_setting_changed)
        pos_row.Add(self._y_spin, 1)

        pos_sizer.Add(pos_row, 0, wx.EXPAND | wx.ALL, 10)

        # 크기
        size_row = wx.BoxSizer(wx.HORIZONTAL)
        w_label = wx.StaticText(self, label="너비:")
        w_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        size_row.Add(w_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self._width_spin = wx.SpinCtrl(self, min=10, max=1000, initial=100)
        self._width_spin.SetBackgroundColour(Colors.BG_TERTIARY)
        self._width_spin.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._width_spin.Bind(wx.EVT_SPINCTRL, self._on_setting_changed)
        size_row.Add(self._width_spin, 1)

        size_row.AddSpacer(10)

        h_label = wx.StaticText(self, label="높이:")
        h_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        size_row.Add(h_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self._height_spin = wx.SpinCtrl(self, min=10, max=1000, initial=100)
        self._height_spin.SetBackgroundColour(Colors.BG_TERTIARY)
        self._height_spin.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._height_spin.Bind(wx.EVT_SPINCTRL, self._on_setting_changed)
        size_row.Add(self._height_spin, 1)

        pos_sizer.Add(size_row, 0, wx.EXPAND | wx.ALL, 10)

        settings_sizer.Add(pos_sizer, 0, wx.EXPAND)
        settings_sizer.AddSpacer(10)

        # 색상 설정
        color_box = wx.StaticBox(self, label="색상")
        color_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        color_sizer = wx.StaticBoxSizer(color_box, wx.VERTICAL)
        color_sizer.AddSpacer(10)

        # 채우기 색상
        fill_row = wx.BoxSizer(wx.HORIZONTAL)
        self._fill_check = wx.CheckBox(self, label="채우기")
        self._fill_check.SetValue(True)
        self._fill_check.SetForegroundColour(Colors.TEXT_SECONDARY)
        self._fill_check.Bind(wx.EVT_CHECKBOX, self._on_setting_changed)
        fill_row.Add(self._fill_check, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self._fill_color_btn = wx.ColourPickerCtrl(self, colour=self._fill_color)
        self._fill_color_btn.Bind(wx.EVT_COLOURPICKER_CHANGED, self._on_fill_color_changed)
        fill_row.Add(self._fill_color_btn, 0)

        fill_row.AddStretchSpacer()
        color_sizer.Add(fill_row, 0, wx.EXPAND | wx.ALL, 10)

        # 테두리
        stroke_row = wx.BoxSizer(wx.HORIZONTAL)
        self._stroke_check = wx.CheckBox(self, label="테두리")
        self._stroke_check.SetValue(True)
        self._stroke_check.SetForegroundColour(Colors.TEXT_SECONDARY)
        self._stroke_check.Bind(wx.EVT_CHECKBOX, self._on_setting_changed)
        stroke_row.Add(self._stroke_check, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self._stroke_color_btn = wx.ColourPickerCtrl(self, colour=self._stroke_color)
        self._stroke_color_btn.Bind(wx.EVT_COLOURPICKER_CHANGED, self._on_stroke_color_changed)
        stroke_row.Add(self._stroke_color_btn, 0, wx.RIGHT, 10)

        self._stroke_width_spin = wx.SpinCtrl(self, min=1, max=20, initial=2)
        self._stroke_width_spin.SetBackgroundColour(Colors.BG_TERTIARY)
        self._stroke_width_spin.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._stroke_width_spin.Bind(wx.EVT_SPINCTRL, self._on_setting_changed)
        stroke_row.Add(self._stroke_width_spin, 0)

        stroke_row.AddStretchSpacer()
        color_sizer.Add(stroke_row, 0, wx.EXPAND | wx.ALL, 10)

        # 투명도
        opacity_row = wx.BoxSizer(wx.HORIZONTAL)
        opacity_label = wx.StaticText(self, label="투명도:")
        opacity_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        opacity_row.Add(opacity_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self._opacity_slider = wx.Slider(self, value=100, minValue=0, maxValue=100,
                                        style=wx.SL_HORIZONTAL)
        self._opacity_slider.SetBackgroundColour(Colors.BG_PRIMARY)
        self._opacity_slider.Bind(wx.EVT_SLIDER, self._on_setting_changed)
        opacity_row.Add(self._opacity_slider, 1)

        self._opacity_label = wx.StaticText(self, label="100%")
        self._opacity_label.SetMinSize((40, -1))
        self._opacity_label.SetForegroundColour(Colors.TEXT_MUTED)
        opacity_row.Add(self._opacity_label, 0, wx.LEFT, 10)

        color_sizer.Add(opacity_row, 0, wx.EXPAND | wx.ALL, 10)

        settings_sizer.Add(color_sizer, 0, wx.EXPAND)
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

        settings_sizer.Add(target_sizer, 0, wx.EXPAND)
        settings_sizer.AddStretchSpacer()

        # 버튼
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
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

        settings_sizer.Add(button_sizer, 0, wx.EXPAND)
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

                self._x_spin.SetMax(current_frame.width)
                self._y_spin.SetMax(current_frame.height)

                self._update_preview()
        except Exception:
            pass

    def _on_shape_clicked(self, event):
        """도형 버튼 클릭"""
        btn = event.GetEventObject()
        if not isinstance(btn, ShapeButton):
            return

        # 다른 버튼 해제
        for b in self._shape_buttons:
            b.set_selected(b == btn)

        self._current_shape = btn.shape_type
        self._update_preview()

    def _on_setting_changed(self, event):
        """설정 변경됨"""
        self._opacity_label.SetLabel(f"{self._opacity_slider.GetValue()}%")
        self._preview_timer.Start(100, wx.TIMER_ONE_SHOT)

    def _on_fill_color_changed(self, event):
        """채우기 색상 변경"""
        self._fill_color = event.GetColour()
        self._on_setting_changed(event)

    def _on_stroke_color_changed(self, event):
        """테두리 색상 변경"""
        self._stroke_color = event.GetColour()
        self._on_setting_changed(event)

    def _on_preview_timer(self, event):
        """프리뷰 타이머"""
        self._update_preview()

    def _update_preview(self):
        """프리뷰 업데이트"""
        if not self._original_image:
            return

        try:
            result = self.apply_shape_to_image(self._original_image.copy())

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

    def apply_shape_to_image(self, image: Image.Image) -> Image.Image:
        """이미지에 도형 적용"""
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        # 도형 레이어 생성
        shape_layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(shape_layer)

        x = self._x_spin.GetValue()
        y = self._y_spin.GetValue()
        w = self._width_spin.GetValue()
        h = self._height_spin.GetValue()
        opacity = int(self._opacity_slider.GetValue() * 255 / 100)

        # 색상
        fill = None
        if self._fill_check.GetValue():
            fill = (
                self._fill_color.Red(),
                self._fill_color.Green(),
                self._fill_color.Blue(),
                opacity
            )

        outline = None
        outline_width = 0
        if self._stroke_check.GetValue():
            outline = (
                self._stroke_color.Red(),
                self._stroke_color.Green(),
                self._stroke_color.Blue(),
                opacity
            )
            outline_width = self._stroke_width_spin.GetValue()

        # 도형 그리기
        if self._current_shape == "rectangle":
            draw.rectangle([x, y, x + w, y + h], fill=fill, outline=outline, width=outline_width)

        elif self._current_shape == "ellipse":
            draw.ellipse([x, y, x + w, y + h], fill=fill, outline=outline, width=outline_width)

        elif self._current_shape == "triangle":
            points = [
                (x + w // 2, y),
                (x, y + h),
                (x + w, y + h)
            ]
            draw.polygon(points, fill=fill, outline=outline, width=outline_width)

        elif self._current_shape == "star":
            self._draw_star(draw, x, y, w, h, fill, outline, outline_width)

        elif self._current_shape == "arrow":
            self._draw_arrow(draw, x, y, w, h, fill, outline, outline_width)

        elif self._current_shape == "heart":
            self._draw_heart(draw, x, y, w, h, fill, outline, outline_width)

        # 합성
        return Image.alpha_composite(image, shape_layer)

    def _draw_star(self, draw, x, y, w, h, fill, outline, outline_width):
        """별 그리기"""
        cx, cy = x + w // 2, y + h // 2
        outer_r = min(w, h) // 2
        inner_r = outer_r * 0.4

        points = []
        for i in range(10):
            angle = math.pi / 2 + i * math.pi / 5
            r = outer_r if i % 2 == 0 else inner_r
            px = cx + r * math.cos(angle)
            py = cy - r * math.sin(angle)
            points.append((px, py))

        draw.polygon(points, fill=fill, outline=outline, width=outline_width)

    def _draw_arrow(self, draw, x, y, w, h, fill, outline, outline_width):
        """화살표 그리기"""
        points = [
            (x, y + h // 3),
            (x + w * 2 // 3, y + h // 3),
            (x + w * 2 // 3, y),
            (x + w, y + h // 2),
            (x + w * 2 // 3, y + h),
            (x + w * 2 // 3, y + h * 2 // 3),
            (x, y + h * 2 // 3),
        ]
        draw.polygon(points, fill=fill, outline=outline, width=outline_width)

    def _draw_heart(self, draw, x, y, w, h, fill, outline, outline_width):
        """하트 그리기"""
        points = []
        for t in range(0, 360, 5):
            angle = math.radians(t)
            px = 16 * (math.sin(angle) ** 3)
            py = -(13 * math.cos(angle) - 5 * math.cos(2 * angle) -
                   2 * math.cos(3 * angle) - math.cos(4 * angle))

            # 스케일 및 위치 조정
            px = x + w // 2 + px * w / 35
            py = y + h // 2 + py * h / 35
            points.append((px, py))

        draw.polygon(points, fill=fill, outline=outline, width=outline_width)

    def get_target(self) -> str:
        """적용 대상 반환"""
        index = self._target_combo.GetSelection()
        return ["current", "selected", "all"][index]

    def Destroy(self):
        """리소스 정리"""
        self._preview_timer.Stop()
        self._original_image = None
        super().Destroy()
