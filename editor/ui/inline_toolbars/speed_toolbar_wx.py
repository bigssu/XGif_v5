"""
SpeedToolbar - 속도 조절 인라인 툴바 (wxPython 버전)
"""
import wx
from typing import TYPE_CHECKING
from .base_toolbar_wx import InlineToolbarBase

if TYPE_CHECKING:
    from ..main_window import MainWindow


class SpeedToolbar(InlineToolbarBase):
    """속도 조절 인라인 툴바 (wxPython)

    슬라이더와 프리셋 버튼으로 GIF 속도를 조절합니다.
    """

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(main_window, parent)
        self._original_delays = []  # 원본 딜레이 저장
        self._setup_controls()

    def _setup_controls(self):
        """컨트롤 설정"""
        # 번역 시스템 가져오기
        translations = getattr(self._main_window, '_translations', None)

        # 속도 아이콘 + 슬라이더
        playback_speed_tooltip = translations.tr("speed_playback_speed") if translations else "재생 속도"
        self.add_icon_label("speed", 20, playback_speed_tooltip)

        self._speed_slider = wx.Slider(self._controls_widget, value=100,
                                      minValue=10, maxValue=400,
                                      style=wx.SL_HORIZONTAL)
        self._speed_slider.SetMinSize((120, -1))
        speed_tooltip = translations.tr("speed_speed") if translations else "속도"
        self._speed_slider.SetToolTip(speed_tooltip)
        self._speed_slider.Bind(wx.EVT_SLIDER, self._on_slider_changed)
        self.add_control(self._speed_slider)

        # 스핀박스
        self._speed_spin = wx.SpinCtrlDouble(self._controls_widget, min=0.1, max=4.0,
                                             initial=1.0, inc=0.1)
        self._speed_spin.SetDigits(2)
        self._speed_spin.SetMinSize((70, -1))
        self._speed_spin.Bind(wx.EVT_SPINCTRLDOUBLE, self._on_spin_changed)
        self.add_control(self._speed_spin)

        self.add_separator()

        # 프리셋 버튼들
        for speed in [0.5, 0.75, 1.0, 1.5, 2.0]:
            btn = wx.Button(self._controls_widget, label=f"{speed}x")
            btn.SetMinSize((48, 26))
            btn.SetBackgroundColour(wx.Colour(80, 80, 80))
            btn.SetForegroundColour(wx.Colour(255, 255, 255))
            btn.Bind(wx.EVT_BUTTON, lambda e, s=speed: self._apply_preset(s))
            self.add_control(btn)

        self.add_separator()

        # 시간 아이콘 + 결과 정보 라벨
        result_time_tooltip = translations.tr("speed_result_time") if translations else "결과 시간"
        self.add_icon_label("clock", 20, result_time_tooltip)

        self._result_label = wx.StaticText(self._controls_widget, label="")
        self._result_label.SetForegroundColour(wx.Colour(79, 195, 247))
        font = self._result_label.GetFont()
        font.SetPointSize(9)
        self._result_label.SetFont(font)
        self.add_control(self._result_label)

        # Clear 버튼 표시
        self.set_clear_button_visible(True)

    def _on_activated(self):
        """툴바 활성화"""
        # 원본 딜레이 저장
        if self.frames:
            self._original_delays = [f.delay_ms for f in self.frames]
        self._update_result_label()

    def _on_deactivated(self):
        """툴바 비활성화"""
        pass

    def _on_slider_changed(self, event):
        """슬라이더 변경"""
        value = self._speed_slider.GetValue()
        speed = value / 100.0
        self._speed_spin.SetValue(speed)
        self._update_preview()

    def _on_spin_changed(self, event):
        """스핀박스 변경"""
        value = self._speed_spin.GetValue()
        self._speed_slider.SetValue(int(value * 100))
        self._update_preview()

    def _apply_preset(self, speed: float):
        """프리셋 적용"""
        print(f"[SpeedToolbar] 프리셋 적용: {speed}x")
        self._speed_spin.SetValue(speed)
        # SetValue가 이벤트를 발생시키지 않을 수 있으므로 수동으로 업데이트
        self._speed_slider.SetValue(int(speed * 100))
        self._update_preview()
        print(f"[SpeedToolbar] 프리셋 적용 완료")

    def _update_preview(self):
        """미리보기 업데이트 (실시간 프리뷰)"""
        if not self._original_delays or not self.frames:
            return

        speed = self._speed_spin.GetValue()

        # 프레임 딜레이 임시 변경
        for i, frame in enumerate(self.frames):
            if i < len(self._original_delays):
                new_delay = max(10, int(self._original_delays[i] / speed))
                frame.delay_ms = new_delay

        self._update_result_label()

        # 프레임 리스트 업데이트
        if hasattr(self._main_window, '_frame_list'):
            self._main_window._frame_list.refresh()

        self.update_preview()

    def _update_result_label(self):
        """결과 라벨 업데이트"""
        if not self.frames or not self._original_delays:
            return

        original_total = sum(self._original_delays)
        current_total = sum(f.delay_ms for f in self.frames)

        self._result_label.SetLabel(
            f"{current_total / 1000:.2f}초 (원본: {original_total / 1000:.2f}초)"
        )

    def _on_clear(self, event):
        """초기화 버튼 클릭"""
        self._speed_spin.SetValue(1.0)
        self._speed_slider.SetValue(100)
        self._update_preview()

    def _on_apply(self, event):
        """적용 버튼 클릭"""
        # 변경사항이 이미 프리뷰에 반영되어 있으므로 원본 딜레이만 업데이트
        if self.frames:
            self._original_delays = [f.delay_ms for f in self.frames]

        # 원본 PyQt6와 동일: 수정 플래그 및 정보 바 업데이트
        if hasattr(self._main_window, '_is_modified'):
            self._main_window._is_modified = True
        if hasattr(self._main_window, '_update_info_bar'):
            self._main_window._update_info_bar()

        super()._on_apply(event)
        self.hide_from_canvas()

    def reset_to_default(self):
        """기본값으로 초기화"""
        # 원본 딜레이 복원
        if self._original_delays and self.frames:
            for i, frame in enumerate(self.frames):
                if i < len(self._original_delays):
                    frame.delay_ms = self._original_delays[i]

            if hasattr(self._main_window, '_frame_list'):
                self._main_window._frame_list.refresh()
