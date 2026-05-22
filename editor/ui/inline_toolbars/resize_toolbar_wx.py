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
        self._keep_ratio_check = wx.CheckBox(self._controls_widget, label=translations.tr("resize_keep_ratio") if translations else "비율 유지")
        self._keep_ratio_check.SetValue(True)
        keep_ratio_tooltip = translations.tr("resize_keep_ratio") if translations else "비율 유지"
        self._keep_ratio_check.SetToolTip(keep_ratio_tooltip)
        self._keep_ratio_check.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.add_control(self._keep_ratio_check)

        self.add_separator()

        # 프리셋
        self._preset_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY,
                                        choices=["50%", "75%", "100%", "150%", "200%"])
        self._preset_combo.SetSelection(1)  # 기본값 75% — 대부분의 GIF 가 압축 후 작은 크기를 선호함
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
        """툴바 활성화 — snapshot 은 lazy (사용자가 실제로 크기 변경할 때만).

        활성화 시 N × Image.copy() 가 1.8GB / 359 프레임 환경에서 ~1초 UI
        freeze 를 유발해, 사용자가 "크기조절 클릭 시 1초 화면 정지" 를 보고함.
        snapshot 은 _update_preview/_on_apply/_on_cancel 시작점의 lazy ensure
        로 옮긴다. 클릭만 하고 변경 없이 닫는 케이스는 비용 0.
        """
        frames = self.frames
        if not frames or getattr(frames, 'is_empty', False):
            return

        # lazy snapshot — 첫 변경 시점에 _ensure_original_images_snapshot() 가 받음
        self._original_images = []

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
        """프리셋 적용 — 단일 선택이므로 디바운스 불필요, 즉시 미리보기.

        이전엔 50ms `_preview_timer` 로 지연 → `_update_preview` 안에서 lazy
        snapshot 비용까지 합쳐져 사용자 체감 "풀다운 50% 선택 후에도 화면이
        안 줄어드는" 회귀를 유발 (사용자 보고 2026-05-21). spin 변경 (width/
        height) 은 사용자가 빠르게 클릭하는 케이스라 150ms 디바운스가 필요하지만,
        preset 은 한 번의 명확한 선택이므로 즉시 처리해야 한다.

        ComboBox 이벤트 핸들러 내 동기 호출은 dropdown 위치 회귀를 일으킬 수
        있어 `wx.CallAfter` 로 다음 idle 에서 미리보기 갱신 (50ms timer 보다
        빠르고 안전).
        """
        self._updating = True
        self._width_spin.SetValue(int(self._original_width * scale))
        self._height_spin.SetValue(int(self._original_height * scale))
        self._updating = False
        # 이전 pending timer 가 있으면 취소 — 중복 갱신 방지
        if self._preview_timer.IsRunning():
            self._preview_timer.Stop()
        wx.CallAfter(self._update_preview)

    def _update_preview(self):
        """실시간 프리뷰 업데이트"""
        # lazy snapshot — 첫 호출에서 원본 캡처
        self._ensure_original_images_snapshot()
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

        # snapshot 없으면 변경한 적 없음 → 복원할 것도 없음
        if self._original_images:
            self._restore_original_images_with_size()
            self._safe_canvas_update()

    def _on_apply(self, event):
        """적용"""
        new_width = self._width_spin.GetValue()
        new_height = self._height_spin.GetValue()
        resample = self.get_resample_method()

        # 크기가 변경되지 않으면 원본 복원 후 종료
        if new_width == self._original_width and new_height == self._original_height:
            # snapshot 없으면 이미 원본 상태 → 복원 불필요
            if self._original_images:
                self._restore_original_images_with_size()
            self._finish_apply()
            return

        # 실제 변경이 있을 때만 lazy snapshot
        self._ensure_original_images_snapshot()
        self._apply_resized_images(new_width, new_height, resample)
        self._finish_apply()

    def _on_cancel(self, event):
        """취소 - 원본으로 복원"""
        # snapshot 없으면 변경한 적 없음 → 복원할 것도 없음
        if self._original_images:
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
