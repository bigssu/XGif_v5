"""
IconUtils - 통일된 아이콘 스타일 시스템 (wxPython 버전)
모든 UI 컴포넌트에서 사용하는 아이콘을 일관된 스타일로 생성
"""
import wx
import math
import os
from typing import Optional

try:
    from .style_constants_wx import Colors
except ImportError:
    Colors = None


class IconColors:
    """통일된 아이콘 색상 팔레트"""

    # 액션 색상
    APPLY = "#81c784"       # 녹색 - 적용/확인
    CANCEL = "#4fc3f7"      # 파랑 - 취소/닫기
    DELETE = "#ff6b6b"      # 빨강 - 삭제/지우기

    # 기능별 색상
    CROP = "#9C27B0"        # 보라 - 자르기
    RESIZE = "#00BCD4"      # 청록 - 크기조절
    EFFECTS = "#FF9800"     # 주황 - 효과
    TEXT = "#4CAF50"        # 초록 - 텍스트
    STICKER = "#FFC107"     # 노랑 - 스티커
    SPEED = "#FF5722"       # 딥오렌지 - 속도
    PENCIL = "#FFC107"      # 노랑 - 펜슬

    # 기타 색상
    OPEN_FILE = "#FFA726"   # 오렌지 - 파일 열기
    FRAME = "#2196F3"       # 파랑 - 프레임
    ROTATE = "#3F51B5"      # 인디고 - 회전
    FLIP = "#607D8B"        # 블루그레이 - 뒤집기
    REVERSE = "#E91E63"     # 핑크 - 역재생
    YOYO = "#795548"        # 브라운 - 요요
    REDUCE = "#009688"      # 틸 - 줄이기
    TIME = "#4fc3f7"        # 파랑 - 시간
    ADD = "#81c784"         # 녹색 - 추가
    PLAY = "#4CAF50"        # 녹색 - 재생
    PAUSE = "#FF9800"       # 주황 - 일시정지


class IconFactory:
    """통일된 스타일의 아이콘 생성 팩토리 (wxPython)"""

    # 기본 아이콘 크기
    DEFAULT_SIZE = 24
    TOOLBAR_SIZE = 32
    BUTTON_SIZE = 32

    # 기본 펜 두께
    DEFAULT_PEN_WIDTH = 2

    @classmethod
    def _create_transparent_bitmap(cls, width: int, height: int) -> wx.Bitmap:
        """알파 채널이 완전 투명으로 초기화된 비트맵 생성

        Windows에서 wx.MemoryDC.Clear()는 알파를 0으로 설정하지 않으므로
        wx.Image를 통해 명시적으로 알파를 초기화합니다.
        """
        img = wx.Image(width, height)
        img.InitAlpha()
        # 알파 전체를 0(투명)으로 초기화
        img.SetAlpha(bytes([0] * (width * height)))
        # RGB도 0으로 (pre-multiplied alpha 환경에서 안전)
        img.SetData(bytes([0] * (width * height * 3)))
        return wx.Bitmap(img, 32)

    @classmethod
    def create_bitmap(cls, icon_type: str, size: Optional[int] = None, color: Optional[str] = None) -> wx.Bitmap:
        """아이콘 비트맵 생성

        Args:
            icon_type: 아이콘 타입 (예: 'apply', 'cancel', 'delete', 'crop' 등)
            size: 아이콘 크기 (기본: 24)
            color: 아이콘 색상 (기본: 타입별 기본 색상)

        Returns:
            wx.Bitmap: 생성된 아이콘 비트맵
        """
        if size is None:
            size = cls.DEFAULT_SIZE

        # 알파가 투명으로 초기화된 비트맵 생성
        bitmap = cls._create_transparent_bitmap(size, size)
        dc = wx.MemoryDC(bitmap)

        # 안티앨리어싱 사용
        gc = wx.GraphicsContext.Create(dc)
        if gc:
            # 아이콘 타입별 그리기
            draw_method = getattr(cls, f'_draw_{icon_type}', None)
            if draw_method:
                draw_method(gc, dc, size, color)
            else:
                print(f"Warning: Unknown icon type: {icon_type}")
            del gc

        dc.SelectObject(wx.NullBitmap)
        return bitmap

    # ==================== 액션 아이콘 ====================

    @classmethod
    def _draw_apply(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """적용/확인 아이콘 (체크마크)"""
        c = wx.Colour(color or IconColors.APPLY)
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH + 1).Cap(wx.CAP_ROUND).Join(wx.JOIN_ROUND))
        gc.SetPen(pen)

        m = size // 4
        # 체크마크
        path = gc.CreatePath()
        path.MoveToPoint(m, size // 2)
        path.AddLineToPoint(size // 2 - 2, size - m)
        path.AddLineToPoint(size - m, m)
        gc.StrokePath(path)

    @classmethod
    def _draw_cancel(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """취소 아이콘 (X)"""
        c = wx.Colour(color or IconColors.CANCEL)
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH + 1).Cap(wx.CAP_ROUND))
        gc.SetPen(pen)

        m = size // 4
        path = gc.CreatePath()
        path.MoveToPoint(m, m)
        path.AddLineToPoint(size - m, size - m)
        path.MoveToPoint(size - m, m)
        path.AddLineToPoint(m, size - m)
        gc.StrokePath(path)

    @classmethod
    def _draw_exit(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """종료 아이콘 (문과 화살표)"""
        c = wx.Colour(color or IconColors.CANCEL)
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen)
        gc.SetBrush(wx.NullGraphicsBrush)

        m = 4
        # 문 프레임
        gc.DrawRectangle(m, m, size // 2, size - 2*m)

        # 화살표
        arrow_start = size // 2 + 2
        arrow_y = size // 2
        path = gc.CreatePath()
        path.MoveToPoint(arrow_start, arrow_y)
        path.AddLineToPoint(size - m, arrow_y)
        path.MoveToPoint(size - m - 4, arrow_y - 4)
        path.AddLineToPoint(size - m, arrow_y)
        path.AddLineToPoint(size - m - 4, arrow_y + 4)
        gc.StrokePath(path)

    @classmethod
    def _draw_delete(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """삭제 아이콘 (휴지통)"""
        c = wx.Colour(color or IconColors.DELETE)
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen)
        gc.SetBrush(wx.NullGraphicsBrush)

        m = 4
        mid = size // 2

        # 뚜껑
        path = gc.CreatePath()
        path.MoveToPoint(m + 2, m + 2)
        path.AddLineToPoint(size - m - 2, m + 2)
        path.MoveToPoint(mid - 3, m)
        path.AddLineToPoint(mid + 3, m)

        # 몸통
        path.AddRectangle(m + 2, m + 4, size - 2*m - 4, size - m - 6)

        # 세로 줄
        line_top = m + 8
        line_bottom = size - m - 3
        path.MoveToPoint(mid - 4, line_top)
        path.AddLineToPoint(mid - 4, line_bottom)
        path.MoveToPoint(mid, line_top)
        path.AddLineToPoint(mid, line_bottom)
        path.MoveToPoint(mid + 4, line_top)
        path.AddLineToPoint(mid + 4, line_bottom)

        gc.StrokePath(path)

    @classmethod
    def _draw_clear(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """지우기 아이콘 (휴지통과 동일)"""
        cls._draw_delete(gc, dc, size, color)

    # ==================== 파일 아이콘 ====================

    @classmethod
    def _draw_open_file(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """파일 열기 아이콘 (폴더)"""
        c = wx.Colour(color or IconColors.OPEN_FILE)
        brush = gc.CreateBrush(wx.Brush(c))
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(brush)

        # 폴더 몸통
        path = gc.CreatePath()
        path.MoveToPoint(4, 10)
        path.AddLineToPoint(4, size - 4)
        path.AddLineToPoint(size - 4, size - 4)
        path.AddLineToPoint(size - 4, 10)
        path.CloseSubpath()
        gc.FillPath(path)

        # 폴더 탭
        path = gc.CreatePath()
        path.MoveToPoint(4, 10)
        path.AddLineToPoint(4, 6)
        path.AddLineToPoint(14, 6)
        path.AddLineToPoint(16, 10)
        path.CloseSubpath()
        gc.FillPath(path)

        # 폴더 앞면 (밝은 색)
        lighter = wx.Colour(
            min(255, int(c.Red() * 1.2)),
            min(255, int(c.Green() * 1.2)),
            min(255, int(c.Blue() * 1.2))
        )
        brush = gc.CreateBrush(wx.Brush(lighter))
        gc.SetBrush(brush)

        path = gc.CreatePath()
        path.MoveToPoint(4, 12)
        path.AddLineToPoint(4, size - 4)
        path.AddLineToPoint(size - 4, size - 4)
        path.AddLineToPoint(size - 4, 12)
        path.CloseSubpath()
        gc.FillPath(path)

    # ==================== 편집 아이콘 ====================

    @classmethod
    def _draw_crop(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """자르기 아이콘"""
        c = wx.Colour(color or IconColors.CROP)
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH + 0.5))
        gc.SetPen(pen)

        m = 6
        path = gc.CreatePath()
        # 왼쪽 상단 L
        path.MoveToPoint(m, m + 8)
        path.AddLineToPoint(m, m)
        path.AddLineToPoint(m + 8, m)

        # 오른쪽 하단 L
        path.MoveToPoint(size - m, size - m - 8)
        path.AddLineToPoint(size - m, size - m)
        path.AddLineToPoint(size - m - 8, size - m)

        gc.StrokePath(path)

        # 점선 사각형
        pen_dashed = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH).Style(wx.PENSTYLE_SHORT_DASH))
        gc.SetPen(pen_dashed)
        gc.DrawRectangle(m + 2, m + 2, size - 2*m - 4, size - 2*m - 4)

    @classmethod
    def _draw_resize(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """크기 조절 아이콘"""
        c = wx.Colour(color or IconColors.RESIZE)
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen)
        gc.SetBrush(wx.NullGraphicsBrush)

        m = 5
        # 사각형
        gc.DrawRectangle(m, m, size - 2*m - 6, size - 2*m - 6)

        # 대각선 화살표
        path = gc.CreatePath()
        path.MoveToPoint(size - m - 2, m + 8)
        path.AddLineToPoint(size - m - 2, size - m - 2)
        path.AddLineToPoint(m + 8, size - m - 2)
        path.MoveToPoint(size - m - 8, size - m - 8)
        path.AddLineToPoint(size - m - 2, size - m - 2)

        # 화살표 머리
        path.MoveToPoint(size - m - 2, size - m - 2)
        path.AddLineToPoint(size - m - 6, size - m - 2)
        path.MoveToPoint(size - m - 2, size - m - 2)
        path.AddLineToPoint(size - m - 2, size - m - 6)

        gc.StrokePath(path)

    @classmethod
    def _draw_rotate(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """회전 아이콘"""
        c = wx.Colour(color or IconColors.ROTATE)
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH + 0.5))
        gc.SetPen(pen)

        m = 5
        # Arc (300 degrees starting from 30 degrees)
        path = gc.CreatePath()
        path.AddArc(size / 2, size / 2, size / 2 - m, math.radians(30), math.radians(330), True)
        gc.StrokePath(path)

        # 화살표 머리
        path = gc.CreatePath()
        path.MoveToPoint(size - m - 2, m + 6)
        path.AddLineToPoint(size - m - 2, m + 2)
        path.AddLineToPoint(size - m - 6, m + 2)
        gc.StrokePath(path)

    @classmethod
    def _draw_flip_h(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """수평 뒤집기 아이콘"""
        c = wx.Colour(color or IconColors.FLIP)
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen)
        brush = gc.CreateBrush(wx.Brush(c))

        m = 5
        mid = size // 2

        # 왼쪽 삼각형 (채움)
        gc.SetBrush(brush)
        path = gc.CreatePath()
        path.MoveToPoint(m, mid)
        path.AddLineToPoint(mid - 2, m + 4)
        path.AddLineToPoint(mid - 2, size - m - 4)
        path.CloseSubpath()
        gc.FillPath(path)
        gc.StrokePath(path)

        # 오른쪽 삼각형 (선만)
        gc.SetBrush(wx.NullGraphicsBrush)
        path = gc.CreatePath()
        path.MoveToPoint(size - m, mid)
        path.AddLineToPoint(mid + 2, m + 4)
        path.AddLineToPoint(mid + 2, size - m - 4)
        path.CloseSubpath()
        gc.StrokePath(path)

        # 중앙 점선
        pen_dashed = gc.CreatePen(wx.GraphicsPenInfo(c).Width(1).Style(wx.PENSTYLE_SHORT_DASH))
        gc.SetPen(pen_dashed)
        path = gc.CreatePath()
        path.MoveToPoint(mid, m)
        path.AddLineToPoint(mid, size - m)
        gc.StrokePath(path)

    @classmethod
    def _draw_flip_v(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """수직 뒤집기 아이콘"""
        c = wx.Colour(color or IconColors.FLIP)
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen)
        brush = gc.CreateBrush(wx.Brush(c))

        m = 5
        mid = size // 2

        # 위쪽 삼각형 (채움)
        gc.SetBrush(brush)
        path = gc.CreatePath()
        path.MoveToPoint(mid, m)
        path.AddLineToPoint(m + 4, mid - 2)
        path.AddLineToPoint(size - m - 4, mid - 2)
        path.CloseSubpath()
        gc.FillPath(path)
        gc.StrokePath(path)

        # 아래쪽 삼각형 (선만)
        gc.SetBrush(wx.NullGraphicsBrush)
        path = gc.CreatePath()
        path.MoveToPoint(mid, size - m)
        path.AddLineToPoint(m + 4, mid + 2)
        path.AddLineToPoint(size - m - 4, mid + 2)
        path.CloseSubpath()
        gc.StrokePath(path)

        # 중앙 점선
        pen_dashed = gc.CreatePen(wx.GraphicsPenInfo(c).Width(1).Style(wx.PENSTYLE_SHORT_DASH))
        gc.SetPen(pen_dashed)
        path = gc.CreatePath()
        path.MoveToPoint(m, mid)
        path.AddLineToPoint(size - m, mid)
        gc.StrokePath(path)

    # ==================== 효과 아이콘 ====================

    @classmethod
    def _draw_effects(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """효과 아이콘 (색상 원)"""
        m = 6
        r = (size - 2*m) // 3

        gc.SetPen(wx.NullGraphicsPen)

        # 빨강
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour("#ff6b6b"))))
        gc.DrawEllipse(m, size//2 - r//2, r, r)

        # 초록
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour("#51cf66"))))
        gc.DrawEllipse(m + r - 2, m, r, r)

        # 파랑
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour("#339af0"))))
        gc.DrawEllipse(m + 2*r - 4, size//2 - r//2, r, r)

    @classmethod
    def _draw_text(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """텍스트 아이콘 (A)"""
        c = wx.Colour(color or IconColors.TEXT)
        font = wx.Font(int(size * 0.55), wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, faceName="Arial")
        dc.SetFont(font)
        dc.SetTextForeground(c)

        text_w, text_h = dc.GetTextExtent("A")
        x = (size - text_w) // 2
        y = (size - text_h) // 2
        dc.DrawText("A", x, y)

    @classmethod
    def _draw_sticker(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """스티커 아이콘 (별)"""
        c = wx.Colour(color or IconColors.STICKER)
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH))
        brush = gc.CreateBrush(wx.Brush(c))
        gc.SetPen(pen)
        gc.SetBrush(brush)

        cx, cy = size / 2, size / 2
        outer_r = size / 2 - 4
        inner_r = outer_r * 0.4

        path = gc.CreatePath()
        for i in range(10):
            angle = math.pi / 2 + i * math.pi / 5
            r = outer_r if i % 2 == 0 else inner_r
            x = cx + r * math.cos(angle)
            y = cy - r * math.sin(angle)
            if i == 0:
                path.MoveToPoint(x, y)
            else:
                path.AddLineToPoint(x, y)
        path.CloseSubpath()
        gc.FillPath(path)
        gc.StrokePath(path)

    @classmethod
    def _draw_pencil(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """펜슬 아이콘"""
        gc.SetPen(wx.NullGraphicsPen)

        # 연필 몸통 (노란색)
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(IconColors.PENCIL))))
        path = gc.CreatePath()
        path.MoveToPoint(6, size - 10)
        path.AddLineToPoint(10, size - 6)
        path.AddLineToPoint(size - 6, 10)
        path.AddLineToPoint(size - 10, 6)
        path.CloseSubpath()
        gc.FillPath(path)

        # 연필 끝 (분홍색 - 지우개)
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour("#FF8A80"))))
        path = gc.CreatePath()
        path.MoveToPoint(size - 10, 6)
        path.AddLineToPoint(size - 6, 10)
        path.AddLineToPoint(size - 3, 7)
        path.AddLineToPoint(size - 7, 3)
        path.CloseSubpath()
        gc.FillPath(path)

        # 연필 심 (어두운 부분)
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour("#5D4037"))))
        path = gc.CreatePath()
        path.MoveToPoint(6, size - 10)
        path.AddLineToPoint(10, size - 6)
        path.AddLineToPoint(4, size - 4)
        path.CloseSubpath()
        gc.FillPath(path)

    # ==================== 재생/프레임 아이콘 ====================

    @classmethod
    def _draw_play(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """재생 아이콘"""
        c = wx.Colour(color or IconColors.PLAY)
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(c)))

        m = size // 4
        path = gc.CreatePath()
        path.MoveToPoint(m, m)
        path.AddLineToPoint(m, size - m)
        path.AddLineToPoint(size - m, size // 2)
        path.CloseSubpath()
        gc.FillPath(path)

    @classmethod
    def _draw_pause(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """일시정지 아이콘"""
        c = wx.Colour(color or IconColors.PAUSE)
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(c)))

        m = size // 4
        bar_w = size // 5
        gc.DrawRectangle(m, m, bar_w, size - 2*m)
        gc.DrawRectangle(size - m - bar_w, m, bar_w, size - 2*m)

    @classmethod
    def _draw_speed(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """속도 아이콘 (게이지)"""
        c = wx.Colour(color or IconColors.SPEED)
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen)
        gc.SetBrush(wx.NullGraphicsBrush)

        m = 4
        # Arc (180 degrees starting from 0)
        path = gc.CreatePath()
        path.AddArc(size / 2, size / 2 + 4, size / 2 - m, math.radians(0), math.radians(180), False)
        gc.StrokePath(path)

        # 바늘
        cx, cy = size // 2, size // 2 + 4
        angle = math.radians(45)
        length = size // 2 - m - 4

        pen_needle = gc.CreatePen(wx.GraphicsPenInfo(wx.Colour("#ff4444")).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen_needle)
        path = gc.CreatePath()
        path.MoveToPoint(cx, cy)
        path.AddLineToPoint(cx + length * math.cos(angle), cy - length * math.sin(angle))
        gc.StrokePath(path)

    @classmethod
    def _draw_reverse(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """역재생 아이콘"""
        c = wx.Colour(color or IconColors.REVERSE)
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH))
        brush = gc.CreateBrush(wx.Brush(c))
        gc.SetPen(pen)
        gc.SetBrush(brush)

        m = 6
        path = gc.CreatePath()
        path.MoveToPoint(m, size // 2)
        path.AddLineToPoint(size - m, m + 2)
        path.AddLineToPoint(size - m, size - m - 2)
        path.CloseSubpath()
        gc.FillPath(path)
        gc.StrokePath(path)

    @classmethod
    def _draw_yoyo(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """요요 아이콘 (양방향 화살표)"""
        m = 5
        mid = size // 2

        # 오른쪽 화살표 (주황색)
        pen_orange = gc.CreatePen(wx.GraphicsPenInfo(wx.Colour("#FF9800")).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen_orange)
        path = gc.CreatePath()
        path.MoveToPoint(m, mid)
        path.AddLineToPoint(size - m - 4, mid)
        path.MoveToPoint(size - m - 4, mid)
        path.AddLineToPoint(size - m - 8, mid - 4)
        path.MoveToPoint(size - m - 4, mid)
        path.AddLineToPoint(size - m - 8, mid + 4)
        gc.StrokePath(path)

        # 왼쪽 화살표 (파란색)
        pen_blue = gc.CreatePen(wx.GraphicsPenInfo(wx.Colour("#2196F3")).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen_blue)
        path = gc.CreatePath()
        path.MoveToPoint(m + 4, mid + 6)
        path.AddLineToPoint(size - m, mid + 6)
        path.MoveToPoint(m + 4, mid + 6)
        path.AddLineToPoint(m + 8, mid + 2)
        path.MoveToPoint(m + 4, mid + 6)
        path.AddLineToPoint(m + 8, mid + 10)
        gc.StrokePath(path)

    @classmethod
    def _draw_reduce(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """프레임 줄이기 아이콘"""
        c = wx.Colour(color or IconColors.REDUCE)
        m = 4
        gap = 6
        w = 6

        gc.SetPen(wx.NullGraphicsPen)

        # 프레임들 (일부 투명)
        gc.SetBrush(gc.CreateBrush(wx.Brush(c)))
        gc.DrawRectangle(m, m + 4, w, size - 2*m - 8)

        lighter = wx.Colour(
            min(255, int(c.Red() * 1.5)),
            min(255, int(c.Green() * 1.5)),
            min(255, int(c.Blue() * 1.5))
        )
        gc.SetBrush(gc.CreateBrush(wx.Brush(lighter)))
        gc.DrawRectangle(m + gap + w, m + 4, w, size - 2*m - 8)

        gc.SetBrush(gc.CreateBrush(wx.Brush(c)))
        gc.DrawRectangle(m + 2*(gap + w), m + 4, w, size - 2*m - 8)

        gc.SetBrush(gc.CreateBrush(wx.Brush(lighter)))
        gc.DrawRectangle(m + 3*(gap + w), m + 4, w, size - 2*m - 8)

    @classmethod
    def _draw_frame(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """프레임/격자 아이콘"""
        c = wx.Colour(color or IconColors.FRAME)
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen)
        gc.SetBrush(wx.NullGraphicsBrush)

        m = 4
        # 외곽선
        gc.DrawRectangle(m, m, size - 2*m, size - 2*m)

        # 격자
        mid = size // 2
        path = gc.CreatePath()
        path.MoveToPoint(mid, m)
        path.AddLineToPoint(mid, size - m)
        path.MoveToPoint(m, mid)
        path.AddLineToPoint(size - m, mid)
        gc.StrokePath(path)

    @classmethod
    def _draw_time(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """시간 아이콘 (시계)"""
        c = wx.Colour(color or IconColors.TIME)
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen)
        gc.SetBrush(wx.NullGraphicsBrush)

        m = 3
        mid = size // 2

        # 원
        gc.DrawEllipse(m, m, size - 2*m, size - 2*m)

        # 시침
        path = gc.CreatePath()
        path.MoveToPoint(mid, mid)
        path.AddLineToPoint(mid, m + 5)
        path.MoveToPoint(mid, mid)
        path.AddLineToPoint(mid + 5, mid + 3)
        gc.StrokePath(path)

    @classmethod
    def _draw_add(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """추가 아이콘 (플러스)"""
        c = wx.Colour(color or IconColors.ADD)
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH + 1))
        gc.SetPen(pen)

        m = 6
        mid = size // 2
        path = gc.CreatePath()
        path.MoveToPoint(mid, m)
        path.AddLineToPoint(mid, size - m)
        path.MoveToPoint(m, mid)
        path.AddLineToPoint(size - m, mid)
        gc.StrokePath(path)

    # ==================== 툴바 컨트롤 아이콘 (컬러) ====================

    @classmethod
    def _draw_font_size(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """폰트 크기 아이콘 (T + 화살표) - 파란색"""
        c = wx.Colour(color or "#4fc3f7")
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen)

        # T 문자
        font = wx.Font(int(size * 0.4), wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, faceName="Arial")
        dc.SetFont(font)
        dc.SetTextForeground(c)
        text_w, text_h = dc.GetTextExtent("T")
        dc.DrawText("T", 2, (size - text_h) // 2)

        # 위아래 화살표
        arrow_x = size - 6
        path = gc.CreatePath()
        path.MoveToPoint(arrow_x, 4)
        path.AddLineToPoint(arrow_x, size - 4)
        # 위 화살표
        path.MoveToPoint(arrow_x - 2, 7)
        path.AddLineToPoint(arrow_x, 4)
        path.AddLineToPoint(arrow_x + 2, 7)
        # 아래 화살표
        path.MoveToPoint(arrow_x - 2, size - 7)
        path.AddLineToPoint(arrow_x, size - 4)
        path.AddLineToPoint(arrow_x + 2, size - 7)
        gc.StrokePath(path)

    @classmethod
    def _draw_outline(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """아웃라인/테두리 아이콘 - 주황색"""
        c = wx.Colour(color or "#ffa726")
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH + 1))
        gc.SetPen(pen)
        gc.SetBrush(wx.NullGraphicsBrush)

        m = 4
        # 외곽 사각형
        gc.DrawRectangle(m, m, size - 2*m, size - 2*m)

        # 내부 점선 사각형
        pen_dashed = gc.CreatePen(wx.GraphicsPenInfo(c).Width(1).Style(wx.PENSTYLE_SHORT_DASH))
        gc.SetPen(pen_dashed)
        gc.DrawRectangle(m + 3, m + 3, size - 2*m - 6, size - 2*m - 6)

    @classmethod
    def _draw_animation(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """애니메이션 아이콘 (움직임 물결) - 보라색"""
        c = wx.Colour(color or "#ab47bc")
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen)

        m = 4
        mid = size // 2

        # 물결선 3개
        for offset in [-5, 0, 5]:
            y = mid + offset
            path = gc.CreatePath()
            path.MoveToPoint(m, y)
            path.AddLineToPoint(m + 4, y - 2)
            path.AddLineToPoint(m + 8, y + 2)
            path.AddLineToPoint(m + 12, y - 2)
            path.AddLineToPoint(size - m, y)
            gc.StrokePath(path)

    @classmethod
    def _draw_blink(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """깜빡임 아이콘 (별 반짝임) - 노란색"""
        c = wx.Colour(color or "#ffd54f")
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen)

        mid = size // 2

        # 별 모양 십자
        path = gc.CreatePath()
        path.MoveToPoint(mid, 3)
        path.AddLineToPoint(mid, size - 3)
        path.MoveToPoint(3, mid)
        path.AddLineToPoint(size - 3, mid)

        # 대각선
        path.MoveToPoint(6, 6)
        path.AddLineToPoint(size - 6, size - 6)
        path.MoveToPoint(size - 6, 6)
        path.AddLineToPoint(6, size - 6)
        gc.StrokePath(path)

        # 중앙 원
        gc.SetBrush(gc.CreateBrush(wx.Brush(c)))
        gc.DrawEllipse(mid - 2, mid - 2, 4, 4)

    @classmethod
    def _draw_position(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """위치 아이콘 (십자가 + 점) - 초록색"""
        c = wx.Colour(color or "#66bb6a")
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen)

        mid = size // 2
        m = 3

        # 십자선
        path = gc.CreatePath()
        path.MoveToPoint(mid, m)
        path.AddLineToPoint(mid, size - m)
        path.MoveToPoint(m, mid)
        path.AddLineToPoint(size - m, mid)
        gc.StrokePath(path)

        # 중앙 점
        gc.SetBrush(gc.CreateBrush(wx.Brush(c)))
        gc.DrawEllipse(mid - 3, mid - 3, 6, 6)

    @classmethod
    def _draw_clock(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """시계 아이콘 (시간 간격용) - 시안색"""
        c = wx.Colour(color or "#4dd0e1")
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen)
        gc.SetBrush(wx.NullGraphicsBrush)

        m = 3
        mid = size // 2

        # 원
        gc.DrawEllipse(m, m, size - 2*m, size - 2*m)

        # 시침 분침
        path = gc.CreatePath()
        path.MoveToPoint(mid, mid)
        path.AddLineToPoint(mid, m + 4)
        path.MoveToPoint(mid, mid)
        path.AddLineToPoint(mid + 4, mid + 2)
        gc.StrokePath(path)

    @classmethod
    def _draw_target(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """타겟/적용대상 아이콘 (프레임 그룹) - 주황색"""
        c = wx.Colour(color or "#ff7043")
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen)
        gc.SetBrush(wx.NullGraphicsBrush)

        m = 3
        # 3개의 겹친 프레임
        gc.DrawRectangle(m, m + 4, size - 8, size - 10)
        gc.DrawRectangle(m + 2, m + 2, size - 8, size - 10)
        gc.DrawRectangle(m + 4, m, size - 8, size - 10)

    @classmethod
    def _draw_color_palette(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """색상 팔레트 아이콘"""
        m = 4
        r = (size - 2*m) // 3

        gc.SetPen(wx.NullGraphicsPen)

        # 빨강
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour("#ff6b6b"))))
        gc.DrawEllipse(m, m, r + 2, r + 2)

        # 초록
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour("#51cf66"))))
        gc.DrawEllipse(size - m - r - 2, m, r + 2, r + 2)

        # 파랑
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour("#339af0"))))
        gc.DrawEllipse(m, size - m - r - 2, r + 2, r + 2)

        # 노랑
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour("#ffd43b"))))
        gc.DrawEllipse(size - m - r - 2, size - m - r - 2, r + 2, r + 2)

    @classmethod
    def _draw_style(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """스타일 아이콘 (브러시) - 분홍색"""
        c = wx.Colour(color or "#f06292")
        pen = gc.CreatePen(wx.GraphicsPenInfo(c).Width(cls.DEFAULT_PEN_WIDTH))
        gc.SetPen(pen)
        gc.SetBrush(wx.NullGraphicsBrush)

        # 브러시 손잡이
        gc.DrawRectangle(size - 8, 3, 5, 10)

        # 브러시 머리
        gc.SetBrush(gc.CreateBrush(wx.Brush(c)))
        path = gc.CreatePath()
        path.MoveToPoint(3, size - 3)
        path.AddLineToPoint(size - 8, 13)
        path.AddLineToPoint(size - 3, 13)
        path.AddLineToPoint(8, size - 3)
        path.CloseSubpath()
        gc.FillPath(path)
        gc.StrokePath(path)

    @classmethod
    def _draw_width(cls, gc: wx.GraphicsContext, dc: wx.DC, size: int, color: Optional[str] = None):
        """너비/두께 아이콘 - 청회색"""
        c = wx.Colour(color or "#78909c")
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(c)))

        m = 4
        # 다양한 두께의 선
        gc.DrawRectangle(m, m, size - 2*m, 2)
        gc.DrawRectangle(m, m + 5, size - 2*m, 4)
        gc.DrawRectangle(m, m + 12, size - 2*m, 6)


def create_icon_button(icon_type: str, tooltip: str, size: int = 40,
                       dark_bg: bool = True) -> wx.Button:
    """아이콘 버튼 생성 헬퍼 함수 (wxPython)

    Args:
        icon_type: 아이콘 타입
        tooltip: 툴팁 텍스트
        size: 버튼 크기
        dark_bg: 어두운 배경 사용 여부

    Returns:
        wx.Button: 생성된 버튼
    """
    btn = wx.Button(None, size=(size, size))
    btn.SetToolTip(tooltip)
    btn.SetCursor(wx.Cursor(wx.CURSOR_HAND))

    # 아이콘 생성
    icon_size = size - 8
    bitmap = IconFactory.create_bitmap(icon_type, icon_size)
    btn.SetBitmap(bitmap)

    # 스타일 적용
    if dark_bg and Colors:
        btn.SetBackgroundColour(Colors.BG_TERTIARY)
        btn.SetForegroundColour(Colors.TEXT_PRIMARY)
    else:
        btn.SetBackgroundColour(wx.Colour(255, 255, 255))

    return btn


def load_icon(path: str, size: Optional[int] = None,
              mask_black: bool = True) -> wx.Bitmap:
    """이미지 파일에서 아이콘 비트맵을 로드하는 헬퍼 함수

    PNG는 알파 채널을 유지하고, JPG/BMP 등 알파가 없는 포맷은
    검은색(0,0,0)을 투명 마스크로 지정합니다.

    Args:
        path: 이미지 파일 경로 (PNG, JPG, BMP 등)
        size: 리사이즈할 크기 (정사각형). None이면 원본 크기 유지
        mask_black: 알파 채널이 없을 때 검은색을 투명 마스크로 지정할지 여부

    Returns:
        wx.Bitmap: 투명도가 적용된 비트맵
    """
    if not os.path.isfile(path):
        # 파일이 없으면 빈 투명 비트맵 반환
        s = size or IconFactory.DEFAULT_SIZE
        return IconFactory._create_transparent_bitmap(s, s)

    ext = os.path.splitext(path)[1].lower()

    # wx.Image로 로드 (포맷 자동 감지)
    img = wx.Image(path, wx.BITMAP_TYPE_ANY)
    if not img.IsOk():
        s = size or IconFactory.DEFAULT_SIZE
        return IconFactory._create_transparent_bitmap(s, s)

    # PNG: 알파 채널 유지
    if ext == '.png':
        if not img.HasAlpha():
            img.InitAlpha()
    else:
        # JPG, BMP 등: 알파 채널이 없으므로 검은색을 마스크로 지정
        if mask_black and not img.HasAlpha():
            img.SetMaskColour(0, 0, 0)

    # 리사이즈 (고품질 보간)
    if size is not None:
        orig_w, orig_h = img.GetWidth(), img.GetHeight()
        if orig_w != size or orig_h != size:
            img = img.Scale(size, size, wx.IMAGE_QUALITY_HIGH)

    # 비트맵 변환
    if img.HasAlpha():
        return wx.Bitmap(img, 32)
    else:
        bmp = wx.Bitmap(img)
        if img.HasMask():
            mask = wx.Mask(bmp, wx.Colour(0, 0, 0))
            bmp.SetMask(mask)
        return bmp
