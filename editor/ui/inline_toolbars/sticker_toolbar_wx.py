"""
StickerToolbar - 스티커/도형 인라인 툴바 (wxPython 버전)
"""
import wx
import math
from PIL import Image, ImageDraw
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


class StickerToolbar(InlineToolbarBase):
    """스티커/도형 인라인 툴바 (wxPython)

    도형 선택, 크기, 색상 설정을 제공합니다.
    """

    # 도형 목록
    SHAPES = [
        ("shape_rectangle", "rectangle"),
        ("shape_ellipse", "ellipse"),
        ("shape_triangle", "triangle"),
        ("shape_star", "star"),
        ("shape_arrow", "arrow"),
        ("shape_heart", "heart"),
    ]

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(main_window, parent)
        self._original_images: List[Optional[Image.Image]] = []
        self._fill_color = wx.Colour(255, 107, 107)
        self._shape_x = 50
        self._shape_y = 50
        self._animation_type = AnimationType.NONE if AnimationType else 0
        self._updating_from_canvas = False
        self._setup_controls()
        self.set_clear_button_visible(True)

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
        self._target_combo.SetToolTip("적용 대상")
        self._target_combo.Bind(wx.EVT_COMBOBOX, lambda e: self._on_setting_changed())
        self.add_control(self._target_combo)

        self.add_separator()

        # 도형 선택
        sticker_shape_tooltip = translations.tr("sticker_shape") if translations else "스티커 도형"
        self.add_icon_label("sticker", 20, sticker_shape_tooltip)

        shape_names = []
        for key, _ in self.SHAPES:
            shape_name = translations.tr(key) if translations else key
            shape_names.append(shape_name)

        self._shape_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY, choices=shape_names)
        self._shape_combo.SetSelection(0)
        self._shape_combo.SetMinSize((90, -1))
        shape_tooltip = translations.tr("sticker_shape") if translations else "도형"
        self._shape_combo.SetToolTip(shape_tooltip)
        self._shape_combo.Bind(wx.EVT_COMBOBOX, lambda e: self._on_setting_changed())
        self.add_control(self._shape_combo)

        # 크기
        sticker_size_tooltip = translations.tr("sticker_size") if translations else "스티커 크기"
        self.add_icon_label("resize", 28, sticker_size_tooltip)

        self._size_spin = wx.SpinCtrl(self._controls_widget, min=10, max=500, initial=80)
        self._size_spin.SetMinSize((70, -1))
        size_tooltip = translations.tr("sticker_size_tooltip") if translations else "크기"
        self._size_spin.SetToolTip(size_tooltip)
        self._size_spin.Bind(wx.EVT_SPINCTRL, lambda e: self._on_setting_changed())
        self.add_control(self._size_spin)

        # 색상
        self._color_btn = wx.ColourPickerCtrl(self._controls_widget, colour=self._fill_color)
        self._color_btn.SetMinSize((40, 30))
        fill_color_tooltip = translations.tr("sticker_fill_color") if translations else "채우기 색상"
        self._color_btn.SetToolTip(fill_color_tooltip)
        self._color_btn.Bind(wx.EVT_COLOURPICKER_CHANGED, self._on_color_changed)
        self.add_control(self._color_btn)

        self.add_separator()

        # 애니메이션
        if AnimationPreset:
            self.add_icon_label("animation", 20, "애니메이션 효과")
            self._anim_names = [(name, atype) for name, atype in AnimationPreset.get_animation_names()
                               if atype != AnimationType.TYPING]
            anim_choices = [name for name, _ in self._anim_names]
            self._anim_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY, choices=anim_choices)
            self._anim_combo.SetSelection(0)
            self._anim_combo.SetMinSize((100, -1))
            self._anim_combo.SetToolTip("애니메이션")
            self._anim_combo.Bind(wx.EVT_COMBOBOX, self._on_animation_changed)
            self.add_control(self._anim_combo)

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
        except Exception as e:
            print(f"원본 이미지 저장 오류: {e}")
            self._original_images = []

        # 캔버스 스티커 모드 시작
        canvas = self._safe_get_canvas()
        if canvas:
            try:
                # wxPython: Bind 방식으로 이벤트 연결
                from ...utils.wx_events import EVT_STICKER_CHANGED
                canvas.Bind(EVT_STICKER_CHANGED, self._on_canvas_sticker_changed)
                print("[StickerToolbar] 캔버스 스티커 이벤트 바인딩 완료")

                if hasattr(canvas, 'start_sticker_mode'):
                    canvas.start_sticker_mode(
                        self._shape_x, self._shape_y, self._size_spin.GetValue()
                    )
            except Exception as e:
                print(f"[StickerToolbar] 스티커 모드 시작 오류: {e}")

        self._update_preview()

    def _on_deactivated(self):
        """툴바 비활성화"""
        self._original_images = []
        self._preview_timer.Stop()

        canvas = self._safe_get_canvas()
        if canvas:
            try:
                # wxPython: Unbind 방식으로 이벤트 연결 해제
                from ...utils.wx_events import EVT_STICKER_CHANGED
                canvas.Unbind(EVT_STICKER_CHANGED)
                print("[StickerToolbar] 캔버스 스티커 이벤트 언바인딩 완료")
            except:
                pass
            try:
                if hasattr(canvas, 'stop_sticker_mode'):
                    canvas.stop_sticker_mode()
            except Exception as e:
                print(f"스티커 모드 종료 오류: {e}")

    def _on_setting_changed(self):
        """설정 변경됨"""
        if not self._updating_from_canvas:
            self._update_canvas_sticker_rect()
        self._preview_timer.Start(100, wx.TIMER_ONE_SHOT)

    def _update_canvas_sticker_rect(self):
        """캔버스의 스티커 영역 업데이트"""
        canvas = self._safe_get_canvas()
        if canvas and hasattr(canvas, '_sticker_mode') and canvas._sticker_mode:
            try:
                if hasattr(canvas, 'update_sticker_rect'):
                    canvas.update_sticker_rect(
                        self._shape_x,
                        self._shape_y,
                        self._size_spin.GetValue()
                    )
            except Exception as e:
                print(f"스티커 영역 업데이트 오류: {e}")

    def _on_canvas_sticker_changed(self, event):
        """캔버스에서 스티커가 변경됨 (wxPython 이벤트)"""
        print(f"[StickerToolbar] _on_canvas_sticker_changed: x={event.x}, y={event.y}, w={event.width}, h={event.height}")
        self._updating_from_canvas = True
        self._shape_x = event.x
        self._shape_y = event.y
        # width와 height 중 큰 값을 size로 사용
        size = max(event.width, event.height)
        self._size_spin.SetValue(size)
        self._updating_from_canvas = False
        self._preview_timer.Start(100, wx.TIMER_ONE_SHOT)

    def _on_animation_changed(self, event):
        """애니메이션 타입 변경"""
        if AnimationType and hasattr(self, '_anim_combo'):
            index = self._anim_combo.GetSelection()
            if 0 <= index < len(self._anim_names):
                self._animation_type = self._anim_names[index][1]
        self._preview_timer.Start(50, wx.TIMER_ONE_SHOT)

    def _on_color_changed(self, event):
        """색상 변경"""
        self._fill_color = event.GetColour()
        self._on_setting_changed()

    def _update_preview(self):
        """미리보기 업데이트"""
        if not self._original_images:
            return

        if not self.frames or getattr(self.frames, 'is_empty', False):
            return

        target = self._target_combo.GetSelection()
        selected_indices = getattr(self.frames, 'selected_indices', set())
        current_idx = getattr(self.frames, 'current_index', 0)

        # 애니메이션 모드
        if AnimatedOverlay and self._animation_type != AnimationType.NONE and target == 0:
            self._update_preview_with_animation()
            return

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
                    processed = self._apply_shape(self._original_images[i])
                    frame._image = processed
                else:
                    frame._image = self._original_images[i].copy()
            except Exception as e:
                print(f"스티커 처리 오류 (프레임 {i}): {e}")

        self._safe_canvas_update()
        self.update_preview()

    def _update_preview_with_animation(self):
        """애니메이션이 적용된 미리보기"""
        if not AnimatedOverlay:
            return

        size = self._size_spin.GetValue()
        sticker_img = self._create_shape_image(size)

        animated_images = AnimatedOverlay.apply_sticker_animation(
            base_images=self._original_images,
            sticker=sticker_img,
            position=(self._shape_x, self._shape_y),
            animation_type=self._animation_type,
            start_frame=0,
            duration_frames=None
        )

        for i, frame in enumerate(self.frames):
            if i < len(animated_images):
                frame._image = animated_images[i]

        self._safe_canvas_update()
        self.update_preview()

    def _create_shape_image(self, size: int) -> Image.Image:
        """도형 이미지 생성"""
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        fill = (
            self._fill_color.Red(),
            self._fill_color.Green(),
            self._fill_color.Blue(),
            255
        )
        outline = (255, 255, 255, 200)
        outline_width = 2

        shape_idx = self._shape_combo.GetSelection()
        shape_type = self.SHAPES[shape_idx][1]

        if shape_type == "rectangle":
            draw.rectangle([0, 0, size-1, size-1], fill=fill, outline=outline, width=outline_width)
        elif shape_type == "ellipse":
            draw.ellipse([0, 0, size-1, size-1], fill=fill, outline=outline, width=outline_width)
        elif shape_type == "triangle":
            points = [(size // 2, 0), (0, size-1), (size-1, size-1)]
            draw.polygon(points, fill=fill, outline=outline, width=outline_width)
        elif shape_type == "star":
            self._draw_star(draw, 0, 0, size, size, fill, outline, outline_width)
        elif shape_type == "arrow":
            self._draw_arrow(draw, 0, 0, size, size, fill, outline, outline_width)
        elif shape_type == "heart":
            self._draw_heart(draw, 0, 0, size, size, fill, outline, outline_width)

        return img

    def _apply_shape(self, image: Image.Image) -> Image.Image:
        """이미지에 도형 적용"""
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        result = image.copy()
        shape_layer = Image.new('RGBA', result.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(shape_layer)

        size = self._size_spin.GetValue()
        x = self._shape_x
        y = self._shape_y

        fill = (
            self._fill_color.Red(),
            self._fill_color.Green(),
            self._fill_color.Blue(),
            255
        )
        outline = (255, 255, 255, 200)
        outline_width = 2

        shape_idx = self._shape_combo.GetSelection()
        shape_type = self.SHAPES[shape_idx][1]

        if shape_type == "rectangle":
            draw.rectangle([x, y, x + size, y + size], fill=fill, outline=outline, width=outline_width)
        elif shape_type == "ellipse":
            draw.ellipse([x, y, x + size, y + size], fill=fill, outline=outline, width=outline_width)
        elif shape_type == "triangle":
            points = [(x + size // 2, y), (x, y + size), (x + size, y + size)]
            draw.polygon(points, fill=fill, outline=outline, width=outline_width)
        elif shape_type == "star":
            self._draw_star(draw, x, y, size, size, fill, outline, outline_width)
        elif shape_type == "arrow":
            self._draw_arrow(draw, x, y, size, size, fill, outline, outline_width)
        elif shape_type == "heart":
            self._draw_heart(draw, x, y, size, size, fill, outline, outline_width)

        return Image.alpha_composite(result, shape_layer)

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

            px = x + w // 2 + px * w / 35
            py = y + h // 2 + py * h / 35
            points.append((px, py))

        draw.polygon(points, fill=fill, outline=outline, width=outline_width)

    def _on_clear(self, event):
        """초기화"""
        self._shape_x = 50
        self._shape_y = 50
        self._size_spin.SetValue(80)
        self._update_canvas_sticker_rect()

        for i, frame in enumerate(self.frames):
            if i < len(self._original_images) and self._original_images[i] is not None:
                try:
                    frame._image = self._original_images[i].copy()
                except Exception as e:
                    print(f"원본 복원 오류 (프레임 {i}): {e}")

        self._safe_canvas_update()

    def _on_apply(self, event):
        """적용"""
        target = self._target_combo.GetSelection()
        selected_indices = getattr(self.frames, 'selected_indices', set())
        current_idx = getattr(self.frames, 'current_index', 0)

        # 애니메이션 적용
        if AnimatedOverlay and self._animation_type != AnimationType.NONE and target == 0:
            size = self._size_spin.GetValue()
            sticker_img = self._create_shape_image(size)

            animated_images = AnimatedOverlay.apply_sticker_animation(
                base_images=self._original_images,
                sticker=sticker_img,
                position=(self._shape_x, self._shape_y),
                animation_type=self._animation_type,
                start_frame=0,
                duration_frames=None
            )

            for i, frame in enumerate(self.frames):
                if i < len(animated_images) and animated_images[i] is not None:
                    try:
                        frame._image = animated_images[i]
                    except Exception as e:
                        print(f"애니메이션 적용 오류 (프레임 {i}): {e}")
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
                        processed = self._apply_shape(self._original_images[i])
                        frame._image = processed
                    except Exception as e:
                        print(f"스티커 적용 오류 (프레임 {i}): {e}")
                else:
                    try:
                        frame._image = self._original_images[i].copy()
                    except Exception as e:
                        print(f"원본 복원 오류 (프레임 {i}): {e}")

        self._on_deactivated()
        if hasattr(self._main_window, '_is_modified'):
            self._main_window._is_modified = True
        if hasattr(self._main_window, '_update_info_bar'):
            self._main_window._update_info_bar()
        self._safe_canvas_update()
        super()._on_apply(event)
        self.hide_from_canvas()

    def _on_cancel(self, event):
        """취소"""
        for i, frame in enumerate(self.frames):
            if i < len(self._original_images) and self._original_images[i] is not None:
                try:
                    frame._image = self._original_images[i].copy()
                except Exception as e:
                    print(f"원본 복원 오류 (프레임 {i}): {e}")

        self._safe_canvas_update()
        super()._on_cancel(event)

    def reset_to_default(self):
        """기본값으로 초기화"""
        self._shape_combo.SetSelection(0)
        self._size_spin.SetValue(80)
        self._fill_color = wx.Colour(255, 107, 107)
        self._shape_x = 50
        self._shape_y = 50
        if hasattr(self, '_anim_combo'):
            self._anim_combo.SetSelection(0)
            self._animation_type = AnimationType.NONE if AnimationType else 0
