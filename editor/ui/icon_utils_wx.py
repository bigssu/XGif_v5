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

    PRIMARY = "#dbe6f2"
    MUTED = "#7f8b9a"
    ACCENT = "#8bbcff"
    BLUE = "#8bbcff"
    CYAN = "#7cc7d9"
    TEAL = "#79c7b1"
    AMBER = "#d6aa63"
    ROSE = "#d98a92"
    LAVENDER = "#b8a7ee"
    STEEL = "#a8b5c5"

    # 액션 색상
    APPLY = PRIMARY
    CANCEL = PRIMARY
    DELETE = PRIMARY

    # 기능별 색상
    CROP = PRIMARY
    RESIZE = PRIMARY
    EFFECTS = PRIMARY
    TEXT = PRIMARY
    STICKER = PRIMARY
    SPEED = PRIMARY
    PENCIL = PRIMARY

    # 기타 색상
    OPEN_FILE = PRIMARY
    FRAME = PRIMARY
    ROTATE = PRIMARY
    FLIP = PRIMARY
    REVERSE = PRIMARY
    YOYO = PRIMARY
    REDUCE = PRIMARY
    TIME = PRIMARY
    ADD = PRIMARY
    PLAY = PRIMARY
    PAUSE = PRIMARY

    _BY_ICON = {
        "open_file": AMBER,
        "text": BLUE,
        "font_size": BLUE,
        "sticker": LAVENDER,
        "pencil": AMBER,
        "crop": AMBER,
        "resize": CYAN,
        "effects": LAVENDER,
        "color_palette": LAVENDER,
        "rotate": BLUE,
        "flip_h": STEEL,
        "flip_v": STEEL,
        "reverse": ROSE,
        "yoyo": CYAN,
        "speed": AMBER,
        "reduce": TEAL,
        "frame": STEEL,
        "delete": ROSE,
        "clear": ROSE,
        "exit": STEEL,
        "add": TEAL,
        "apply": BLUE,
        "cancel": STEEL,
        "play": TEAL,
        "pause": AMBER,
        "time": CYAN,
        "clock": CYAN,
        "target": BLUE,
        "outline": AMBER,
        "animation": LAVENDER,
        "blink": AMBER,
        "position": BLUE,
        "style": LAVENDER,
        "width": STEEL,
    }

    @classmethod
    def for_icon(cls, icon_type: str) -> str:
        return cls._BY_ICON.get(icon_type, cls.PRIMARY)


class IconFactory:
    """통일된 스타일의 아이콘 생성 팩토리 (wxPython)"""

    # 기본 아이콘 크기
    DEFAULT_SIZE = 24
    TOOLBAR_SIZE = 32
    BUTTON_SIZE = 32

    # 기본 펜 두께
    DEFAULT_PEN_WIDTH = 2

    # 비트맵 캐시 — (icon_type, size, color) → wx.Bitmap
    _cache: dict = {}

    @classmethod
    def _create_transparent_bitmap(cls, width: int, height: int) -> wx.Bitmap:
        """알파 채널이 완전 투명으로 초기화된 비트맵 생성

        Windows에서 wx.MemoryDC.Clear()는 알파를 0으로 설정하지 않으므로
        wx.Image를 통해 명시적으로 알파를 초기화합니다.
        """
        return wx.Bitmap.FromRGBA(width, height, 0, 0, 0, 0)

    @classmethod
    def create_bitmap(cls, icon_type: str, size: Optional[int] = None, color: Optional[str] = None) -> wx.Bitmap:
        """아이콘 비트맵 생성 (캐시 지원)

        Args:
            icon_type: 아이콘 타입 (예: 'apply', 'cancel', 'delete', 'crop' 등)
            size: 아이콘 크기 (기본: 24)
            color: 아이콘 색상 (기본: 타입별 기본 색상)

        Returns:
            wx.Bitmap: 생성된 아이콘 비트맵
        """
        if size is None:
            size = cls.DEFAULT_SIZE

        cache_key = (icon_type, size, color)
        cached = cls._cache.get(cache_key)
        if cached is not None:
            return cached

        # 알파가 투명으로 초기화된 비트맵 생성
        bitmap = cls._create_transparent_bitmap(size, size)
        dc = wx.MemoryDC(bitmap)

        # 안티앨리어싱 사용
        gc = wx.GraphicsContext.Create(dc)
        if gc:
            # 최신 툴바는 모든 아이콘을 같은 stroke/색상 언어로 그린다.
            # 기존 개별 draw_* 구현은 하위 호환 fallback으로만 남긴다.
            if cls._draw_modern_icon(gc, dc, icon_type, size, color):
                pass
            else:
                draw_method = getattr(cls, f'_draw_{icon_type}', None)
                if draw_method:
                    draw_method(gc, dc, size, color)

            del gc

        dc.SelectObject(wx.NullBitmap)
        cls._cache[cache_key] = bitmap
        return bitmap

    @classmethod
    def _icon_color(cls, icon_type: str, color: Optional[str] = None) -> wx.Colour:
        return wx.Colour(color or IconColors.for_icon(icon_type))

    @classmethod
    def _stroke_width(cls, size: int) -> float:
        return max(1.8, round(size / 14, 1))

    @classmethod
    def _set_stroke(cls, gc: wx.GraphicsContext, c: wx.Colour, size: int, *, width: Optional[float] = None):
        info = wx.GraphicsPenInfo(c).Width(width or cls._stroke_width(size)).Cap(wx.CAP_ROUND).Join(wx.JOIN_ROUND)
        gc.SetPen(gc.CreatePen(info))
        gc.SetBrush(wx.NullGraphicsBrush)

    @classmethod
    def _set_fill(cls, gc: wx.GraphicsContext, c: wx.Colour):
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(c)))

    @classmethod
    def _stroke_lines(cls, gc: wx.GraphicsContext, points):
        path = gc.CreatePath()
        for item in points:
            if item is None:
                continue
            start, end = item
            path.MoveToPoint(*start)
            path.AddLineToPoint(*end)
        gc.StrokePath(path)

    @classmethod
    def _draw_arrow(cls, gc: wx.GraphicsContext, start, end, head: float = 4.5):
        sx, sy = start
        ex, ey = end
        path = gc.CreatePath()
        path.MoveToPoint(sx, sy)
        path.AddLineToPoint(ex, ey)
        angle = math.atan2(ey - sy, ex - sx)
        for delta in (math.pi * 0.82, -math.pi * 0.82):
            hx = ex + head * math.cos(angle + delta)
            hy = ey + head * math.sin(angle + delta)
            path.MoveToPoint(ex, ey)
            path.AddLineToPoint(hx, hy)
        gc.StrokePath(path)

    @classmethod
    def _draw_modern_icon(cls, gc: wx.GraphicsContext, dc: wx.DC, icon_type: str, size: int, color: Optional[str]) -> bool:
        """단일 모노라인 아이콘 세트.

        모든 아이콘은 투명 캔버스 위에 같은 두께와 같은 색으로 그려져
        툴바가 서로 다른 앱에서 가져온 것처럼 보이지 않게 한다.
        """
        c = cls._icon_color(icon_type, color)
        cls._set_stroke(gc, c, size)
        optical_adjust = {
            "open_file": -1.0,
            "rotate": -0.5,
            "speed": -0.5,
            "effects": -0.5,
            "text": 1.0,
            "sticker": -0.5,
            "pencil": -0.5,
            "crop": 0.5,
            "reduce": 1.0,
            "play": 0.5,
            "reverse": 0.5,
            "delete": 0.5,
            "flip_h": -0.5,
            "flip_v": -0.5,
            "yoyo": -0.5,
            "font_size": 0.5,
            "target": 0.5,
        }
        m = max(3, min(size * 0.30, size * 0.18 + optical_adjust.get(icon_type, 0)))
        cx = cy = size / 2
        u = size / 24
        known = {
            "apply", "cancel", "exit", "delete", "clear", "open_file", "crop", "resize",
            "rotate", "flip_h", "flip_v", "effects", "text", "sticker", "pencil", "play",
            "pause", "speed", "reverse", "yoyo", "reduce", "frame", "time", "add",
            "font_size", "outline", "animation", "blink", "position", "clock", "target",
            "color_palette", "style", "width",
        }
        if icon_type not in known:
            return False

        path = gc.CreatePath()

        if icon_type == "apply":
            path.MoveToPoint(m + 1, cy)
            path.AddLineToPoint(cx - 2, size - m - 1)
            path.AddLineToPoint(size - m, m + 1)
            gc.StrokePath(path)
        elif icon_type in {"cancel", "clear"}:
            cls._stroke_lines(gc, [((m, m), (size - m, size - m)), ((size - m, m), (m, size - m))])
        elif icon_type == "exit":
            gc.DrawRoundedRectangle(m, m, size * 0.42, size - 2 * m, 2)
            cls._draw_arrow(gc, (cx - 1, cy), (size - m, cy))
        elif icon_type == "delete":
            gc.DrawRoundedRectangle(4 * u, 5 * u, 16 * u, 14 * u, 2 * u)
            cls._stroke_lines(gc, [
                ((7 * u, 5 * u), (7 * u, 19 * u)),
                ((17 * u, 5 * u), (17 * u, 19 * u)),
                ((5.5 * u, 8 * u), (7 * u, 8 * u)),
                ((5.5 * u, 12 * u), (7 * u, 12 * u)),
                ((5.5 * u, 16 * u), (7 * u, 16 * u)),
                ((17 * u, 8 * u), (18.5 * u, 8 * u)),
                ((17 * u, 12 * u), (18.5 * u, 12 * u)),
                ((17 * u, 16 * u), (18.5 * u, 16 * u)),
                ((9.5 * u, 9.5 * u), (14.5 * u, 14.5 * u)),
                ((14.5 * u, 9.5 * u), (9.5 * u, 14.5 * u)),
            ])
        elif icon_type == "open_file":
            path.MoveToPoint(3 * u, 9 * u)
            path.AddLineToPoint(3 * u, 19 * u)
            path.AddLineToPoint(21 * u, 19 * u)
            path.AddLineToPoint(21 * u, 10 * u)
            path.AddLineToPoint(12 * u, 10 * u)
            path.AddLineToPoint(10 * u, 7 * u)
            path.AddLineToPoint(3 * u, 7 * u)
            path.CloseSubpath()
            gc.StrokePath(path)
        elif icon_type == "crop":
            cls._stroke_lines(gc, [
                ((6 * u, 3 * u), (6 * u, 18 * u)),
                ((3 * u, 6 * u), (18 * u, 6 * u)),
                ((18 * u, 6 * u), (18 * u, 21 * u)),
                ((6 * u, 18 * u), (21 * u, 18 * u)),
            ])
        elif icon_type == "resize":
            gc.DrawRoundedRectangle(4 * u, 4 * u, 12 * u, 12 * u, 2 * u)
            cls._draw_arrow(gc, (10 * u, 10 * u), (21 * u, 21 * u), head=4 * u)
            cls._stroke_lines(gc, [
                ((16 * u, 21 * u), (21 * u, 21 * u)),
                ((21 * u, 16 * u), (21 * u, 21 * u)),
            ])
        elif icon_type == "rotate":
            path.AddArc(cx, cy, 8 * u, math.radians(35), math.radians(330), True)
            gc.StrokePath(path)
            cls._stroke_lines(gc, [
                ((18.5 * u, 5.5 * u), (21 * u, 5.5 * u)),
                ((21 * u, 5.5 * u), (21 * u, 8 * u)),
                ((18.5 * u, 18.5 * u), (15.5 * u, 18.5 * u)),
            ])
        elif icon_type in {"flip_h", "flip_v"}:
            if icon_type == "flip_h":
                cls._stroke_lines(gc, [((cx, 4 * u), (cx, 20 * u))])
                path.MoveToPoint(m, cy)
                path.AddLineToPoint(cx - 4, m + 4)
                path.AddLineToPoint(cx - 4, size - m - 4)
                path.CloseSubpath()
                path.MoveToPoint(size - m, cy)
                path.AddLineToPoint(cx + 4, m + 4)
                path.AddLineToPoint(cx + 4, size - m - 4)
                path.CloseSubpath()
            else:
                cls._stroke_lines(gc, [((4 * u, cy), (20 * u, cy))])
                path.MoveToPoint(cx, m)
                path.AddLineToPoint(m + 4, cy - 4)
                path.AddLineToPoint(size - m - 4, cy - 4)
                path.CloseSubpath()
                path.MoveToPoint(cx, size - m)
                path.AddLineToPoint(m + 4, cy + 4)
                path.AddLineToPoint(size - m - 4, cy + 4)
                path.CloseSubpath()
            gc.StrokePath(path)
        elif icon_type == "effects":
            path.MoveToPoint(4 * u, 5 * u)
            path.AddLineToPoint(20 * u, 5 * u)
            path.AddLineToPoint(14 * u, 12 * u)
            path.AddLineToPoint(14 * u, 18.5 * u)
            path.AddLineToPoint(10 * u, 21 * u)
            path.AddLineToPoint(10 * u, 12 * u)
            path.CloseSubpath()
            gc.StrokePath(path)
            cls._stroke_lines(gc, [((7 * u, 9 * u), (17 * u, 9 * u))])
        elif icon_type == "text":
            font = wx.Font(
                max(9, int(size * 0.76)),
                wx.FONTFAMILY_SWISS,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_BOLD,
            )
            gc.SetFont(font, c)
            text_w, text_h = gc.GetTextExtent("T")[:2]
            gc.DrawText("T", (size - text_w) / 2, (size - text_h) / 2 - 0.5)
            cls._set_stroke(gc, c, size)
        elif icon_type == "font_size":
            font = wx.Font(
                max(9, int(size * 0.62)),
                wx.FONTFAMILY_SWISS,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_BOLD,
            )
            gc.SetFont(font, c)
            text_w, text_h = gc.GetTextExtent("T")[:2]
            gc.DrawText("T", 5 * u, (size - text_h) / 2 - 0.5)
            cls._set_stroke(gc, c, size, width=max(1.8, size / 14))
            arrow_x = 18 * u
            cls._stroke_lines(gc, [
                ((arrow_x, 6 * u), (arrow_x, 18 * u)),
                ((arrow_x, 6 * u), (15.5 * u, 8.7 * u)),
                ((arrow_x, 6 * u), (20.5 * u, 8.7 * u)),
                ((arrow_x, 18 * u), (15.5 * u, 15.3 * u)),
                ((arrow_x, 18 * u), (20.5 * u, 15.3 * u)),
            ])
            cls._set_stroke(gc, c, size)
        elif icon_type == "sticker":
            gc.DrawRoundedRectangle(3 * u, 12 * u, 7 * u, 7 * u, 1.5 * u)
            gc.DrawEllipse(13 * u, 4 * u, 7 * u, 7 * u)
            path.MoveToPoint(14 * u, 20 * u)
            path.AddLineToPoint(21 * u, 20 * u)
            path.AddLineToPoint(17.5 * u, 13 * u)
            path.CloseSubpath()
            gc.StrokePath(path)
        elif icon_type == "pencil":
            fill = wx.Colour(c.Red(), c.Green(), c.Blue(), 58)
            gc.SetBrush(gc.CreateBrush(wx.Brush(fill)))
            body_a = (7 * u, 17 * u)
            body_b = (16 * u, 8 * u)
            body_c = (20 * u, 12 * u)
            body_d = (11 * u, 21 * u)
            tip = (3.5 * u, 21.5 * u)
            path.MoveToPoint(*body_a)
            path.AddLineToPoint(*body_b)
            path.AddLineToPoint(*body_c)
            path.AddLineToPoint(*body_d)
            path.CloseSubpath()
            gc.StrokePath(path)
            cap = gc.CreatePath()
            cap.MoveToPoint(16 * u, 8 * u)
            cap.AddLineToPoint(18.5 * u, 5.5 * u)
            cap.AddLineToPoint(22 * u, 9 * u)
            cap.AddLineToPoint(20 * u, 12 * u)
            cap.CloseSubpath()
            gc.StrokePath(cap)
            cls._stroke_lines(gc, [
                (body_a, tip),
                (tip, body_d),
                ((15 * u, 9 * u), (19 * u, 13 * u)),
                ((6 * u, 18 * u), (10 * u, 22 * u)),
            ])
            gc.SetBrush(wx.NullGraphicsBrush)
        elif icon_type == "play":
            path.MoveToPoint(m + 3, m)
            path.AddLineToPoint(size - m, cy)
            path.AddLineToPoint(m + 3, size - m)
            path.CloseSubpath()
            gc.StrokePath(path)
        elif icon_type == "pause":
            cls._stroke_lines(gc, [((cx - 5, m), (cx - 5, size - m)), ((cx + 5, m), (cx + 5, size - m))])
        elif icon_type == "speed":
            cls._set_stroke(gc, c, size, width=max(1.9, size / 13))
            path.AddArc(12 * u, 16 * u, 8 * u, math.radians(205), math.radians(335), False)
            gc.StrokePath(path)
            cls._stroke_lines(gc, [
                ((5.5 * u, 16.5 * u), (4 * u, 18 * u)),
                ((7.2 * u, 10.5 * u), (5.5 * u, 9 * u)),
                ((12 * u, 8 * u), (12 * u, 5.5 * u)),
                ((16.8 * u, 10.5 * u), (18.5 * u, 9 * u)),
                ((18.5 * u, 16.5 * u), (20 * u, 18 * u)),
                ((7 * u, 20 * u), (17 * u, 20 * u)),
            ])
            cls._set_stroke(gc, c, size, width=max(2.2, size / 11))
            cls._stroke_lines(gc, [((12 * u, 16 * u), (17.2 * u, 10.8 * u))])
            gc.DrawEllipse(10.6 * u, 14.6 * u, 2.8 * u, 2.8 * u)
            cls._set_stroke(gc, c, size)
        elif icon_type == "reverse":
            path.MoveToPoint(20 * u, 5 * u)
            path.AddLineToPoint(12 * u, cy)
            path.AddLineToPoint(20 * u, 19 * u)
            path.CloseSubpath()
            path.MoveToPoint(12 * u, 5 * u)
            path.AddLineToPoint(4 * u, cy)
            path.AddLineToPoint(12 * u, 19 * u)
            path.CloseSubpath()
            gc.StrokePath(path)
        elif icon_type == "yoyo":
            cls._draw_arrow(gc, (5 * u, 8 * u), (19 * u, 8 * u), head=4 * u)
            cls._draw_arrow(gc, (19 * u, 16 * u), (5 * u, 16 * u), head=4 * u)
        elif icon_type == "reduce":
            gc.DrawRoundedRectangle(4 * u, 5 * u, 16 * u, 14 * u, 2 * u)
            cls._stroke_lines(gc, [
                ((7 * u, 5 * u), (7 * u, 19 * u)),
                ((17 * u, 5 * u), (17 * u, 19 * u)),
                ((5.5 * u, 8 * u), (7 * u, 8 * u)),
                ((5.5 * u, 12 * u), (7 * u, 12 * u)),
                ((5.5 * u, 16 * u), (7 * u, 16 * u)),
                ((17 * u, 8 * u), (18.5 * u, 8 * u)),
                ((17 * u, 12 * u), (18.5 * u, 12 * u)),
                ((17 * u, 16 * u), (18.5 * u, 16 * u)),
                ((9.5 * u, 12 * u), (14.5 * u, 12 * u)),
            ])
        elif icon_type == "frame":
            gc.DrawRoundedRectangle(m, m, size - 2 * m, size - 2 * m, 2)
            cls._stroke_lines(gc, [((cx, m), (cx, size - m)), ((m, cy), (size - m, cy))])
        elif icon_type in {"time", "clock"}:
            gc.DrawEllipse(m, m, size - 2 * m, size - 2 * m)
            cls._stroke_lines(gc, [((cx, cy), (cx, m + 6)), ((cx, cy), (cx + 6, cy + 3))])
        elif icon_type == "add":
            cls._stroke_lines(gc, [((cx, m), (cx, size - m)), ((m, cy), (size - m, cy))])
        elif icon_type == "outline":
            gc.DrawRoundedRectangle(m, m, size - 2 * m, size - 2 * m, 3)
            gc.DrawRoundedRectangle(m + 5, m + 5, size - 2 * m - 10, size - 2 * m - 10, 2)
        elif icon_type == "animation":
            for offset in (-5, 0, 5):
                path = gc.CreatePath()
                y = cy + offset
                path.MoveToPoint(m, y)
                path.AddCurveToPoint(m + 5, y - 4, cx - 4, y + 4, cx + 1, y)
                path.AddCurveToPoint(cx + 7, y - 4, size - m - 5, y + 4, size - m, y)
                gc.StrokePath(path)
        elif icon_type == "blink":
            cls._stroke_lines(gc, [
                ((cx, m), (cx, size - m)), ((m, cy), (size - m, cy)),
                ((m + 5, m + 5), (size - m - 5, size - m - 5)),
                ((size - m - 5, m + 5), (m + 5, size - m - 5)),
            ])
        elif icon_type == "position":
            gc.DrawEllipse(m + 3, m + 3, size - 2 * m - 6, size - 2 * m - 6)
            cls._stroke_lines(gc, [((cx, m), (cx, size - m)), ((m, cy), (size - m, cy))])
        elif icon_type == "target":
            for offset in (0, 3, 6):
                gc.DrawRoundedRectangle(m + offset, m + 6 - offset, size - 2 * m - 6, size - 2 * m - 8, 2)
        elif icon_type == "color_palette":
            for x, y in ((m + 2, m + 2), (size - m - 9, m + 2), (m + 2, size - m - 9), (size - m - 9, size - m - 9)):
                gc.DrawEllipse(x, y, 7, 7)
        elif icon_type == "style":
            gc.DrawRoundedRectangle(size - m - 8, m, 7, 10, 2)
            cls._stroke_lines(gc, [((size - m - 6, m + 10), (m + 4, size - m - 3))])
            gc.DrawRoundedRectangle(m, size - m - 7, 11, 5, 2)
        elif icon_type == "width":
            cls._stroke_lines(gc, [
                ((m, m + 3), (size - m, m + 3)),
                ((m, cy), (size - m, cy)),
                ((m, size - m - 3), (size - m, size - m - 3)),
            ])

        return True

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
