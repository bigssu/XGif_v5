"""
TimelineWidget - 프레임 타임라인 (wxPython 버전)

PyQt6 QScrollArea를 wx.ScrolledWindow로 마이그레이션
wx.BufferedPaintDC를 사용한 고성능 렌더링
"""
import wx
from typing import Optional, List, TYPE_CHECKING
from PIL import Image
from .style_constants_wx import Colors, Fonts
from ..utils.image_utils import pil_to_wx_bitmap
from ..utils.wx_events import (
    FrameSelectedEvent, FramesReorderedEvent, FrameDelayChangedEvent
)

if TYPE_CHECKING:
    from .main_window import MainWindow


class TimelineWidget(wx.ScrolledCanvas):
    """프레임 타임라인 위젯 (wxPython)"""

    THUMB_WIDTH = 80
    THUMB_HEIGHT = 60      # 썸네일 영역 높이 (텍스트 제외)
    TEXT_HEIGHT = 18       # 텍스트 영역 높이
    TOTAL_HEIGHT = 78      # 총 높이 (THUMB_HEIGHT + TEXT_HEIGHT)
    THUMB_PADDING = 5
    FRAME_SPACING = 10

    def __init__(self, main_window: 'MainWindow'):
        super().__init__(main_window)
        self._main_window = main_window

        # 썸네일 캐시
        self._thumbnails: List[Optional[wx.Bitmap]] = []

        # 드래그 상태
        self._drag_start_index = -1
        self._drag_target_index = -1
        self._is_dragging = False

        # 스크롤 설정
        self.SetScrollRate(10, 0)  # 수평 스크롤만
        self.SetBackgroundColour(Colors.BG_PRIMARY)

        # 최소 높이 설정
        min_height = self.TOTAL_HEIGHT + self.THUMB_PADDING * 2 + 10
        self.SetMinSize((-1, min_height))

        # 이벤트 바인딩
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_mouse_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_mouse_up)
        self.Bind(wx.EVT_MOTION, self._on_mouse_move)
        self.Bind(wx.EVT_LEFT_DCLICK, self._on_double_click)
        self.Bind(wx.EVT_KEY_DOWN, self._on_key_down)

    def refresh(self):
        """타임라인 새로고침 (썸네일 캐시 초기화 + 재생성은 지연)"""
        self._thumbnails.clear()
        self._generate_thumbnails()
        self._update_size()
        self.Refresh()

    def clear_cache(self):
        """썸네일 캐시 정리"""
        self._thumbnails.clear()

    def _generate_thumbnails(self):
        """썸네일 캐시 크기를 프레임 수에 맞춤 (실제 생성은 _get_thumbnail에서 지연)"""
        frames = self._main_window.frames
        count = frames.frame_count if frames else 0
        # 기존 캐시와 크기가 다르면 리셋
        if len(self._thumbnails) != count:
            self._thumbnails = [None] * count

    def _get_thumbnail(self, index: int) -> Optional[wx.Bitmap]:
        """인덱스의 썸네일을 지연 생성하여 반환"""
        if index < 0 or index >= len(self._thumbnails):
            return None
        if self._thumbnails[index] is not None:
            return self._thumbnails[index]
        # 지연 생성
        frames = self._main_window.frames
        if frames.is_empty or index >= frames.frame_count:
            return None
        try:
            frame = frames[index]
            if frame is None:
                return None
            thumb_size = min(self.THUMB_WIDTH - 4, self.THUMB_HEIGHT - 4)
            thumb = frame.get_thumbnail(thumb_size)
            if thumb is None:
                return None
            wx_bitmap = pil_to_wx_bitmap(thumb)
            if wx_bitmap:
                self._thumbnails[index] = wx_bitmap
                return wx_bitmap
        except Exception:
            pass
        return None

    def _update_size(self):
        """위젯 크기 업데이트"""
        frames = self._main_window.frames
        if frames.is_empty:
            virtual_width = 100
        else:
            virtual_width = (frames.frame_count * (self.THUMB_WIDTH + self.FRAME_SPACING)
                           + self.FRAME_SPACING)

        virtual_height = self.TOTAL_HEIGHT + self.THUMB_PADDING * 2

        # 가상 크기 설정 (스크롤 가능 영역)
        self.SetVirtualSize(virtual_width, virtual_height)

    def _on_paint(self, event):
        """페인트 이벤트 - wx.BufferedPaintDC로 플리커 방지"""
        dc = wx.BufferedPaintDC(self)
        self.PrepareDC(dc)  # 스크롤 오프셋 적용

        # 배경 지우기
        dc.SetBackground(wx.Brush(Colors.BG_PRIMARY))
        dc.Clear()

        frames = self._main_window.frames
        if frames.is_empty:
            # 빈 상태 표시
            dc.SetTextForeground(Colors.TEXT_MUTED)
            dc.DrawText("No frames", 20, self.THUMB_PADDING + 20)
            return

        current_index = frames.current_index

        # viewport 범위 계산 (보이는 프레임만 렌더링)
        scroll_x, _ = self.GetViewStart()
        scroll_x *= 10  # scroll rate 보정
        client_w = self.GetClientSize().GetWidth()
        frame_step = self.THUMB_WIDTH + self.FRAME_SPACING
        start_idx = max(0, (scroll_x - self.FRAME_SPACING) // frame_step)
        end_idx = min(frames.frame_count, (scroll_x + client_w) // frame_step + 2)

        # 보이는 프레임만 그리기
        for i in range(start_idx, end_idx):
            x = self.FRAME_SPACING + i * frame_step
            y = self.THUMB_PADDING

            is_selected = frames.is_selected(i)
            is_current = (i == current_index)

            self._draw_frame(dc, i, x, y, is_selected, is_current)

        # 드래그 삽입 위치 표시
        if self._is_dragging and self._drag_target_index >= 0:
            insert_x = (self.FRAME_SPACING +
                       self._drag_target_index * (self.THUMB_WIDTH + self.FRAME_SPACING) -
                       self.FRAME_SPACING // 2)
            dc.SetPen(wx.Pen(Colors.INFO, 2))
            dc.DrawLine(insert_x, self.THUMB_PADDING,
                       insert_x, self.THUMB_PADDING + self.TOTAL_HEIGHT)

    def _draw_frame(self, dc: wx.DC, index: int, x: int, y: int,
                   selected: bool, current: bool):
        """프레임 그리기"""
        if not self._main_window:
            return

        frames = self._main_window.frames
        if not frames or frames.is_empty:
            return

        if index < 0 or index >= frames.frame_count:
            return

        try:
            frame = frames[index]
            if not frame:
                return
        except (IndexError, AttributeError):
            return

        # 배경색
        if current:
            bg_color = wx.Colour(40, 76, 100)
            border_color = Colors.ACCENT
        elif selected:
            bg_color = wx.Colour(50, 50, 70)
            border_color = wx.Colour(100, 100, 160)
        else:
            bg_color = Colors.BG_CANVAS
            border_color = Colors.BORDER

        # 전체 프레임 배경 (썸네일 + 텍스트 영역)
        dc.SetBrush(wx.Brush(bg_color))
        dc.SetPen(wx.Pen(border_color, 1))
        dc.DrawRoundedRectangle(x, y, self.THUMB_WIDTH, self.TOTAL_HEIGHT, 4)

        # 썸네일 (상단 영역에 표시, 지연 생성)
        try:
            thumb = self._get_thumbnail(index)
            if thumb and thumb.IsOk():
                thumb_w = thumb.GetWidth()
                thumb_h = thumb.GetHeight()
                thumb_x = x + (self.THUMB_WIDTH - thumb_w) // 2
                # 썸네일 높이를 초과하지 않도록 중앙 배치
                thumb_y = y + 2 + (self.THUMB_HEIGHT - 4 - thumb_h) // 2
                thumb_y = max(y + 2, thumb_y)
                dc.DrawBitmap(thumb, thumb_x, thumb_y, True)
        except (IndexError, AttributeError):
            pass

        # 프레임 정보 (하단 텍스트 영역에 표시 - 썸네일과 분리)
        dc.SetTextForeground(Colors.TEXT_SECONDARY)
        font = Fonts.get_font(8)
        dc.SetFont(font)

        info = f"#{index + 1} {frame.delay_ms}ms"
        text_rect = wx.Rect(x, y + self.THUMB_HEIGHT + 2,
                          self.THUMB_WIDTH, self.TEXT_HEIGHT - 4)

        # 텍스트 중앙 정렬
        text_w, text_h = dc.GetTextExtent(info)
        text_x = text_rect.x + (text_rect.width - text_w) // 2
        text_y = text_rect.y + (text_rect.height - text_h) // 2
        dc.DrawText(info, text_x, text_y)

    def _get_frame_at_pos(self, pos: wx.Point) -> int:
        """위치에 있는 프레임 인덱스 반환"""
        # 스크롤 오프셋 적용
        x, y = self.CalcUnscrolledPosition(pos.x, pos.y)

        frames = self._main_window.frames
        if frames.is_empty:
            return -1

        index = (x - self.FRAME_SPACING // 2) // \
                (self.THUMB_WIDTH + self.FRAME_SPACING)

        if 0 <= index < frames.frame_count:
            return index
        return -1

    def scroll_to_frame(self, index: int):
        """특정 프레임으로 스크롤"""
        try:
            client_width = self.GetClientSize().GetWidth()
            if client_width <= 0:
                return

            x = self.FRAME_SPACING + index * (self.THUMB_WIDTH + self.FRAME_SPACING)
            scroll_value = x - client_width // 2 + self.THUMB_WIDTH // 2
            scroll_value = max(0, scroll_value)

            # 스크롤 단위로 변환 (SetScrollRate(10, 0)이므로 10으로 나눔)
            scroll_units = scroll_value // 10
            self.Scroll(scroll_units, 0)
        except Exception:
            pass

    # === 마우스 이벤트 ===
    def _on_mouse_down(self, event):
        """마우스 다운 이벤트"""
        self.SetFocus()

        index = self._get_frame_at_pos(event.GetPosition())
        if index < 0:
            event.Skip()
            return

        frames = self._main_window.frames

        if event.ControlDown():
            # Ctrl+클릭: 선택에 추가/제거
            frames.select_frame(index, add_to_selection=True)
        elif event.ShiftDown():
            # Shift+클릭: 범위 선택
            frames.select_range(frames.current_index, index)
        else:
            # 일반 클릭
            frames.select_frame(index)
            frames.current_index = index

        self._drag_start_index = index
        self.Refresh()
        if hasattr(self._main_window, '_canvas') and self._main_window._canvas:
            self._main_window._canvas.Refresh()

        event.Skip()

    def _on_mouse_up(self, event):
        """마우스 업 이벤트"""
        if self._is_dragging and self._drag_start_index >= 0 and self._drag_target_index >= 0:
            frames = self._main_window.frames
            if self._drag_start_index != self._drag_target_index:
                frames.move_frame(self._drag_start_index, self._drag_target_index)
                self._main_window._is_modified = True

                # 이벤트 발생
                evt = FramesReorderedEvent(self._drag_start_index, self._drag_target_index)
                wx.PostEvent(self, evt)

                self.refresh()

        self._is_dragging = False
        self._drag_start_index = -1
        self._drag_target_index = -1
        self.Refresh()

        event.Skip()

    def _on_mouse_move(self, event):
        """마우스 이동 이벤트"""
        if event.LeftIsDown() and self._drag_start_index >= 0:
            self._is_dragging = True

            # 스크롤 오프셋 적용
            x, y = self.CalcUnscrolledPosition(event.GetPosition().x, event.GetPosition().y)

            # 타겟 인덱스 계산
            self._drag_target_index = (x +
                (self.THUMB_WIDTH + self.FRAME_SPACING) // 2) // \
                (self.THUMB_WIDTH + self.FRAME_SPACING)

            frames = self._main_window.frames
            self._drag_target_index = max(0, min(self._drag_target_index, frames.frame_count))

            self.Refresh()

        event.Skip()

    def _on_double_click(self, event):
        """더블 클릭: 프레임 딜레이 편집 다이얼로그"""
        index = self._get_frame_at_pos(event.GetPosition())
        if index < 0:
            event.Skip()
            return

        frames = self._main_window.frames
        if frames.is_empty or index >= frames.frame_count:
            event.Skip()
            return

        frame = frames[index]
        if not frame or not hasattr(frame, "delay_ms"):
            event.Skip()
            return

        current_delay = max(10, frame.delay_ms)

        tr = getattr(self._main_window, "_translations", None)
        if tr:
            title = tr.tr("msg_frame_delay")
            label = tr.tr("msg_frame_delay_label")
        else:
            title = "Frame Delay"
            label = "Delay (ms):"

        # 입력 다이얼로그
        dlg = wx.NumberEntryDialog(
            self._main_window,
            label,
            "",
            title,
            current_delay,
            10,
            10000
        )

        if dlg.ShowModal() == wx.ID_OK:
            delay = dlg.GetValue()
            if delay >= 10:
                frame.delay_ms = delay
                if hasattr(self._main_window, "_on_delay_changed"):
                    self._main_window._on_delay_changed(index, delay)
                if hasattr(self._main_window, "_is_modified"):
                    self._main_window._is_modified = True

                # 이벤트 발생
                evt = FrameDelayChangedEvent(index, delay)
                wx.PostEvent(self, evt)

                self.Refresh()
                if hasattr(self._main_window, "_canvas") and self._main_window._canvas:
                    self._main_window._canvas.Refresh()

        dlg.Destroy()
        event.Skip()

    def _on_key_down(self, event):
        """키 이벤트 처리"""
        frames = self._main_window.frames
        keycode = event.GetKeyCode()

        if keycode == wx.WXK_LEFT:
            if frames.previous_frame():
                self.Refresh()
                self._main_window._canvas.Refresh()
        elif keycode == wx.WXK_RIGHT:
            if frames.next_frame():
                self.Refresh()
                self._main_window._canvas.Refresh()
        elif keycode == wx.WXK_DELETE:
            if hasattr(self._main_window, '_delete_frame'):
                self._main_window._delete_frame()
        elif keycode == wx.WXK_HOME:
            frames.go_to_first()
            self.Refresh()
            self._main_window._canvas.Refresh()
        elif keycode == wx.WXK_END:
            frames.go_to_last()
            self.Refresh()
            self._main_window._canvas.Refresh()
        else:
            event.Skip()
