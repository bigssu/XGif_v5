"""
CropToolbar - 이미지 자르기 인라인 툴바 (wxPython 버전)
"""
import wx
from typing import TYPE_CHECKING, Tuple
from .base_toolbar_wx import InlineToolbarBase

if TYPE_CHECKING:
    from ..main_window import MainWindow


class CropToolbar(InlineToolbarBase):
    """이미지 자르기 인라인 툴바 (wxPython)

    W/H 스핀박스로 크롭 영역을 지정합니다.
    """

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(main_window, parent)
        self._original_width = 0
        self._original_height = 0
        # X, Y 위치는 UI에서 제거되었지만 내부적으로는 캔버스에서만 조절 가능
        self._x_value = 0
        self._y_value = 0
        self._updating_from_canvas = False
        self._setup_controls()
        self.set_clear_button_visible(True)

    def _setup_controls(self):
        """컨트롤 설정"""
        translations = getattr(self._main_window, '_translations', None)

        # 크기 설정
        crop_size_tooltip = translations.tr("crop_size") if translations else "자르기 크기"
        self.add_icon_label("resize", 20, crop_size_tooltip)

        self._w_spin = wx.SpinCtrl(self._controls_widget, min=1, max=10000, initial=100)
        self._w_spin.SetMinSize((70, -1))
        width_tooltip = translations.tr("crop_width") if translations else "너비"
        self._w_spin.SetToolTip(width_tooltip)
        # wxPython SpinCtrl: EVT_SPINCTRL과 EVT_TEXT 모두 바인딩
        self._w_spin.Bind(wx.EVT_SPINCTRL, self._on_value_changed)
        self._w_spin.Bind(wx.EVT_TEXT, self._on_value_changed)
        self.add_control(self._w_spin)

        self._h_spin = wx.SpinCtrl(self._controls_widget, min=1, max=10000, initial=100)
        self._h_spin.SetMinSize((70, -1))
        height_tooltip = translations.tr("crop_height") if translations else "높이"
        self._h_spin.SetToolTip(height_tooltip)
        # wxPython SpinCtrl: EVT_SPINCTRL과 EVT_TEXT 모두 바인딩
        self._h_spin.Bind(wx.EVT_SPINCTRL, self._on_value_changed)
        self._h_spin.Bind(wx.EVT_TEXT, self._on_value_changed)
        self.add_control(self._h_spin)

        self.add_separator()

        # 프리셋
        self._preset_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY,
                                        choices=["None", "50%", "75%", "정사각형"])
        self._preset_combo.SetSelection(0)  # 기본값: None
        self._preset_combo.SetMinSize((90, -1))
        preset_tooltip = translations.tr("crop_preset") if translations else "크기 프리셋"
        self._preset_combo.SetToolTip(preset_tooltip)
        self._preset_combo.Bind(wx.EVT_COMBOBOX, self._on_preset_changed)
        self.add_control(self._preset_combo)

        # 결과 정보
        self._info_label = wx.StaticText(self._controls_widget, label="")
        self._info_label.SetForegroundColour(wx.Colour(79, 195, 247))
        font = self._info_label.GetFont()
        font.SetPointSize(8)
        self._info_label.SetFont(font)
        self.add_control(self._info_label)

    def _on_activated(self):
        """툴바 활성화"""
        print("[CropToolbar] _on_activated 호출됨")
        if not self.frames or getattr(self.frames, 'is_empty', False):
            print("[CropToolbar] 프레임이 없어서 활성화 중단")
            return

        self._original_width = getattr(self.frames, 'width', 100)
        self._original_height = getattr(self.frames, 'height', 100)
        print(f"[CropToolbar] 원본 크기: {self._original_width}x{self._original_height}")
        self._updating_from_canvas = False

        # 스핀박스 범위 설정
        self._w_spin.SetMax(self._original_width)
        self._h_spin.SetMax(self._original_height)

        # 전체 선택으로 초기화
        self._x_value = 0
        self._y_value = 0
        self._w_spin.SetValue(self._original_width)
        self._h_spin.SetValue(self._original_height)
        print(f"[CropToolbar] 초기 값 설정: w={self._w_spin.GetValue()}, h={self._h_spin.GetValue()}")

        # 캔버스 이벤트 연결 (wxPython 방식)
        canvas = self._safe_get_canvas()
        if canvas:
            try:
                # wxPython: Bind 방식으로 이벤트 연결
                from ...utils.wx_events import EVT_CROP_CHANGED
                canvas.Bind(EVT_CROP_CHANGED, self._on_canvas_crop_changed)
                print("[CropToolbar] 캔버스 CropChanged 이벤트 바인딩 완료")

                # 캔버스에 크롭 모드 활성화
                if hasattr(canvas, 'start_crop_mode'):
                    canvas.start_crop_mode(0, 0, self._original_width, self._original_height)
                    print("[CropToolbar] 캔버스 크롭 모드 시작됨")
            except Exception as e:
                print(f"[CropToolbar] 크롭 모드 시작 오류: {e}")

        self._update_info()
        print("[CropToolbar] _on_activated 완료")

    def _on_value_changed(self, event):
        """값 변경 (W, H만 변경 가능, X, Y는 캔버스에서만 조절)"""
        if self._updating_from_canvas:
            print("[CropToolbar] _on_value_changed: 캔버스에서 업데이트 중이므로 무시")
            return

        w = self._w_spin.GetValue()
        h = self._h_spin.GetValue()
        print(f"[CropToolbar] _on_value_changed: w={w}, h={h}")

        # W/H 최대값 조정
        max_w = self._original_width - self._x_value
        max_h = self._original_height - self._y_value

        self._w_spin.SetMax(max(1, max_w))
        self._h_spin.SetMax(max(1, max_h))

        # 범위를 벗어나면 조정
        if self._w_spin.GetValue() > max_w:
            self._w_spin.SetValue(max(1, max_w))
        if self._h_spin.GetValue() > max_h:
            self._h_spin.SetValue(max(1, max_h))

        # 캔버스에 크롭 영역 업데이트
        self._update_canvas_crop_rect()
        self._update_info()

    def _update_canvas_crop_rect(self):
        """캔버스에 크롭 영역 업데이트"""
        canvas = self._safe_get_canvas()
        if not canvas or not hasattr(canvas, 'update_crop_rect'):
            return
        try:
            canvas.update_crop_rect(
                self._x_value,
                self._y_value,
                self._w_spin.GetValue(),
                self._h_spin.GetValue()
            )
        except Exception as e:
            print(f"크롭 영역 업데이트 오류: {e}")

    def _on_canvas_crop_changed(self, event):
        """캔버스에서 크롭 영역이 변경됨 (wxPython 이벤트)"""
        print(f"[CropToolbar] _on_canvas_crop_changed 호출됨: x={event.x}, y={event.y}, w={event.width}, h={event.height}")
        self._updating_from_canvas = True

        # X, Y는 내부 변수로만 저장
        self._x_value = event.x
        self._y_value = event.y

        self._w_spin.SetValue(event.width)
        self._h_spin.SetValue(event.height)

        self._update_info()
        self._updating_from_canvas = False
        print(f"[CropToolbar] 툴바 값 업데이트 완료: w={self._w_spin.GetValue()}, h={self._h_spin.GetValue()}")

    def _update_info(self):
        """정보 라벨 업데이트"""
        w = self._w_spin.GetValue()
        h = self._h_spin.GetValue()
        self._info_label.SetLabel(f"{self._original_width}x{self._original_height} → {w}x{h}")

    def _on_preset_changed(self, event):
        """프리셋 드롭다운 변경"""
        index = self._preset_combo.GetSelection()
        print(f"[CropToolbar] _on_preset_changed: index={index}")
        if index == 0:  # None - 아무것도 하지 않음
            return
        elif index == 1:  # 50%
            print("[CropToolbar] 50% 프리셋 적용")
            self._apply_center_50()
        elif index == 2:  # 75%
            print("[CropToolbar] 75% 프리셋 적용")
            self._apply_center_75()
        elif index == 3:  # 정사각형
            print("[CropToolbar] 정사각형 프리셋 적용")
            self._apply_square()

    def _apply_center_50(self):
        """중앙 50% 프리셋"""
        w = self._original_width // 2
        h = self._original_height // 2
        x = (self._original_width - w) // 2
        y = (self._original_height - h) // 2

        print(f"[CropToolbar] _apply_center_50: x={x}, y={y}, w={w}, h={h}")

        self._x_value = x
        self._y_value = y
        self._w_spin.SetValue(w)
        self._h_spin.SetValue(h)
        self._update_canvas_crop_rect()
        print(f"[CropToolbar] _apply_center_50 완료: _x_value={self._x_value}, _y_value={self._y_value}, w={self._w_spin.GetValue()}, h={self._h_spin.GetValue()}")

    def _apply_center_75(self):
        """중앙 75% 프리셋"""
        w = int(self._original_width * 0.75)
        h = int(self._original_height * 0.75)
        x = (self._original_width - w) // 2
        y = (self._original_height - h) // 2

        self._x_value = x
        self._y_value = y
        self._w_spin.SetValue(w)
        self._h_spin.SetValue(h)
        self._update_canvas_crop_rect()

    def _apply_square(self):
        """정사각형 프리셋 (중앙)"""
        size = min(self._original_width, self._original_height)
        x = (self._original_width - size) // 2
        y = (self._original_height - size) // 2

        self._x_value = x
        self._y_value = y
        self._w_spin.SetValue(size)
        self._h_spin.SetValue(size)
        self._update_canvas_crop_rect()

    def _on_deactivated(self):
        """툴바 비활성화"""
        canvas = self._safe_get_canvas()
        if canvas:
            try:
                # wxPython: Unbind 방식으로 이벤트 연결 해제
                from ...utils.wx_events import EVT_CROP_CHANGED
                canvas.Unbind(EVT_CROP_CHANGED, handler=self._on_canvas_crop_changed)
                print("[CropToolbar] 캔버스 CropChanged 이벤트 언바인딩 완료")
            except Exception:
                pass
            try:
                if hasattr(canvas, 'stop_crop_mode'):
                    canvas.stop_crop_mode()
            except Exception as e:
                print(f"[CropToolbar] 크롭 모드 종료 오류: {e}")

    def _on_clear(self, event):
        """초기화 - 전체 선택"""
        self._x_value = 0
        self._y_value = 0
        self._w_spin.SetValue(self._original_width)
        self._h_spin.SetValue(self._original_height)
        self._update_canvas_crop_rect()

    def _on_apply(self, event):
        """적용 - 모든 프레임 자르기"""
        print(f"[CropToolbar] _on_apply 호출됨")

        # PyQt6 원본과 동일한 순서:
        # 1. 먼저 _on_deactivated() 호출 (캔버스 시그널 연결 해제, 크롭 모드 종료)
        self._on_deactivated()
        print("[CropToolbar] 크롭 모드 종료됨")

        # 2. 크롭 영역 가져오기
        x, y, w, h = self.get_crop_rect()
        print(f"[CropToolbar] 크롭 영역: x={x}, y={y}, w={w}, h={h}")
        print(f"[CropToolbar] 원본 크기: {self._original_width}x{self._original_height}")

        # 3. 변화가 없으면 무시
        if x == 0 and y == 0 and w == self._original_width and h == self._original_height:
            print("[CropToolbar] 변화가 없어서 무시")
            self.hide_from_canvas()
            return

        # 4. 모든 프레임에 적용
        print(f"[CropToolbar] 프레임 수: {len(list(self.frames))}")
        for i, frame in enumerate(self.frames):
            if hasattr(frame, 'crop'):
                print(f"[CropToolbar] 프레임 {i} 자르기 중...")
                frame.crop(x, y, w, h)
            else:
                print(f"[CropToolbar] 경고: 프레임 {i}에 crop 메서드가 없음")

        # 5. 수정 플래그 설정
        if hasattr(self._main_window, '_is_modified'):
            self._main_window._is_modified = True
            print("[CropToolbar] 수정 플래그 설정됨")

        # 6. 캔버스 업데이트
        self._safe_canvas_update()
        print("[CropToolbar] 캔버스 업데이트 완료")

        # 7. 정보 바 업데이트
        if hasattr(self._main_window, '_update_info_bar'):
            self._main_window._update_info_bar()
            print("[CropToolbar] 정보 바 업데이트 완료")

        # 8. 부모 클래스 _on_apply 호출 (PyQt6 원본: super()._on_apply(), 시그널만 발생)
        super()._on_apply(event)
        print("[CropToolbar] 부모 _on_apply 호출 완료")

        # 9. 툴바 숨기기 (PyQt6 원본과 동일)
        self.hide_from_canvas()
        print("[CropToolbar] _on_apply 완료")

    def _on_cancel(self, event):
        """취소"""
        # crop은 이미지를 변경하지 않으므로 복원 불필요
        super()._on_cancel(event)

    def get_crop_rect(self) -> Tuple[int, int, int, int]:
        """크롭 영역 반환 (x, y, w, h)"""
        return (
            self._x_value,
            self._y_value,
            self._w_spin.GetValue(),
            self._h_spin.GetValue()
        )

    def reset_to_default(self):
        """기본값으로 초기화"""
        self._on_clear(None)
