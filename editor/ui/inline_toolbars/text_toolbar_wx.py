"""
TextToolbar - 텍스트 추가 인라인 툴바 (wxPython 버전)
"""
import wx
from PIL import Image, ImageDraw, ImageFont
from typing import TYPE_CHECKING, Optional, List
from .base_toolbar_wx import InlineToolbarBase

if TYPE_CHECKING:
    from ..main_window import MainWindow

try:
    from ...core.animation_effects import AnimationType, AnimationPreset, AnimatedOverlay
except ImportError:
    AnimationType = None
    AnimationPreset = None
    AnimatedOverlay = None


class TextToolbar(InlineToolbarBase):
    """텍스트 추가 인라인 툴바 (wxPython)

    텍스트 입력, 크기, 색상 설정을 제공합니다.
    캔버스에서 드래그로 위치를 지정합니다.
    """

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(main_window, parent)
        self._original_images: List[Optional[Image.Image]] = []
        self._text_color = wx.Colour(255, 255, 255)
        self._outline_color = wx.Colour(0, 0, 0)
        self._outline_enabled = False
        self._blink_enabled = False
        self._blink_interval = 0.3
        self._text_x = 50
        self._text_y = 50
        self._text_width = 100
        self._text_height = 40
        self._base_font_size = 32
        self._animation_type = AnimationType.NONE if AnimationType else 0
        self._is_low_end_mode = getattr(main_window, '_is_low_end_mode', False)
        self._preview_delay = getattr(main_window, '_preview_delay', 100)
        self._updating_from_canvas = False
        self._setup_controls()

    def _setup_controls(self):
        """컨트롤 설정"""
        translations = getattr(self._main_window, '_translations', None)

        # 적용 대상
        target_tooltip = translations.tr("target_tooltip") if translations else "적용 대상 프레임"
        self.add_icon_label("target", 20, target_tooltip)

        target_choices = []
        if translations:
            target_choices = [translations.tr("target_all"), translations.tr("target_selected"), translations.tr("target_current")]
        else:
            target_choices = ["모두", "선택", "현재"]

        self._target_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY, choices=target_choices)
        self._target_combo.SetSelection(1)
        self._target_combo.SetMinSize((70, -1))
        self._target_combo.SetToolTip(target_tooltip)
        self._target_combo.Bind(wx.EVT_COMBOBOX, lambda e: self._on_setting_changed())
        self.add_control(self._target_combo)

        self.add_separator()

        # 텍스트 입력
        text_input_tooltip = translations.tr("text_input") if translations else "텍스트 입력"
        self.add_icon_label("text", 20, text_input_tooltip)

        self._text_input = wx.TextCtrl(self._controls_widget)
        text_placeholder = translations.tr("text_placeholder") if translations else "텍스트"
        self._text_input.SetHint(text_placeholder)
        self._text_input.SetValue("Hello!")
        self._text_input.SetMinSize((120, -1))
        self._text_input.Bind(wx.EVT_TEXT, lambda e: self._on_setting_changed())
        self.add_control(self._text_input)

        # 폰트 크기
        font_size_tooltip = translations.tr("text_font_size") if translations else "폰트 크기"
        self.add_icon_label("font_size", 20, font_size_tooltip)

        self._size_spin = wx.SpinCtrl(self._controls_widget, min=8, max=200, initial=32)
        self._size_spin.SetMinSize((70, -1))
        self._size_spin.SetToolTip(font_size_tooltip)
        self._size_spin.Bind(wx.EVT_SPINCTRL, lambda e: self._on_setting_changed())
        self.add_control(self._size_spin)

        # 폰트 선택
        self._font_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY)
        font_select_tooltip = translations.tr("text_font_select") if translations else "폰트 선택"
        self._font_combo.SetToolTip(font_select_tooltip)
        self._load_system_fonts()
        self._font_combo.SetMinSize((100, -1))
        self._font_combo.Bind(wx.EVT_COMBOBOX, lambda e: self._on_setting_changed())
        self.add_control(self._font_combo)

        # 색상
        self._color_btn = wx.ColourPickerCtrl(self._controls_widget, colour=self._text_color)
        self._color_btn.SetMinSize((40, 30))
        text_color_tooltip = translations.tr("text_color") if translations else "텍스트 색상"
        self._color_btn.SetToolTip(text_color_tooltip)
        self._color_btn.Bind(wx.EVT_COLOURPICKER_CHANGED, self._on_color_changed)
        self.add_control(self._color_btn)

        # 아웃라인
        outline_tooltip = translations.tr("text_outline") if translations else "텍스트 테두리"
        self.add_icon_label("outline", 28, outline_tooltip)

        self._outline_check = wx.CheckBox(self._controls_widget)
        self._outline_check.SetValue(False)
        self._outline_check.SetToolTip(outline_tooltip)
        self._outline_check.Bind(wx.EVT_CHECKBOX, self._on_outline_changed)
        self.add_control(self._outline_check)

        self._outline_width_spin = wx.SpinCtrl(self._controls_widget, min=1, max=20, initial=2)
        self._outline_width_spin.SetMinSize((70, -1))
        outline_width_tooltip = translations.tr("text_outline_width") if translations else "외곽선 두께"
        self._outline_width_spin.SetToolTip(outline_width_tooltip)
        self._outline_width_spin.Enable(False)
        self._outline_width_spin.Bind(wx.EVT_SPINCTRL, lambda e: self._on_setting_changed())
        self.add_control(self._outline_width_spin)

        self.add_separator()

        # 애니메이션
        if AnimationPreset:
            anim_tooltip = translations.tr("text_animation") if translations else "애니메이션 효과"
            self.add_icon_label("animation", 20, anim_tooltip)

            self._anim_names = AnimationPreset.get_animation_names()
            anim_choices = [name for name, _ in self._anim_names]
            self._anim_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY, choices=anim_choices)
            self._anim_combo.SetSelection(0)
            self._anim_combo.SetMinSize((100, -1))
            self._anim_combo.SetToolTip("애니메이션")
            self._anim_combo.Bind(wx.EVT_COMBOBOX, self._on_animation_changed)
            self.add_control(self._anim_combo)

        # 깜빡임
        blink_tooltip = translations.tr("text_blink") if translations else "깜빡임 효과"
        self.add_icon_label("blink", 20, blink_tooltip)

        self._blink_check = wx.CheckBox(self._controls_widget)
        self._blink_check.SetValue(False)
        blink_check_tooltip = translations.tr("text_blink") if translations else "깜빡임"
        self._blink_check.SetToolTip(blink_check_tooltip)
        self._blink_check.Bind(wx.EVT_CHECKBOX, self._on_blink_changed)
        self.add_control(self._blink_check)

        # 깜빡임 간격
        blink_interval_tooltip = translations.tr("text_blink_interval") if translations else "깜빡임 간격"
        self.add_icon_label("clock", 20, blink_interval_tooltip)

        self._blink_spin = wx.SpinCtrlDouble(self._controls_widget, min=0.1, max=5.0, initial=0.3, inc=0.1)
        self._blink_spin.SetMinSize((70, -1))
        self._blink_spin.SetToolTip(blink_interval_tooltip)
        self._blink_spin.SetDigits(1)
        self._blink_spin.Enable(False)
        self._blink_spin.Bind(wx.EVT_SPINCTRLDOUBLE, self._on_blink_interval_changed)
        self.add_control(self._blink_spin)

    def _load_system_fonts(self):
        """시스템 폰트 목록 로드"""
        recommended_fonts = [
            "Arial", "Malgun Gothic", "맑은 고딕", "Gulim", "굴림",
            "Dotum", "돋움", "Batang", "바탕", "NanumGothic", "나눔고딕",
            "NanumBarunGothic", "나눔바른고딕", "Noto Sans KR", "Noto Sans CJK KR",
            "AppleGothic", "Helvetica", "Times New Roman", "Verdana",
            "Tahoma", "Georgia", "Comic Sans MS", "Impact", "Courier New"
        ]

        # wxPython의 폰트 열거자
        font_enum = wx.FontEnumerator()
        font_enum.EnumerateFacenames()
        font_families = font_enum.GetFacenames()

        added = set()
        for font in recommended_fonts:
            if font in font_families and font not in added:
                self._font_combo.Append(font)
                added.add(font)

        for font in sorted(font_families):
            if font not in added and not font.startswith("@"):
                self._font_combo.Append(font)

        # 기본 폰트 선택
        default_idx = self._font_combo.FindString("Arial")
        if default_idx < 0:
            default_idx = self._font_combo.FindString("Malgun Gothic")
        if default_idx < 0:
            default_idx = self._font_combo.FindString("맑은 고딕")
        if default_idx >= 0:
            self._font_combo.SetSelection(default_idx)
        elif self._font_combo.GetCount() > 0:
            self._font_combo.SetSelection(0)

    def _get_font_path(self) -> str:
        """선택된 폰트의 경로 반환"""
        font_name = self._font_combo.GetStringSelection()

        font_map = {
            "Arial": "arial.ttf",
            "Malgun Gothic": "malgun.ttf",
            "맑은 고딕": "malgun.ttf",
            "Gulim": "gulim.ttc",
            "굴림": "gulim.ttc",
            "Dotum": "dotum.ttc",
            "돋움": "dotum.ttc",
            "Batang": "batang.ttc",
            "바탕": "batang.ttc",
            "Times New Roman": "times.ttf",
            "Verdana": "verdana.ttf",
            "Tahoma": "tahoma.ttf",
            "Georgia": "georgia.ttf",
            "Comic Sans MS": "comic.ttf",
            "Impact": "impact.ttf",
            "Courier New": "cour.ttf",
        }

        import os
        windows_fonts = "C:/Windows/Fonts/"

        if font_name in font_map:
            font_file = font_map[font_name]
            font_path = windows_fonts + font_file
            if os.path.exists(font_path):
                return font_path

        possible_names = [
            font_name.lower().replace(" ", "") + ".ttf",
            font_name.lower().replace(" ", "") + ".ttc",
            font_name.lower() + ".ttf",
            font_name.lower() + ".ttc",
        ]

        for name in possible_names:
            font_path = windows_fonts + name
            if os.path.exists(font_path):
                return font_path

        return "arial.ttf"

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

        # 캔버스 이벤트 연결 (wxPython 방식)
        canvas = self._safe_get_canvas()
        if canvas:
            try:
                from ...utils.wx_events import EVT_TEXT_MOVED, EVT_TEXT_RESIZED
                canvas.Bind(EVT_TEXT_MOVED, self._on_canvas_text_moved)
                canvas.Bind(EVT_TEXT_RESIZED, self._on_canvas_text_resized)
            except Exception:
                pass

        if not self._text_input.GetValue():
            self._text_input.SetValue("텍스트")

        self._base_font_size = self._size_spin.GetValue()
        self._update_text_bounds()
        self._update_canvas_text_rect()
        self._update_preview()

    def _on_deactivated(self):
        """툴바 비활성화"""
        self._original_images = []
        self._preview_timer.Stop()

        canvas = self._safe_get_canvas()
        if canvas:
            try:
                # wxPython: Unbind 방식으로 이벤트 연결 해제
                from ...utils.wx_events import EVT_TEXT_MOVED, EVT_TEXT_RESIZED
                canvas.Unbind(EVT_TEXT_MOVED, handler=self._on_canvas_text_moved)
                canvas.Unbind(EVT_TEXT_RESIZED, handler=self._on_canvas_text_resized)
            except Exception:
                pass

            if hasattr(canvas, 'stop_text_edit_mode'):
                canvas.stop_text_edit_mode()

    def _on_setting_changed(self):
        """설정 변경됨"""
        self._update_text_bounds()
        self._update_canvas_text_rect()
        self._preview_timer.Start(self._preview_delay, wx.TIMER_ONE_SHOT)

    def _update_text_bounds(self):
        """텍스트 경계 크기 계산"""
        text = self._text_input.GetValue()
        if not text:
            self._text_width = 20
            self._text_height = 20
            return

        font_size = self._size_spin.GetValue()

        try:
            font = ImageFont.truetype(self._get_font_path(), font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

        bbox = font.getbbox(text)
        self._text_width = bbox[2] - bbox[0] + max(2, font_size // 15) * 2 + 10
        self._text_height = bbox[3] - bbox[1] + max(2, font_size // 15) * 2 + 10

    def _update_canvas_text_rect(self):
        """캔버스에 텍스트 영역 업데이트"""
        canvas = self._safe_get_canvas()
        if not canvas:
            return

        try:
            if hasattr(canvas, 'start_text_edit_mode'):
                canvas.start_text_edit_mode(
                    self._text_x, self._text_y,
                    self._text_width, self._text_height,
                    self._size_spin.GetValue()
                )
        except Exception:
            pass

    def _on_canvas_text_moved(self, event):
        """캔버스에서 텍스트가 이동됨 (wxPython 이벤트)"""
        self._updating_from_canvas = True
        self._text_x = event.x
        self._text_y = event.y
        self._updating_from_canvas = False
        self._preview_timer.Start(self._preview_delay, wx.TIMER_ONE_SHOT)

    def _on_canvas_text_resized(self, event):
        """캔버스에서 텍스트 크기가 변경됨 (wxPython 이벤트)

        원본 PyQt6 로직: 캔버스가 리사이즈 시 폰트 크기를 계산하여 직접 전달
        """
        font_size = event.font_size

        self._updating_from_canvas = True
        self._size_spin.SetValue(font_size)
        self._base_font_size = font_size  # 기준 폰트 크기 업데이트
        self._updating_from_canvas = False
        self._update_text_bounds()
        self._update_canvas_text_rect()  # 캔버스 영역도 업데이트
        self._preview_timer.Start(self._preview_delay, wx.TIMER_ONE_SHOT)

    def _on_outline_changed(self, event):
        """아웃라인 토글 변경"""
        self._outline_enabled = self._outline_check.GetValue()
        self._outline_width_spin.Enable(self._outline_enabled)
        self._preview_timer.Start(self._preview_delay, wx.TIMER_ONE_SHOT)

    def _on_animation_changed(self, event):
        """애니메이션 타입 변경"""
        if AnimationType and hasattr(self, '_anim_combo'):
            index = self._anim_combo.GetSelection()
            if 0 <= index < len(self._anim_names):
                self._animation_type = self._anim_names[index][1]
        self._preview_timer.Start(self._preview_delay, wx.TIMER_ONE_SHOT)

    def _on_blink_changed(self, event):
        """깜빡임 토글 변경"""
        self._blink_enabled = self._blink_check.GetValue()
        self._blink_spin.Enable(self._blink_enabled)
        self._preview_timer.Start(self._preview_delay, wx.TIMER_ONE_SHOT)

    def _on_blink_interval_changed(self, event):
        """깜빡임 간격 변경"""
        self._blink_interval = self._blink_spin.GetValue()
        self._preview_timer.Start(self._preview_delay, wx.TIMER_ONE_SHOT)

    def _on_color_changed(self, event):
        """색상 변경"""
        self._text_color = event.GetColour()
        self._on_setting_changed()

    def _update_preview(self):
        """미리보기 업데이트"""
        if not self._original_images:
            return

        target = self._target_combo.GetSelection()
        selected_indices = getattr(self.frames, 'selected_indices', set())
        current_idx = getattr(self.frames, 'current_index', 0)

        # 저사양 모드
        if self._is_low_end_mode:
            if current_idx < len(self._original_images) and self._original_images[current_idx] is not None:
                try:
                    processed = self._apply_text(self._original_images[current_idx])
                    if current_idx < len(self.frames):
                        self.frames[current_idx]._image = processed
                except Exception:
                    pass
                self._safe_canvas_update()
                self.update_preview()
            return

        # 애니메이션 모드
        if AnimatedOverlay and self._animation_type != AnimationType.NONE and target == 0:
            self._update_preview_with_animation()
            return

        # Blink 패턴
        blink_pattern = self._calculate_blink_pattern() if self._blink_enabled else None

        for i, frame in enumerate(self.frames):
            if i >= len(self._original_images) or self._original_images[i] is None:
                continue

            should_apply = False
            if target == 0:
                should_apply = True
            elif target == 1:
                should_apply = i in selected_indices
            elif target == 2:
                should_apply = i == current_idx

            show_preview = should_apply or (i == current_idx)

            try:
                if show_preview:
                    if blink_pattern and should_apply:
                        if blink_pattern[i]:
                            processed = self._apply_text(self._original_images[i])
                            frame._image = processed
                        else:
                            frame._image = self._original_images[i].copy()
                    else:
                        processed = self._apply_text(self._original_images[i])
                        frame._image = processed
                else:
                    frame._image = self._original_images[i].copy()
            except Exception:
                pass

        self._safe_canvas_update()
        self.update_preview()

    def _update_preview_with_animation(self):
        """애니메이션이 적용된 미리보기"""
        if not AnimatedOverlay:
            return

        text = self._text_input.GetValue()
        if not text:
            return

        font_size = self._size_spin.GetValue()
        try:
            font = ImageFont.truetype(self._get_font_path(), font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

        text_color = (
            self._text_color.Red(),
            self._text_color.Green(),
            self._text_color.Blue(),
            255
        )

        outline_color = None
        outline_width = 0
        if self._outline_enabled:
            outline_color = (
                self._outline_color.Red(),
                self._outline_color.Green(),
                self._outline_color.Blue(),
                255
            )
            outline_width = self._outline_width_spin.GetValue()

        animated_images = AnimatedOverlay.apply_text_animation(
            base_images=self._original_images,
            text=text,
            position=(self._text_x, self._text_y),
            font=font,
            color=text_color,
            animation_type=self._animation_type,
            start_frame=0,
            duration_frames=None,
            outline_color=outline_color,
            outline_width=outline_width
        )

        for i, frame in enumerate(self.frames):
            if i < len(animated_images) and animated_images[i] is not None:
                try:
                    frame._image = animated_images[i]
                except Exception:
                    pass

        self._safe_canvas_update()
        self.update_preview()

    def _calculate_blink_pattern(self) -> List[bool]:
        """깜빡임 패턴 계산"""
        pattern = []
        interval_ms = self._blink_interval * 1000
        accumulated_time = 0
        show_text = True

        for frame in self.frames:
            pattern.append(show_text)
            accumulated_time += getattr(frame, 'delay_ms', 100)

            if accumulated_time >= interval_ms:
                accumulated_time = 0
                show_text = not show_text

        return pattern

    def _apply_text(self, image: Image.Image) -> Image.Image:
        """이미지에 텍스트 적용"""
        text = self._text_input.GetValue()
        if not text:
            return image.copy()

        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        result = image.copy()
        txt_layer = Image.new('RGBA', result.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_layer)

        font_size = self._size_spin.GetValue()

        try:
            font = ImageFont.truetype(self._get_font_path(), font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

        text_color = (
            self._text_color.Red(),
            self._text_color.Green(),
            self._text_color.Blue(),
            255
        )

        # 아웃라인
        if self._outline_enabled:
            outline_color = (
                self._outline_color.Red(),
                self._outline_color.Green(),
                self._outline_color.Blue(),
                255
            )
            outline_width = self._outline_width_spin.GetValue()
            for dx in range(-outline_width, outline_width + 1):
                for dy in range(-outline_width, outline_width + 1):
                    if dx != 0 or dy != 0:
                        draw.text(
                            (self._text_x + dx, self._text_y + dy),
                            text, font=font, fill=outline_color
                        )

        # 텍스트
        draw.text((self._text_x, self._text_y), text, font=font, fill=text_color)

        return Image.alpha_composite(result, txt_layer)

    def _on_clear(self, event):
        """초기화"""
        self._text_input.SetValue("")

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

        # selected_indices가 property로 리스트를 반환하는지 확인
        if isinstance(selected_indices, (list, tuple)):
            selected_indices = set(selected_indices)

        blink_pattern = self._calculate_blink_pattern() if self._blink_enabled else None

        # 애니메이션 적용
        if AnimatedOverlay and self._animation_type != AnimationType.NONE and target == 0:
            text = self._text_input.GetValue()
            if text:
                font_size = self._size_spin.GetValue()
                try:
                    font = ImageFont.truetype(self._get_font_path(), font_size)
                except (OSError, IOError):
                    font = ImageFont.load_default()

                text_color = (self._text_color.Red(), self._text_color.Green(), self._text_color.Blue(), 255)

                outline_color = None
                outline_width = 0
                if self._outline_enabled:
                    outline_color = (
                        self._outline_color.Red(), self._outline_color.Green(), self._outline_color.Blue(), 255
                    )
                    outline_width = self._outline_width_spin.GetValue()

                animated_images = AnimatedOverlay.apply_text_animation(
                    base_images=self._original_images,
                    text=text,
                    position=(self._text_x, self._text_y),
                    font=font,
                    color=text_color,
                    animation_type=self._animation_type,
                    start_frame=0,
                    duration_frames=None,
                    outline_color=outline_color,
                    outline_width=outline_width
                )

                for i, frame in enumerate(self.frames):
                    if i < len(animated_images) and animated_images[i] is not None:
                        frame._image = animated_images[i]
        else:
            # 일반 적용
            for i, frame in enumerate(self.frames):
                if i >= len(self._original_images) or self._original_images[i] is None:
                    continue

                should_apply = False
                if target == 0:
                    should_apply = True
                elif target == 1:
                    should_apply = i in selected_indices
                elif target == 2:
                    should_apply = i == current_idx

                if should_apply:
                    try:
                        if blink_pattern:
                            if blink_pattern[i]:
                                processed = self._apply_text(self._original_images[i])
                                frame._image = processed
                            else:
                                frame._image = self._original_images[i].copy()
                        else:
                            processed = self._apply_text(self._original_images[i])
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
        self._text_input.SetValue("Hello!")
        self._size_spin.SetValue(32)
        self._base_font_size = 32

        default_idx = self._font_combo.FindString("Arial")
        if default_idx < 0:
            default_idx = self._font_combo.FindString("Malgun Gothic")
        if default_idx < 0:
            default_idx = self._font_combo.FindString("맑은 고딕")
        if default_idx >= 0:
            self._font_combo.SetSelection(default_idx)

        self._text_color = wx.Colour(255, 255, 255)
        self._text_x = 50
        self._text_y = 50
        self._outline_check.SetValue(False)
        self._outline_enabled = False
        self._outline_width_spin.SetValue(2)
        self._outline_width_spin.Enable(False)

        if hasattr(self, '_anim_combo'):
            self._anim_combo.SetSelection(0)
            self._animation_type = AnimationType.NONE if AnimationType else 0

        self._blink_check.SetValue(False)
        self._blink_enabled = False
        self._blink_spin.SetValue(0.3)
        self._blink_interval = 0.3
