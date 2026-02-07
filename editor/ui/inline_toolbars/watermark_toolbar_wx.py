"""
WatermarkToolbar - 워터마크 추가 인라인 툴바 (wxPython 버전)
"""
import wx
from PIL import Image, ImageDraw, ImageFont
from typing import TYPE_CHECKING, Optional, List
from pathlib import Path
from .base_toolbar_wx import InlineToolbarBase

if TYPE_CHECKING:
    from ..main_window import MainWindow


class WatermarkToolbar(InlineToolbarBase):
    """워터마크 추가 인라인 툴바 (wxPython)

    텍스트 또는 이미지 워터마크를 추가합니다.
    9개 위치 선택, 투명도 조절, 타일링 패턴 지원.
    """

    # 위치 옵션
    POSITIONS = [
        ("좌측 상단", "top_left"),
        ("중앙 상단", "top_center"),
        ("우측 상단", "top_right"),
        ("좌측 중앙", "middle_left"),
        ("중앙", "middle_center"),
        ("우측 중앙", "middle_right"),
        ("좌측 하단", "bottom_left"),
        ("중앙 하단", "bottom_center"),
        ("우측 하단", "bottom_right"),
        ("타일링 (반복)", "tiling"),
    ]

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(main_window, parent)
        self._original_images: List[Optional[Image.Image]] = []
        self._text_color = wx.Colour(255, 255, 255)
        self._watermark_image: Optional[Image.Image] = None
        self._watermark_path: Optional[str] = None
        self._setup_controls()
        self.set_clear_button_visible(True)

    def _setup_controls(self):
        """컨트롤 설정"""
        translations = getattr(self._main_window, '_translations', None)

        # 워터마크 타입
        watermark_type_tooltip = translations.tr("watermark_type") if translations else "워터마크 타입"
        self.add_icon_label("text", 20, watermark_type_tooltip)

        type_choices = []
        if translations:
            type_choices.append(translations.tr("watermark_type_text"))
            type_choices.append(translations.tr("watermark_type_image"))
        else:
            type_choices = ["텍스트", "이미지"]

        self._type_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY, choices=type_choices)
        self._type_combo.SetSelection(0)
        self._type_combo.SetMinSize((90, -1))
        type_tooltip = translations.tr("watermark_type_tooltip") if translations else "타입"
        self._type_combo.SetToolTip(type_tooltip)
        self._type_combo.Bind(wx.EVT_COMBOBOX, self._on_type_changed)
        self.add_control(self._type_combo)

        # 텍스트 입력
        self._text_input = wx.TextCtrl(self._controls_widget)
        text_placeholder = translations.tr("watermark_text_placeholder") if translations else "텍스트"
        self._text_input.SetHint(text_placeholder)
        self._text_input.SetValue("© GIF")
        self._text_input.SetMinSize((120, -1))
        self._text_input.Bind(wx.EVT_TEXT, lambda e: self._on_setting_changed())
        self.add_control(self._text_input)

        # 폰트 크기
        font_size_tooltip = translations.tr("watermark_font_size") if translations else "폰트 크기"
        self.add_icon_label("font_size", 20, font_size_tooltip)

        self._font_spin = wx.SpinCtrl(self._controls_widget, min=8, max=72, initial=16)
        self._font_spin.SetMinSize((70, -1))
        self._font_spin.SetToolTip(font_size_tooltip)
        self._font_spin.Bind(wx.EVT_SPINCTRL, lambda e: self._on_setting_changed())
        self.add_control(self._font_spin)

        # 색상 버튼
        self._color_btn = wx.ColourPickerCtrl(self._controls_widget, colour=self._text_color)
        self._color_btn.SetMinSize((40, 30))
        text_color_tooltip = translations.tr("watermark_text_color") if translations else "텍스트 색상"
        self._color_btn.SetToolTip(text_color_tooltip)
        self._color_btn.Bind(wx.EVT_COLOURPICKER_CHANGED, self._on_color_changed)
        self.add_control(self._color_btn)

        # 이미지 선택 버튼
        image_btn_text = translations.tr("watermark_image_btn") if translations else "이미지"
        self._image_btn = wx.Button(self._controls_widget, label=f"{image_btn_text} 선택...")
        self._image_btn.SetMinSize((100, -1))
        self._image_btn.Bind(wx.EVT_BUTTON, self._select_image)
        self._image_btn.Hide()
        self.add_control(self._image_btn)

        self.add_separator()

        # 위치
        self.add_icon_label("position", 20, "워터마크 위치")
        pos_choices = [name for name, _ in self.POSITIONS]
        self._pos_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY, choices=pos_choices)
        self._pos_combo.SetSelection(8)  # 우측 하단 기본
        self._pos_combo.SetMinSize((90, -1))
        self._pos_combo.SetToolTip("위치")
        self._pos_combo.Bind(wx.EVT_COMBOBOX, lambda e: self._on_setting_changed())
        self.add_control(self._pos_combo)

        # 투명도
        self._opacity_slider = wx.Slider(self._controls_widget, minValue=10, maxValue=100, value=50,
                                        style=wx.SL_HORIZONTAL)
        self._opacity_slider.SetMinSize((60, -1))
        self._opacity_slider.SetToolTip("투명도")
        self._opacity_slider.Bind(wx.EVT_SLIDER, lambda e: self._on_setting_changed())
        self.add_control(self._opacity_slider)

        self._opacity_label = wx.StaticText(self._controls_widget, label="50%")
        self._opacity_label.SetMinSize((28, -1))
        self.add_control(self._opacity_label)

        # 마진
        self._margin_spin = wx.SpinCtrl(self._controls_widget, min=0, max=100, initial=10)
        self._margin_spin.SetMinSize((70, -1))
        self._margin_spin.SetToolTip("여백")
        self._margin_spin.Bind(wx.EVT_SPINCTRL, lambda e: self._on_setting_changed())
        self.add_control(self._margin_spin)

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

        self._update_preview()

    def _on_deactivated(self):
        """툴바 비활성화"""
        self._original_images = []
        self._preview_timer.Stop()

    def _on_type_changed(self, event):
        """워터마크 타입 변경"""
        is_text = self._type_combo.GetSelection() == 0
        self._text_input.Show(is_text)
        self._font_spin.Show(is_text)
        self._color_btn.Show(is_text)
        self._image_btn.Show(not is_text)
        self._controls_sizer.Layout()
        self._on_setting_changed()

    def _on_setting_changed(self):
        """설정 변경됨"""
        self._opacity_label.SetLabel(f"{self._opacity_slider.GetValue()}%")
        self._preview_timer.Start(100, wx.TIMER_ONE_SHOT)

    def _on_color_changed(self, event):
        """색상 변경"""
        self._text_color = event.GetColour()
        self._on_setting_changed()

    def _select_image(self, event):
        """워터마크 이미지 선택"""
        with wx.FileDialog(
            self,
            "워터마크 이미지 선택",
            wildcard="이미지 파일 (*.png;*.jpg;*.jpeg;*.bmp;*.gif)|*.png;*.jpg;*.jpeg;*.bmp;*.gif",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                file_path = dlg.GetPath()
                try:
                    self._watermark_image = Image.open(file_path).convert('RGBA')
                    self._watermark_path = file_path
                    self._image_btn.SetLabel(Path(file_path).name[:15] + "...")
                    self._on_setting_changed()
                except Exception as e:
                    translations = getattr(self._main_window, '_translations', None)
                    wx.MessageBox(
                        f"이미지 로드 실패: {e}",
                        translations.tr("msg_error") if translations else "오류",
                        wx.OK | wx.ICON_ERROR
                    )

    def _update_preview(self):
        """미리보기 업데이트"""
        if not self._original_images:
            return

        for i, frame in enumerate(self.frames):
            if i >= len(self._original_images) or self._original_images[i] is None:
                continue

            try:
                processed = self._apply_watermark(self._original_images[i])
                frame._image = processed
            except Exception:
                pass

        self._safe_canvas_update()
        self.update_preview()

    def _apply_watermark(self, image: Image.Image) -> Image.Image:
        """이미지에 워터마크 적용"""
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        result = image.copy()

        is_text = self._type_combo.GetSelection() == 0
        opacity = self._opacity_slider.GetValue() / 100.0
        position_idx = self._pos_combo.GetSelection()
        position = self.POSITIONS[position_idx][1]
        margin = self._margin_spin.GetValue()

        if is_text:
            watermark = self._create_text_watermark()
        else:
            if self._watermark_image is None:
                return result
            watermark = self._watermark_image.copy()
            # 크기 조정
            max_size = min(image.width, image.height) // 4
            if watermark.width > max_size or watermark.height > max_size:
                ratio = max_size / max(watermark.width, watermark.height)
                new_w = int(watermark.width * ratio)
                new_h = int(watermark.height * ratio)
                watermark = watermark.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # 투명도 적용
        if opacity < 1.0:
            alpha = watermark.split()[3]
            alpha = alpha.point(lambda x: int(x * opacity))
            watermark.putalpha(alpha)

        # 타일링 또는 단일 위치
        if position == "tiling":
            result = self._apply_tiling(result, watermark, margin)
        else:
            x, y = self._calculate_position(image.size, watermark.size, position, margin)
            result.paste(watermark, (x, y), watermark)

        return result

    def _create_text_watermark(self) -> Image.Image:
        """텍스트 워터마크 이미지 생성"""
        text = self._text_input.GetValue()
        if not text:
            return Image.new('RGBA', (1, 1), (0, 0, 0, 0))

        font_size = self._font_spin.GetValue()

        # 폰트 로드
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
            except (OSError, IOError):
                font = ImageFont.load_default()

        # 텍스트 크기 측정
        temp_img = Image.new('RGBA', (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)
        bbox = temp_draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0] + 20
        text_h = bbox[3] - bbox[1] + 10

        # 워터마크 이미지 생성
        watermark = Image.new('RGBA', (text_w, text_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark)

        color = (
            self._text_color.Red(),
            self._text_color.Green(),
            self._text_color.Blue(),
            255
        )

        # 그림자
        shadow_color = (0, 0, 0, 128)
        draw.text((11, 6), text, font=font, fill=shadow_color)

        # 텍스트
        draw.text((10, 5), text, font=font, fill=color)

        return watermark

    def _calculate_position(self, image_size: tuple, watermark_size: tuple,
                           position: str, margin: int) -> tuple:
        """위치 계산"""
        img_w, img_h = image_size
        wm_w, wm_h = watermark_size

        positions = {
            "top_left": (margin, margin),
            "top_center": ((img_w - wm_w) // 2, margin),
            "top_right": (img_w - wm_w - margin, margin),
            "middle_left": (margin, (img_h - wm_h) // 2),
            "middle_center": ((img_w - wm_w) // 2, (img_h - wm_h) // 2),
            "middle_right": (img_w - wm_w - margin, (img_h - wm_h) // 2),
            "bottom_left": (margin, img_h - wm_h - margin),
            "bottom_center": ((img_w - wm_w) // 2, img_h - wm_h - margin),
            "bottom_right": (img_w - wm_w - margin, img_h - wm_h - margin),
        }

        return positions.get(position, (margin, margin))

    def _apply_tiling(self, image: Image.Image, watermark: Image.Image,
                      margin: int) -> Image.Image:
        """타일링 패턴 적용"""
        result = image.copy()
        wm_w, wm_h = watermark.size

        spacing = max(wm_w, wm_h) + margin * 2

        y = margin
        row = 0
        while y < image.height:
            x_offset = spacing // 2 if row % 2 == 1 else 0
            x = margin + x_offset

            while x < image.width:
                result.paste(watermark, (x, y), watermark)
                x += spacing

            y += spacing
            row += 1

        return result

    def _on_clear(self, event):
        """초기화"""
        self._text_input.SetValue("")
        self._watermark_image = None
        self._watermark_path = None
        translations = getattr(self._main_window, '_translations', None)
        image_btn_text = translations.tr("watermark_image_btn") if translations else "이미지"
        self._image_btn.SetLabel(f"{image_btn_text} 선택...")

        for i, frame in enumerate(self.frames):
            if i < len(self._original_images) and self._original_images[i] is not None:
                try:
                    frame._image = self._original_images[i].copy()
                except Exception:
                    pass

        self._safe_canvas_update()

    def _on_apply(self, event):
        """적용"""
        self._on_deactivated()
        if hasattr(self._main_window, '_is_modified'):
            self._main_window._is_modified = True
        if hasattr(self._main_window, '_update_info_bar'):
            self._main_window._update_info_bar()
        super()._on_apply(event)
        self.hide_from_canvas()

    def _on_cancel(self, event):
        """취소"""
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
        self._text_input.SetValue("© GIF Editor")
        self._font_spin.SetValue(16)
        self._text_color = wx.Colour(255, 255, 255)
        self._pos_combo.SetSelection(8)
        self._opacity_slider.SetValue(50)
        self._margin_spin.SetValue(10)
        self._watermark_image = None
