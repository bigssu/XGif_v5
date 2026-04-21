"""
캡처 영역 선택 오버레이 창
빨간 테두리, 외부 핸들로 리사이즈, 항상 위
DPI 스케일링 및 다중 모니터 지원
"""

from typing import Tuple, Optional, Callable
import wx

from ui.theme import Colors, Fonts

# 상수 정의
from ui.constants import (
    OVERLAY_BORDER_WIDTH, OVERLAY_HANDLE_SIZE, OVERLAY_HANDLE_MARGIN,
    OVERLAY_MIN_CAPTURE_SIZE, OVERLAY_BOTTOM_EXTRA,
    DEFAULT_CAPTURE_WIDTH, DEFAULT_CAPTURE_HEIGHT,
    OVERLAY_MOVE_SMALL, OVERLAY_MOVE_LARGE, DEBOUNCE_DELAY_MS,
    MIN_VISIBLE_PIXELS
)


class CoordinateConverter:
    """논리적 좌표 <-> 물리적 픽셀 좌표 변환
    
    wx는 논리적 좌표(DIP)를 사용하고, 캡처 라이브러리(dxcam, gdi)는
    물리적 픽셀 좌표를 사용합니다. 이 클래스는 두 좌표 체계 간 변환을 담당합니다.
    
    다중 모니터 환경에서 각 모니터의 DPI가 다를 수 있으므로,
    좌표가 위치한 모니터의 DPI 스케일을 사용합니다.
    """

    @staticmethod
    def get_screen_at(x: int, y: int) -> Optional[wx.Display]:
        """주어진 좌표가 위치한 화면 반환
        
        Args:
            x, y: 논리적 좌표
            
        Returns:
            wx.Display: 해당 화면 (없으면 기본 화면)
        """
        for i in range(wx.Display.GetCount()):
            display = wx.Display(i)
            geometry = display.GetGeometry()
            if geometry.Contains(x, y):
                return display
        return wx.Display(0)  # 기본 화면

    @staticmethod
    def get_dpi_scale(display: Optional[wx.Display]) -> float:
        """화면의 DPI 스케일 반환"""
        if display:
            try:
                # wx에서는 PPI를 통해 스케일 계산
                ppi = display.GetPPI()
                if ppi and ppi[0] > 0:
                    return ppi[0] / 96.0  # 96 DPI가 100% 스케일
                return 1.0
            except Exception:
                return 1.0
        return 1.0

    @staticmethod
    def logical_to_physical(x: int, y: int, width: int, height: int,
                           display: Optional[wx.Display] = None) -> Tuple[int, int, int, int]:
        """논리적 좌표를 물리적 픽셀 좌표로 변환
        
        Args:
            x, y: 논리적 좌표
            width, height: 논리적 크기
            display: 대상 화면 (None이면 자동 감지)
            
        Returns:
            Tuple[int, int, int, int]: (물리적 x, y, width, height)
        """
        if display is None:
            display = CoordinateConverter.get_screen_at(x, y)

        scale = CoordinateConverter.get_dpi_scale(display)

        # 모니터 오프셋 고려
        if display:
            screen_geo = display.GetGeometry()
            # 화면 내 상대 좌표 계산
            rel_x = x - screen_geo.x
            rel_y = y - screen_geo.y

            # 물리적 좌표 = 화면 물리적 시작점 + 상대 좌표 * 스케일
            phys_screen_x = int(screen_geo.x * scale)
            phys_screen_y = int(screen_geo.y * scale)

            phys_x = phys_screen_x + int(rel_x * scale)
            phys_y = phys_screen_y + int(rel_y * scale)
        else:
            phys_x = int(x * scale)
            phys_y = int(y * scale)

        phys_w = int(width * scale)
        phys_h = int(height * scale)

        return (phys_x, phys_y, phys_w, phys_h)

    @staticmethod
    def physical_to_logical(x: int, y: int, width: int, height: int,
                           display: Optional[wx.Display] = None) -> Tuple[int, int, int, int]:
        """물리적 픽셀 좌표를 논리적 좌표로 변환
        
        Args:
            x, y: 물리적 좌표
            width, height: 물리적 크기
            display: 대상 화면 (None이면 기본 화면)
            
        Returns:
            Tuple[int, int, int, int]: (논리적 x, y, width, height)
        """
        if display is None:
            display = wx.Display(0)

        scale = CoordinateConverter.get_dpi_scale(display)
        if scale == 0:
            scale = 1.0

        log_x = int(x / scale)
        log_y = int(y / scale)
        log_w = int(width / scale)
        log_h = int(height / scale)

        return (log_x, log_y, log_w, log_h)


class CaptureOverlay(wx.Frame):
    """캡처 영역 선택을 위한 오버레이 창"""

    # 리사이즈 핸들 위치
    HANDLE_NONE = 0
    HANDLE_TOP_LEFT = 1
    HANDLE_TOP = 2
    HANDLE_TOP_RIGHT = 3
    HANDLE_RIGHT = 4
    HANDLE_BOTTOM_RIGHT = 5
    HANDLE_BOTTOM = 6
    HANDLE_BOTTOM_LEFT = 7
    HANDLE_LEFT = 8
    HANDLE_MOVE = 9  # 테두리 드래그로 이동

    def __init__(self, parent_window=None):
        # 투명 창을 위한 스타일 설정 (FRAME_SHAPED 제거: SetShape 미사용 + SetSize 충돌)
        style = wx.FRAME_NO_TASKBAR | wx.STAY_ON_TOP | wx.BORDER_NONE

        # 초기 크기를 __init__에서 직접 전달
        _padding = OVERLAY_HANDLE_SIZE + OVERLAY_HANDLE_MARGIN
        _border_offset = (OVERLAY_BORDER_WIDTH + 1) // 2
        init_w = DEFAULT_CAPTURE_WIDTH + 2 * _padding + 2 * _border_offset
        init_h = DEFAULT_CAPTURE_HEIGHT + 2 * _padding + 2 * _border_offset + OVERLAY_BOTTOM_EXTRA

        # parent를 None으로 생성: 메인 윈도우의 DPI 스케일이 오버레이 크기에 영향 방지
        wx.Frame.__init__(self, None, style=style, size=(init_w, init_h))

        self.parent_window = parent_window

        # Windows에서 투명 배경을 위한 설정
        # 특정 색상(검은색)을 투명 키로 설정
        self.SetBackgroundColour(wx.BLACK)

        # Windows의 Layered Window 속성 사용하여 특정 색상을 투명하게
        try:
            import ctypes

            hwnd = self.GetHandle()

            # Get current window style
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            LWA_COLORKEY = 0x00000001

            user32 = ctypes.windll.user32

            # Set WS_EX_LAYERED extended style
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_LAYERED)

            # Set black (0, 0, 0) as transparent color key
            user32.SetLayeredWindowAttributes(hwnd, 0x00000000, 0, LWA_COLORKEY)
        except Exception as e:
            import logging as _overlay_log
            _overlay_log.getLogger(__name__).error(f"Could not set transparent background: {e}")

        # 콜백 함수들
        self._region_changed_callback: Optional[Callable[[int, int, int, int], None]] = None
        self._closed_callback: Optional[Callable[[], None]] = None

        # 상태 변수 (상수에서 가져옴)
        self.border_width = OVERLAY_BORDER_WIDTH
        self.handle_size = OVERLAY_HANDLE_SIZE
        self.handle_margin = OVERLAY_HANDLE_MARGIN
        self.min_capture_size = OVERLAY_MIN_CAPTURE_SIZE

        # 핸들 영역을 위한 패딩
        self.padding = self.handle_size + self.handle_margin
        self.bottom_extra = OVERLAY_BOTTOM_EXTRA

        # 배경 스타일 설정 (투명 배경)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        # 배경 지우기 이벤트 처리 (깜박임 방지)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda e: None)

        # UI 초기화
        self._init_ui()

    def set_region_changed_callback(self, callback: Callable[[int, int, int, int], None]):
        """영역 변경 콜백 설정"""
        self._region_changed_callback = callback

    def set_closed_callback(self, callback: Callable[[], None]):
        """닫힘 콜백 설정"""
        self._closed_callback = callback

    def _emit_region_changed(self, x, y, w, h):
        """영역 변경 이벤트 발생"""
        if self._region_changed_callback:
            try:
                self._region_changed_callback(x, y, w, h)
            except Exception:
                pass

    def _emit_closed(self):
        """닫힘 이벤트 발생"""
        if self._closed_callback:
            try:
                self._closed_callback()
            except Exception:
                pass

    def _init_ui(self):
        """UI 초기화 - __init__에서 호출"""
        self.dragging = False
        self.resizing = False
        self.current_handle = self.HANDLE_NONE
        self.drag_start_pos = wx.Point()
        self.drag_start_geometry = wx.Rect()

        # 이동/리사이즈 가능 여부
        self.movable = True
        self.allow_resize = True

        # 녹화 모드 (투명도 조절용)
        self.recording_mode = False

        # 기본 크기 및 위치 (캡처 영역 기준)
        screen = wx.Display(0).GetGeometry()

        # set_capture_size()/get_capture_size()와 동일한 공식 사용
        border_offset = (self.border_width + 1) // 2
        total_width = DEFAULT_CAPTURE_WIDTH + 2 * self.padding + 2 * border_offset
        total_height = DEFAULT_CAPTURE_HEIGHT + 2 * self.padding + 2 * border_offset + self.bottom_extra

        x = (screen.width - total_width) // 2
        y = (screen.height - total_height) // 2
        self.SetPosition((x, y))
        self.SetSize((total_width, total_height))

        # Win32 API로 크기 강제 (Layered 윈도우에서 wxPython SetSize 무시 방지)
        self._force_win32_size(x, y, total_width, total_height)

        # 마우스 추적 활성화
        # wxPython에서는 마우스 추적이 기본적으로 활성화됨
        self.Bind(wx.EVT_MOTION, self.OnMouseMove)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnMouseDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnMouseUp)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_MOVE, self.OnMove)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

        # 영역 변경 시그널을 위한 타이머 (debounce) - wxPython 스타일
        self.emit_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._emit_region, self.emit_timer)

        # 윈도우 파괴 시 타이머 정리 (Destroy() 직접 호출 시에도 안전)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_window_destroy)

        # 초기 영역 전송
        wx.CallLater(100, self._emit_region)

    def _force_win32_size(self, x: int, y: int, w: int, h: int):
        """Win32 SetWindowPos로 윈도우 크기 강제 (wxPython SetSize가 무시되는 경우 대비)"""
        try:
            import ctypes
            hwnd = self.GetHandle()
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, w, h, SWP_NOZORDER | SWP_NOACTIVATE
            )
        except Exception:
            pass

    def OnSize(self, event):
        """크기 변경 시 모양 업데이트"""
        event.Skip()
        self.Refresh(True)
        self._schedule_emit()

    def set_movable(self, movable: bool, allow_resize: bool = True):
        """이동/리사이즈 가능 여부 설정
        
        Args:
            movable: 이동 가능 여부
            allow_resize: 리사이즈 가능 여부 (movable=True일 때만 적용)
        """
        self.movable = movable
        self.allow_resize = allow_resize if movable else False

    def set_recording_mode(self, recording: bool):
        """녹화 모드 설정 (투명도 조절)
        
        Args:
            recording: 녹화 중 여부 (True면 30% 투명도)
        """
        self.recording_mode = recording
        self.Refresh()  # 다시 그리기

    def OnPaint(self, event):
        """창 그리기"""
        dc = wx.AutoBufferedPaintDC(self)

        # 배경을 검은색으로 채우기 (투명 키로 설정된 색상)
        dc.SetBackground(wx.Brush(wx.BLACK))
        dc.Clear()

        # GraphicsContext 사용 (안티앨리어싱)
        gc = wx.GraphicsContext.Create(dc)
        if not gc:
            return

        # 캡처 영역 테두리 사각형 (내부 영역)
        border_rect = self._get_border_rect()

        # 그라데이션 테두리 색상
        if self.recording_mode:
            # 녹화 중: 30% 투명도
            pen = gc.CreatePen(wx.GraphicsPenInfo(Colors.OVERLAY_BORDER_REC).Width(self.border_width))
        else:
            # 일반: 그라데이션 효과를 위한 밝은 빨강
            pen = gc.CreatePen(wx.GraphicsPenInfo(Colors.OVERLAY_BORDER).Width(self.border_width))
        gc.SetPen(pen)
        gc.SetBrush(wx.TRANSPARENT_BRUSH)

        # 라운드 사각형 테두리
        path = gc.CreatePath()
        path.AddRoundedRectangle(border_rect.x, border_rect.y, border_rect.width, border_rect.height, 4)
        gc.StrokePath(path)

        # 안쪽 테두리 (그라데이션 효과)
        if not self.recording_mode:
            inner_pen = gc.CreatePen(wx.GraphicsPenInfo(Colors.OVERLAY_INNER_BORDER).Width(1))
            gc.SetPen(inner_pen)
            inner_rect = wx.Rect(border_rect.x + 2, border_rect.y + 2,
                                 border_rect.width - 4, border_rect.height - 4)
            path = gc.CreatePath()
            path.AddRoundedRectangle(inner_rect.x, inner_rect.y, inner_rect.width, inner_rect.height, 3)
            gc.StrokePath(path)

        # 녹화 중이 아닐 때만 핸들과 크기 표시
        if not self.recording_mode:
            # 리사이즈 핸들 그리기 (외부)
            self._draw_handles(gc)

            # 크기 표시 (오른쪽 하단 바깥쪽) - 모던 배지 스타일
            capture_w, capture_h = self.get_capture_size()
            size_text = f"{capture_w} × {capture_h}"

            # 폰트 설정
            font = Fonts.get_font(Fonts.SIZE_SMALL, bold=True)
            gc.SetFont(font, Colors.TEXT_PRIMARY)

            # 텍스트 크기 측정
            text_width, text_height = dc.GetTextExtent(size_text)
            text_width += 16
            text_height += 8

            # 오른쪽 하단 바깥쪽에 위치 (테두리 아래)
            text_x = border_rect.GetRight() - text_width + 4
            text_y = border_rect.GetBottom() + 4

            text_rect = wx.Rect(text_x, text_y, text_width, text_height)

            # 배지 배경
            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.SetBrush(gc.CreateBrush(wx.Brush(Colors.OVERLAY_BADGE_BG)))
            path = gc.CreatePath()
            path.AddRoundedRectangle(text_rect.x, text_rect.y, text_rect.width, text_rect.height, 6)
            gc.FillPath(path)

            # 텍스트
            tw, th = dc.GetTextExtent(size_text)
            text_center_x = text_rect.x + (text_rect.width - tw) // 2
            text_center_y = text_rect.y + (text_rect.height - th) // 2
            gc.DrawText(size_text, text_center_x, text_center_y)

    def _get_border_rect(self) -> wx.Rect:
        """테두리 사각형 (핸들 영역 및 하단 텍스트 공간 제외)"""
        size = self.GetSize()
        return wx.Rect(
            self.padding,
            self.padding,
            size.width - 2 * self.padding,
            size.height - 2 * self.padding - self.bottom_extra
        )

    def _draw_handles(self, gc: wx.GraphicsContext):
        """리사이즈 핸들 그리기 (외부) - 모던 원형 스타일"""
        handles = self._get_handle_rects()

        for handle_id, handle_rect in handles.items():
            # 그림자 효과
            shadow_rect = wx.Rect(handle_rect.x + 1, handle_rect.y + 1,
                                  handle_rect.width, handle_rect.height)
            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.SetBrush(gc.CreateBrush(wx.Brush(Colors.OVERLAY_HANDLE_SHADOW)))
            gc.DrawEllipse(shadow_rect.x, shadow_rect.y, shadow_rect.width, shadow_rect.height)

            # 핸들 배경
            gc.SetBrush(gc.CreateBrush(wx.Brush(Colors.OVERLAY_HANDLE_BG)))
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(Colors.OVERLAY_HANDLE_BORDER).Width(1)))
            gc.DrawEllipse(handle_rect.x, handle_rect.y, handle_rect.width, handle_rect.height)

            # 핸들 내부 악센트 (코너 핸들만)
            if handle_id in [self.HANDLE_TOP_LEFT, self.HANDLE_TOP_RIGHT,
                            self.HANDLE_BOTTOM_LEFT, self.HANDLE_BOTTOM_RIGHT]:
                inner_rect = wx.Rect(handle_rect.x + 3, handle_rect.y + 3,
                                     handle_rect.width - 6, handle_rect.height - 6)
                gc.SetBrush(gc.CreateBrush(wx.Brush(Colors.OVERLAY_HANDLE_ACCENT)))
                gc.SetPen(wx.TRANSPARENT_PEN)
                gc.DrawEllipse(inner_rect.x, inner_rect.y, inner_rect.width, inner_rect.height)

    def _get_handle_rects(self) -> dict:
        """각 핸들의 사각형 반환 (테두리 바깥)"""
        hs = self.handle_size
        border_rect = self._get_border_rect()

        # 핸들 위치 (테두리 바깥)
        left = border_rect.GetLeft() - hs - self.handle_margin
        right = border_rect.GetRight() + self.handle_margin
        top = border_rect.GetTop() - hs - self.handle_margin
        bottom = border_rect.GetBottom() + self.handle_margin

        # 중심 좌표 계산
        h_center = border_rect.GetLeft() + border_rect.GetWidth() // 2 - hs // 2
        v_center = border_rect.GetTop() + border_rect.GetHeight() // 2 - hs // 2

        return {
            self.HANDLE_TOP_LEFT: wx.Rect(left, top, hs, hs),
            self.HANDLE_TOP: wx.Rect(h_center, top, hs, hs),
            self.HANDLE_TOP_RIGHT: wx.Rect(right, top, hs, hs),
            self.HANDLE_RIGHT: wx.Rect(right, v_center, hs, hs),
            self.HANDLE_BOTTOM_RIGHT: wx.Rect(right, bottom, hs, hs),
            self.HANDLE_BOTTOM: wx.Rect(h_center, bottom, hs, hs),
            self.HANDLE_BOTTOM_LEFT: wx.Rect(left, bottom, hs, hs),
            self.HANDLE_LEFT: wx.Rect(left, v_center, hs, hs),
        }

    def _get_handle_at(self, pos: wx.Point) -> int:
        """위치에 해당하는 핸들 반환"""
        # 리사이즈 허용 시에만 핸들 체크
        if self.allow_resize:
            handles = self._get_handle_rects()

            for handle_id, handle_rect in handles.items():
                if handle_rect.Contains(pos):
                    return handle_id

        # 테두리 영역이면 이동
        border_rect = self._get_border_rect()
        expanded_border = wx.Rect(border_rect.x - 8, border_rect.y - 8,
                                   border_rect.width + 16, border_rect.height + 16)
        inner_area = wx.Rect(border_rect.x + 15, border_rect.y + 15,
                             border_rect.width - 30, border_rect.height - 30)

        if expanded_border.Contains(pos) and not inner_area.Contains(pos):
            return self.HANDLE_MOVE

        return self.HANDLE_NONE

    def _update_cursor(self, handle: int):
        """핸들에 따른 커서 변경"""
        cursor_map = {
            self.HANDLE_NONE: wx.CURSOR_ARROW,
            self.HANDLE_TOP_LEFT: wx.CURSOR_SIZENWSE,
            self.HANDLE_TOP: wx.CURSOR_SIZENS,
            self.HANDLE_TOP_RIGHT: wx.CURSOR_SIZENESW,
            self.HANDLE_RIGHT: wx.CURSOR_SIZEWE,
            self.HANDLE_BOTTOM_RIGHT: wx.CURSOR_SIZENWSE,
            self.HANDLE_BOTTOM: wx.CURSOR_SIZENS,
            self.HANDLE_BOTTOM_LEFT: wx.CURSOR_SIZENESW,
            self.HANDLE_LEFT: wx.CURSOR_SIZEWE,
            self.HANDLE_MOVE: wx.CURSOR_SIZING,
        }
        self.SetCursor(wx.Cursor(cursor_map.get(handle, wx.CURSOR_ARROW)))

    def OnMouseDown(self, event):
        """마우스 누름"""
        if not self.movable:
            event.Skip()
            return

        if event.GetButton() == wx.MOUSE_BTN_LEFT:
            self.current_handle = self._get_handle_at(event.GetPosition())

            if self.current_handle != self.HANDLE_NONE:
                self.drag_start_pos = wx.GetMousePosition()
                self.drag_start_geometry = self.GetRect()

                if self.current_handle == self.HANDLE_MOVE:
                    self.dragging = True
                else:
                    self.resizing = True

                if not self.HasCapture():
                    self.CaptureMouse()
            else:
                event.Skip()
        else:
            event.Skip()

    def OnMouseMove(self, event):
        """마우스 이동"""
        if not self.movable:
            event.Skip()
            return

        if self.dragging:
            # 창 이동 (화면 경계 검증 적용)
            global_pos = wx.GetMousePosition()
            delta = global_pos - self.drag_start_pos
            new_pos = self.drag_start_geometry.GetTopLeft() + delta
            validated_pos = self._validate_position(new_pos)
            self.Move(validated_pos)
            self._schedule_emit()

        elif self.resizing:
            # 창 리사이즈
            self._resize_by_handle(wx.GetMousePosition())
            self._schedule_emit()

        else:
            # 커서 업데이트
            handle = self._get_handle_at(event.GetPosition())
            self._update_cursor(handle)

    def OnMouseUp(self, event):
        """마우스 놓음"""
        if event.GetButton() == wx.MOUSE_BTN_LEFT:
            if self.HasCapture():
                self.ReleaseMouse()
            self.dragging = False
            self.resizing = False
            self.current_handle = self.HANDLE_NONE
            self._emit_region()

    def _resize_by_handle(self, global_pos: wx.Point):
        """핸들에 따른 리사이즈"""
        delta = wx.Point(global_pos.x - self.drag_start_pos.x,
                        global_pos.y - self.drag_start_pos.y)
        geo = self.drag_start_geometry

        new_left = geo.x
        new_top = geo.y
        new_right = geo.x + geo.width
        new_bottom = geo.y + geo.height

        # 핸들에 따라 변경
        if self.current_handle in [self.HANDLE_TOP_LEFT, self.HANDLE_LEFT, self.HANDLE_BOTTOM_LEFT]:
            new_left = geo.x + delta.x

        if self.current_handle in [self.HANDLE_TOP_LEFT, self.HANDLE_TOP, self.HANDLE_TOP_RIGHT]:
            new_top = geo.y + delta.y

        if self.current_handle in [self.HANDLE_TOP_RIGHT, self.HANDLE_RIGHT, self.HANDLE_BOTTOM_RIGHT]:
            new_right = geo.x + geo.width + delta.x

        if self.current_handle in [self.HANDLE_BOTTOM_LEFT, self.HANDLE_BOTTOM, self.HANDLE_BOTTOM_RIGHT]:
            new_bottom = geo.y + geo.height + delta.y

        # 최소 크기 제한 (캡처 영역 기준)
        min_total = self.min_capture_size + 2 * self.padding + 2 * self.border_width

        if new_right - new_left < min_total:
            if self.current_handle in [self.HANDLE_TOP_LEFT, self.HANDLE_LEFT, self.HANDLE_BOTTOM_LEFT]:
                new_left = new_right - min_total
            else:
                new_right = new_left + min_total

        if new_bottom - new_top < min_total:
            if self.current_handle in [self.HANDLE_TOP_LEFT, self.HANDLE_TOP, self.HANDLE_TOP_RIGHT]:
                new_top = new_bottom - min_total
            else:
                new_bottom = new_top + min_total

        # 새 위치 적용
        self.SetPosition((new_left, new_top))
        self.SetSize((new_right - new_left, new_bottom - new_top))
        self.Refresh()

    def OnMove(self, event):
        """창 이동 시 영역 시그널 전송"""
        event.Skip()
        # 외부에서 SetPosition() 호출 시에도 영역 업데이트
        self._schedule_emit()

    def OnKeyDown(self, event):
        """키 입력 - 화살표로 이동, Shift+화살표로 빠른 이동"""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
            return

        # 이동 불가 상태면 무시
        if not self.movable:
            event.Skip()
            return

        # 이동량 결정 (Shift 키 누르면 10px, 아니면 1px)
        move_amount = OVERLAY_MOVE_LARGE if event.ShiftDown() else OVERLAY_MOVE_SMALL

        dx, dy = 0, 0

        if event.GetKeyCode() == wx.WXK_LEFT:
            dx = -move_amount
        elif event.GetKeyCode() == wx.WXK_RIGHT:
            dx = move_amount
        elif event.GetKeyCode() == wx.WXK_UP:
            dy = -move_amount
        elif event.GetKeyCode() == wx.WXK_DOWN:
            dy = move_amount
        else:
            event.Skip()
            return

        # 새 위치 계산 및 화면 경계 검증
        new_pos = self.GetPosition() + wx.Point(dx, dy)
        validated_pos = self._validate_position(new_pos)

        self.Move(validated_pos)
        self._schedule_emit()

    def _validate_position(self, pos: wx.Point) -> wx.Point:
        """화면 경계 내로 위치 검증
        
        Args:
            pos: 검증할 위치
            
        Returns:
            wx.Point: 화면 내로 조정된 위치
        """
        # 현재 창이 있는 화면 사용 (다중 모니터 지원)
        current_screen = self._get_current_screen()
        screen = current_screen.GetClientArea() if current_screen else wx.Display(0).GetClientArea()
        geo = self.GetRect()

        # 최소 픽셀 이상 화면 내에 있어야 함
        min_visible = MIN_VISIBLE_PIXELS

        x = pos.x
        y = pos.y

        # 화면의 절대 좌표 경계 사용 (다중 모니터 지원)
        screen_right = screen.x + screen.width
        screen_bottom = screen.y + screen.height
        # 왼쪽 경계
        if x + geo.width < screen.x + min_visible:
            x = screen.x + min_visible - geo.width
        # 오른쪽 경계
        if x > screen_right - min_visible:
            x = screen_right - min_visible
        # 상단 경계
        if y + geo.height < screen.y + min_visible:
            y = screen.y + min_visible - geo.height
        # 하단 경계
        if y > screen_bottom - min_visible:
            y = screen_bottom - min_visible

        return wx.Point(x, y)

    def OnClose(self, event):
        """창 닫기"""
        self._cleanup()
        self._emit_closed()
        event.Skip()

    def _on_window_destroy(self, event):
        """윈도우 파괴 시 타이머 정리"""
        if event.GetEventObject() is self:
            self._cleanup()
        event.Skip()

    def _cleanup(self):
        """리소스 정리 - 메모리 누수 방지"""
        from core.utils import safe_delete_timer
        # 타이머 정리
        if self.emit_timer is not None:
            safe_delete_timer(self.emit_timer)
            self.emit_timer = None

    def _schedule_emit(self):
        """영역 변경 시그널 예약 (debounce)"""
        if self.emit_timer is not None:
            self.emit_timer.Start(DEBOUNCE_DELAY_MS, wx.TIMER_ONE_SHOT)

    def _emit_region(self, event=None):
        """캡처 영역 시그널 전송 (테두리 안쪽만)"""
        try:
            x, y, w, h = self.get_capture_region()
            self._emit_region_changed(x, y, w, h)
        except (RuntimeError, AttributeError):
            pass  # 위젯이 이미 삭제된 경우

    def get_capture_size(self) -> tuple:
        """실제 캡처 크기 (테두리 안쪽)"""
        # wx.Pen은 선의 중심을 기준으로 그림
        # 테두리 안쪽 영역 = border_rect - 양쪽 border_offset
        border_rect = self._get_border_rect()
        border_offset = (self.border_width + 1) // 2  # 올림 (3 -> 2)
        w = border_rect.width - 2 * border_offset
        h = border_rect.height - 2 * border_offset
        return (max(0, w), max(0, h))

    def _get_current_screen(self) -> wx.Display:
        """현재 창이 위치한 화면 반환"""
        geo = self.GetRect()
        center_x = geo.x + geo.width // 2
        center_y = geo.y + geo.height // 2
        return CoordinateConverter.get_screen_at(center_x, center_y)

    def _get_dpi_scale(self) -> float:
        """현재 창이 위치한 화면의 DPI 스케일 팩터 반환
        
        다중 모니터 환경에서 올바른 DPI를 사용하기 위해
        창의 중심 좌표가 위치한 화면의 DPI를 반환합니다.
        """
        screen = self._get_current_screen()
        return CoordinateConverter.get_dpi_scale(screen)

    def get_capture_region(self) -> tuple:
        """캡처 영역 좌표 반환 (x, y, width, height) - 물리적 픽셀 좌표

        Per-Monitor DPI Aware 모드에서는 wx 좌표가 이미 물리적 픽셀이므로
        추가 변환 없이 직접 반환합니다.
        DPI Unaware 모드에서는 CoordinateConverter로 변환합니다.

        Returns:
            tuple: (x, y, width, height) 물리적 픽셀 단위
        """
        geo = self.GetRect()

        # 테두리 안쪽 영역 계산
        border_offset = (self.border_width + 1) // 2

        cap_x = geo.x + self.padding + border_offset
        cap_y = geo.y + self.padding + border_offset
        cap_w, cap_h = self.get_capture_size()

        # DPI Awareness 확인: Per-Monitor Aware(2)이면 변환 불필요
        dpi_aware = self._is_dpi_aware()
        if dpi_aware:
            return (cap_x, cap_y, cap_w, cap_h)

        # DPI Unaware: 논리적 → 물리적 변환 필요
        screen = self._get_current_screen()
        phys_x, phys_y, phys_w, phys_h = CoordinateConverter.logical_to_physical(
            cap_x, cap_y, cap_w, cap_h, screen
        )
        return (phys_x, phys_y, phys_w, phys_h)

    @staticmethod
    def _is_dpi_aware() -> bool:
        """프로세스가 DPI Aware인지 확인"""
        try:
            import ctypes
            awareness = ctypes.c_int()
            ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(awareness))
            return awareness.value >= 1  # SYSTEM_AWARE(1) 또는 PER_MONITOR_AWARE(2)
        except (AttributeError, OSError):
            return False

    def set_capture_region(self, x: int, y: int, width: int, height: int):
        """캡처 영역 설정 (외부에서 호출) - 논리적 픽셀 좌표
        
        Args:
            x: 논리적 X 좌표
            y: 논리적 Y 좌표
            width: 논리적 너비
            height: 논리적 높이
            
        Note:
            입력값은 논리적 픽셀 좌표입니다. (DPI 스케일링 적용 전)
            get_capture_region()은 물리적 픽셀 좌표를 반환합니다.
        """
        # 입력 검증
        if width <= 0 or height <= 0:
            return

        # 최소 크기 보장
        width = max(width, self.min_capture_size)
        height = max(height, self.min_capture_size)

        # 전체 창 크기 계산 (하단 텍스트 공간 포함)
        total_width = width + 2 * self.padding + 2 * self.border_width
        total_height = height + 2 * self.padding + 2 * self.border_width + self.bottom_extra

        # 창 위치 계산 (캡처 영역 기준)
        win_x = x - self.padding - self.border_width
        win_y = y - self.padding - self.border_width

        self.SetPosition((win_x, win_y))
        self.SetSize((total_width, total_height))
        self._emit_region()

    def _refresh_after_resize(self):
        """크기 변경 후 지연 갱신 (잘려 그려짐 방지)"""
        try:
            if self and self.IsShown():
                self.Refresh(True)
                self.Update()
        except (RuntimeError, AttributeError):
            pass

    def set_capture_size(self, width: int, height: int):
        """캡처 크기만 변경 (위치 유지). width, height가 get_capture_size() 반환값과 정확히 일치하도록 계산."""
        # get_capture_size() = border_rect - 2*border_offset 이므로
        # border_rect = (width + 2*border_offset, height + 2*border_offset)
        # total = border_rect + 2*padding (+ bottom_extra)
        border_offset = (self.border_width + 1) // 2
        total_width = width + 2 * self.padding + 2 * border_offset
        total_height = height + 2 * self.padding + 2 * border_offset + self.bottom_extra

        # 위치는 유지하고 크기만 변경
        self.SetSize((total_width, total_height))

        # Win32 API로 크기 강제 (Layered 윈도우 호환)
        pos = self.GetPosition()
        self._force_win32_size(pos.x, pos.y, total_width, total_height)

        # 축소 시 잘려 그려지는 문제 방지: 강제 무효화 및 다시 그리기
        self.Refresh(True)
        self.Update()
        # 레이어드 윈도우에서 크기 변경 후 한 번 더 지연 갱신 (잔상 제거)
        wx.CallLater(50, self._refresh_after_resize)
        self._emit_region()
