"""
SpeechBubbleToolbar - 말풍선 인라인 툴바 (wxPython 버전)
"""
import wx
from PIL import Image
from typing import TYPE_CHECKING, Optional, List
from .base_toolbar_wx import InlineToolbarBase

if TYPE_CHECKING:
    from ..main_window import MainWindow

try:
    from ...core.overlays import SpeechBubble, SpeechBubbleConfig, BubbleStyle, TailDirection
except ImportError:
    SpeechBubble = None
    SpeechBubbleConfig = None
    BubbleStyle = None
    TailDirection = None


class SpeechBubbleToolbar(InlineToolbarBase):
    """말풍선 인라인 툴바 (wxPython)"""

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(main_window, parent)
        self._original_images: List[Optional[Image.Image]] = []
        self._bg_color = wx.Colour(255, 255, 255)
        self._text_color = wx.Colour(0, 0, 0)
        self._border_color = wx.Colour(0, 0, 0)
        self._bubble_x = 50
        self._bubble_y = 50
        self._bubble_width = 150
        self._bubble_height = 80
        self._updating_from_canvas = False
        self._setup_controls()

    def _setup_controls(self):
        """컨트롤 설정"""
        translations = getattr(self._main_window, '_translations', None)

        # 적용 대상
        target_tooltip = translations.tr("target_tooltip") if translations else "적용 대상 프레임"
        self._target_combo = self.add_target_combo(self._on_setting_changed, tooltip=target_tooltip)

        self.add_separator()

        # 텍스트 입력
        text_tooltip = translations.tr("speech_bubble_text") if translations else "텍스트 입력"
        self.add_icon_label("text", 20, text_tooltip)

        self._text_input = wx.TextCtrl(self._controls_widget)
        placeholder = translations.tr("speech_bubble_text_placeholder") if translations else "텍스트"
        self._text_input.SetHint(placeholder)
        self._text_input.SetValue("Hello!")
        self._text_input.SetMinSize((120, -1))
        self._text_input.Bind(wx.EVT_TEXT, lambda e: self._on_setting_changed())
        self.add_control(self._text_input)

        # 폰트 크기
        font_tooltip = translations.tr("speech_bubble_font_size") if translations else "폰트 크기"
        self.add_icon_label("font_size", 20, font_tooltip)

        self._font_spin = wx.SpinCtrl(self._controls_widget, min=8, max=72, initial=16)
        self._font_spin.SetMinSize((70, -1))
        self._font_spin.SetToolTip(translations.tr("speech_bubble_font_size") if translations else "폰트 크기")
        self._font_spin.Bind(wx.EVT_SPINCTRL, lambda e: self._on_setting_changed())
        self.add_control(self._font_spin)

        # 스타일
        style_tooltip = translations.tr("speech_bubble_style") if translations else "말풍선 스타일"
        self.add_icon_label("style", 20, style_tooltip)

        if SpeechBubble:
            self._style_names = SpeechBubble.get_style_names()
            style_choices = [name for name, _ in self._style_names]
        else:
            self._style_names = [("기본", 0)]
            style_choices = ["기본"]

        self._style_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY, choices=style_choices)
        self._style_combo.SetSelection(0)
        self._style_combo.SetMinSize((80, -1))
        self._style_combo.SetToolTip(translations.tr("speech_bubble_style") if translations else "스타일")
        self._style_combo.Bind(wx.EVT_COMBOBOX, lambda e: self._on_setting_changed())
        self.add_control(self._style_combo)

        # 꼬리 방향
        if SpeechBubble:
            self._tail_directions = SpeechBubble.get_tail_directions()
            tail_choices = [name for name, _ in self._tail_directions]
        else:
            self._tail_directions = [("아래", 0)]
            tail_choices = ["아래"]

        self._tail_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY, choices=tail_choices)
        self._tail_combo.SetSelection(0)
        self._tail_combo.SetMinSize((70, -1))
        self._tail_combo.SetToolTip(translations.tr("speech_bubble_tail") if translations else "꼬리 방향")
        self._tail_combo.Bind(wx.EVT_COMBOBOX, lambda e: self._on_setting_changed())
        self.add_control(self._tail_combo)

        # 배경색
        self._bg_btn = wx.ColourPickerCtrl(self._controls_widget, colour=self._bg_color)
        self._bg_btn.SetMinSize((40, 30))
        bg_tooltip = translations.tr("speech_bubble_bg_color") if translations else "배경색"
        self._bg_btn.SetToolTip(bg_tooltip)
        self._bg_btn.Bind(wx.EVT_COLOURPICKER_CHANGED, self._on_bg_color_changed)
        self.add_control(self._bg_btn)

        # 텍스트색
        self._text_btn = wx.ColourPickerCtrl(self._controls_widget, colour=self._text_color)
        self._text_btn.SetMinSize((40, 30))
        text_color_tooltip = translations.tr("speech_bubble_text_color") if translations else "텍스트 색상"
        self._text_btn.SetToolTip(text_color_tooltip)
        self._text_btn.Bind(wx.EVT_COLOURPICKER_CHANGED, self._on_text_color_changed)
        self.add_control(self._text_btn)

    def _on_activated(self):
        """툴바 활성화"""
        if not self.frames or getattr(self.frames, 'is_empty', False):
            return

        # 원본 이미지 저장
        self._original_images = self._snapshot_original_images()

        if not getattr(self.frames, 'is_empty', True):
            w = getattr(self.frames, 'width', 100)
            h = getattr(self.frames, 'height', 100)
            default_x = w // 4
            default_y = h // 6

            self._bubble_x = default_x
            self._bubble_y = default_y
            self._bubble_width = 150
            self._bubble_height = 80

        # 캔버스 말풍선 모드 시작
        canvas = self._safe_get_canvas()
        if canvas:
            try:
                # wxPython: Bind 방식으로 이벤트 연결
                from ...utils.wx_events import EVT_SPEECH_BUBBLE_CHANGED
                canvas.Bind(EVT_SPEECH_BUBBLE_CHANGED, self._on_canvas_speech_bubble_changed)
                if hasattr(canvas, 'start_speech_bubble_mode'):
                    canvas.start_speech_bubble_mode(
                        self._bubble_x, self._bubble_y,
                        self._bubble_width, self._bubble_height
                    )
            except Exception:
                pass

        self._update_preview()

    def _on_deactivated(self):
        """툴바 비활성화"""
        self._clear_original_images()

        canvas = self._safe_get_canvas()
        if canvas:
            try:
                # wxPython: Unbind 방식으로 이벤트 연결 해제
                from ...utils.wx_events import EVT_SPEECH_BUBBLE_CHANGED
                canvas.Unbind(EVT_SPEECH_BUBBLE_CHANGED)
            except Exception:
                pass
            try:
                if hasattr(canvas, 'stop_speech_bubble_mode'):
                    canvas.stop_speech_bubble_mode()
            except Exception:
                pass

    def _on_setting_changed(self):
        """설정 변경됨 — 현재 프레임을 즉시 원본 복원 (오버레이가 새 스타일을 그리므로 겹침 방지)"""
        if self._original_images and self.frames and not getattr(self.frames, 'is_empty', True):
            self._restore_current_original_image()

        if not self._updating_from_canvas:
            self._update_canvas_speech_bubble_rect()
        self._preview_timer.Start(100, wx.TIMER_ONE_SHOT)

    def _update_canvas_speech_bubble_rect(self):
        """캔버스의 말풍선 영역 업데이트"""
        canvas = self._safe_get_canvas()
        if not canvas:
            return

        if hasattr(canvas, '_speech_bubble_mode') and canvas._speech_bubble_mode:
            try:
                if hasattr(canvas, 'update_speech_bubble_rect'):
                    canvas.update_speech_bubble_rect(
                        self._bubble_x,
                        self._bubble_y,
                        self._bubble_width,
                        self._bubble_height
                    )
            except Exception:
                pass

    def _on_canvas_speech_bubble_changed(self, event):
        """캔버스에서 말풍선이 변경됨 (wxPython 이벤트)"""
        self._updating_from_canvas = True
        self._bubble_x = event.x
        self._bubble_y = event.y
        self._bubble_width = event.width
        self._bubble_height = event.height
        self._updating_from_canvas = False
        self._preview_timer.Start(100, wx.TIMER_ONE_SHOT)

    def _on_bg_color_changed(self, event):
        """배경색 변경"""
        self._bg_color = event.GetColour()
        self._on_setting_changed()

    def _on_text_color_changed(self, event):
        """텍스트색 변경"""
        self._text_color = event.GetColour()
        self._on_setting_changed()

    def _update_preview(self):
        """미리보기 업데이트"""
        if not self._original_images:
            return

        if not self.frames or getattr(self.frames, 'is_empty', False):
            return

        bubble_img = self._create_bubble()
        self._apply_frame_processor(
            self._target_combo.GetSelection(),
            lambda original, _index, _should_apply: self._apply_bubble(original, bubble_img),
            preview_current=True,
        )

        self._safe_canvas_update()
        self.update_preview()

    def _create_bubble(self) -> Image.Image:
        """말풍선 이미지 생성"""
        if not SpeechBubble:
            # Fallback: 간단한 말풍선
            bubble = Image.new('RGBA', (self._bubble_width, self._bubble_height), (255, 255, 255, 200))
            return bubble

        style = self._style_names[self._style_combo.GetSelection()][1]
        tail = self._tail_directions[self._tail_combo.GetSelection()][1]
        text = self._text_input.GetValue()
        font_size = self._font_spin.GetValue()

        config = SpeechBubbleConfig(
            style=style,
            tail_direction=tail,
            text=text,
            font_size=font_size,
            text_color=(
                self._text_color.Red(),
                self._text_color.Green(),
                self._text_color.Blue(),
                255
            ),
            bg_color=(
                self._bg_color.Red(),
                self._bg_color.Green(),
                self._bg_color.Blue(),
                255
            ),
            border_color=(
                self._border_color.Red(),
                self._border_color.Green(),
                self._border_color.Blue(),
                255
            ),
        )

        w = self._bubble_width
        h = self._bubble_height

        return SpeechBubble.create(w, h, config)

    def _apply_bubble(self, image: Image.Image, bubble: Image.Image) -> Image.Image:
        """이미지에 말풍선 적용"""
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        result = image.copy()
        x = self._bubble_x
        y = self._bubble_y
        result.paste(bubble, (x, y), bubble)

        return result

    def _on_clear(self, event):
        """초기화 — 스티커와 동일 구조 (좌표/크기/텍스트 리셋 + 캔버스 업데이트)"""
        self._text_input.SetValue("")

        # 좌표/크기 초기화
        w = getattr(self.frames, 'width', 100)
        h = getattr(self.frames, 'height', 100)
        self._bubble_x = w // 4
        self._bubble_y = h // 6
        self._bubble_width = 150
        self._bubble_height = 80
        self._update_canvas_speech_bubble_rect()

        self._restore_original_images()
        self._safe_canvas_update()

    def _on_apply(self, event):
        """적용"""
        bubble_img = self._create_bubble()
        self._apply_frame_processor(
            self._target_combo.GetSelection(),
            lambda original, _index, _should_apply: self._apply_bubble(original, bubble_img),
        )

        self._on_deactivated()
        self._finish_apply()

    def _on_cancel(self, event):
        """취소"""
        self._restore_original_images()
        self._finish_cancel()

    def reset_to_default(self):
        """기본값으로 초기화"""
        self._text_input.SetValue("Hello!")
        self._style_combo.SetSelection(0)
        self._tail_combo.SetSelection(0)
        self._font_spin.SetValue(16)
        self._bg_color = wx.Colour(255, 255, 255)
        self._text_color = wx.Colour(0, 0, 0)
        self._bubble_width = 150
        self._bubble_height = 80
        self._target_combo.SetSelection(1)
