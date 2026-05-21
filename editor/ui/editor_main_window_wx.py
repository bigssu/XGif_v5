"""
MainWindow - Honeycam 스타일 GIF 에디터 메인 윈도우 (wxPython 버전)
"""
import contextlib
import wx
import wx.adv
from pathlib import Path
from typing import Optional
import sys
import subprocess
import os

from .. import __version__, __last_modified__
from ..core import FrameCollection, GifDecoder, GifEncoder, UndoManager, gpu_utils
# wxPython 호환 Worker 사용
from ..core.worker_wx import get_worker_manager, VideoLoadWorker, FunctionWorker
from ..core.frame import get_memory_manager
from ..core.editor_gif_encoder import EncoderSettings
from ..utils.translations import Translations
from ..utils.logger import get_logger
from core.app_shutdown import ensure_exit_if_no_primary_windows
from ui.window_chrome import apply_dark_title_bar

# wxPython 버전 위젯 임포트
from .canvas_widget_wx import CanvasWidget
from .frame_list_widget_wx import FrameListWidget
from .icon_toolbar_wx import FlatIconButton, IconToolbar
from .style_constants_wx import Colors, Fonts, apply_button_style

# ── 다이얼로그 (wxPython 버전) ──────────────────────────────
from .dialogs.target_frame_hint_dialog_wx import TargetFrameHintDialog

from .save_dialog_wx import SaveDialog

# 인라인 툴바 (wxPython 버전) - 개별 임포트
from .inline_toolbars.speed_toolbar_wx import SpeedToolbar
from .inline_toolbars.resize_toolbar_wx import ResizeToolbar
from .inline_toolbars.effects_toolbar_wx import EffectsToolbar
from .inline_toolbars.text_toolbar_wx import TextToolbar
from .inline_toolbars.sticker_toolbar_wx import StickerToolbar
from .inline_toolbars.crop_toolbar_wx import CropToolbar
from .inline_toolbars.mosaic_toolbar_wx import MosaicToolbar
from .inline_toolbars.speech_bubble_toolbar_wx import SpeechBubbleToolbar
from .inline_toolbars.watermark_toolbar_wx import WatermarkToolbar
from .inline_toolbars.rotate_toolbar_wx import RotateToolbar
from .inline_toolbars.reduce_toolbar_wx import ReduceToolbar
from .inline_toolbars.pencil_toolbar_wx import PencilToolbar
from .property_bar_wx import PropertyBar

# 대용량 파일 열기 제한 (메모리 안전성)
MAX_EDITOR_FRAMES = 5000
MAX_EDITOR_MEMORY_MB = 1500


class FileDropTarget(wx.FileDropTarget):
    """파일 드래그 & 드롭 처리"""

    def __init__(self, window: 'MainWindow'):
        super().__init__()
        self._window = window

    def OnDropFiles(self, x, y, filenames):
        """파일이 드롭되었을 때"""
        if filenames:
            # 첫 번째 파일만 열기
            file_path = filenames[0]
            if GifDecoder.is_supported_file(file_path):
                wx.CallAfter(self._window.open_file, file_path)
                return True
        return False


class FlatEditorMenuBar(wx.Control):
    """Dark owner-drawn menu strip backed by existing wx.Menu popups."""

    def __init__(self, owner: 'MainWindow', parent=None):
        super().__init__(parent, size=(-1, 28), style=wx.BORDER_NONE)
        self._owner = owner
        self._items: list[tuple[str, wx.Menu]] = []
        self._rects: list[wx.Rect] = []
        self._hover_index = -1
        self.SetMinSize((-1, 28))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda _event: None)
        self.Bind(wx.EVT_MOTION, self._on_motion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_left_down)

    def set_items(self, items: list[tuple[str, wx.Menu]]) -> None:
        self._items = [(label.replace("&", ""), menu) for label, menu in items]
        self._hover_index = -1
        self.Refresh()

    def _layout_items(self, dc: wx.DC) -> list[wx.Rect]:
        rects = []
        x = 8
        h = self.GetClientSize().height
        for label, _menu in self._items:
            tw, _th = dc.GetTextExtent(label)
            width = tw + 18
            rects.append(wx.Rect(x, 3, width, max(20, h - 6)))
            x += width + 2
        return rects

    def _on_paint(self, _event):
        dc = wx.PaintDC(self)
        w, h = self.GetClientSize()
        dc.SetBackground(wx.Brush(Colors.RAIL_BG_ALT))
        dc.Clear()
        dc.SetFont(self.GetFont())
        self._rects = self._layout_items(dc)

        gc = wx.GraphicsContext.Create(dc)
        if gc:
            gc.SetPen(wx.Pen(Colors.DIVIDER_SUBTLE, 1))
            gc.StrokeLine(0, h - 1, w, h - 1)
            for idx, (label, _menu) in enumerate(self._items):
                rect = self._rects[idx]
                if idx == self._hover_index:
                    gc.SetBrush(wx.Brush(Colors.BG_CARD))
                    gc.SetPen(wx.Pen(Colors.BORDER_SOFT, 1))
                    gc.DrawRoundedRectangle(rect.x + 0.5, rect.y + 0.5, rect.width - 1, rect.height - 1, 4)
                gc.SetFont(self.GetFont(), Colors.TEXT_SECONDARY if idx != self._hover_index else Colors.TEXT_PRIMARY)
                _tw, th = gc.GetTextExtent(label)[:2]
                gc.DrawText(label, rect.x + 9, rect.y + (rect.height - th) / 2)

    def _hit_test(self, pos: wx.Point) -> int:
        for idx, rect in enumerate(self._rects):
            if rect.Contains(pos):
                return idx
        return -1

    def _on_motion(self, event):
        index = self._hit_test(event.GetPosition())
        if index != self._hover_index:
            self._hover_index = index
            self.Refresh()

    def _on_leave(self, _event):
        if self._hover_index != -1:
            self._hover_index = -1
            self.Refresh()

    def _on_left_down(self, event):
        index = self._hit_test(event.GetPosition())
        if index < 0 or index >= len(self._items):
            return
        rect = self._rects[index]
        _label, menu = self._items[index]
        self.PopupMenu(menu, rect.x, rect.y + rect.height + 1)


class MainWindow(wx.Frame):
    """Honeycam 스타일 GIF 에디터 메인 윈도우 (wxPython)"""

    def __init__(self):
        super().__init__(None, title="XGif Editor", size=(1680, 1120))
        apply_dark_title_bar(self)
        if Colors:
            self.SetBackgroundColour(Colors.BG_PRIMARY)

        # 로거 초기화
        self._logger = get_logger()

        # 윈도우 아이콘 설정
        from core.utils import get_resource_path
        icon_path = get_resource_path(os.path.join('resources', 'xgif_icon.ico'))
        if not os.path.exists(icon_path):
            icon_path = get_resource_path(os.path.join('resources', 'Xgif_icon.png'))
        if os.path.exists(icon_path):
            icon = wx.Icon(icon_path, wx.BITMAP_TYPE_ICO if icon_path.endswith('.ico') else wx.BITMAP_TYPE_PNG)
            self.SetIcon(icon)

        # 데이터
        self._frames = FrameCollection()
        self._undo_manager = UndoManager(max_history=20, max_memory_mb=200)
        self._current_file_path: Optional[str] = None
        self._is_modified = False

        # 설정 (wxPython의 wx.Config 사용)
        self._settings = wx.Config("XGifEditor")
        self._last_directory = self._settings.Read("last_directory", "")

        # 최근 파일 목록
        self._max_recent_files = 10
        recent_files_str = self._settings.Read("recent_files", "")
        if recent_files_str:
            self._recent_files = recent_files_str.split('|') if '|' in recent_files_str else [recent_files_str]
        else:
            self._recent_files = []

        # 성능 모드 감지 및 설정
        self._is_low_end_mode = self._detect_low_end_mode()
        self._preview_delay = 300 if self._is_low_end_mode else 100

        # 메모리 관리
        self._memory_manager = get_memory_manager()
        self._memory_limit_expanded = False
        # 인덱스 컬러 변환 제안 다이얼로그를 한 파일 당 1회만 표시. open_file 에서 리셋.
        self._index_color_offer_done = False

        # 언어 설정
        self._is_korean = True
        self._translations = Translations(self._is_korean)

        # 재생 타이머
        self._play_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_play_timer, self._play_timer)
        self._is_playing = False
        self._updating_slider = False  # 슬라이더 프로그래밍 업데이트 중 플래그

        # UI 초기화
        self._setup_ui()
        self._setup_menu()
        self._setup_shortcuts()

        # 인라인 툴바: 시작 시 일괄 초기화 (창 표시 후 버튼 지연 표시 방지)
        self._inline_toolbars_initialized = False
        self._deferred_init_inline_toolbars()

        self._update_title()
        self._update_info_bar()

        # GPU 상태 주기적 업데이트
        self._gpu_update_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._update_gpu_status, self._gpu_update_timer)
        self._gpu_update_timer.Start(5000)

        # CuPy 설치 제안 (2초 후 한 번만)
        wx.CallLater(2000, self._check_cupy_install_offer)

        # 윈도우 이벤트
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_SHOW, self.OnShow)
        self.Bind(wx.EVT_CLOSE, self.closeEvent)
        self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyDown)  # 키보드 이벤트

        # 드래그 & 드롭 지원
        self.SetDropTarget(FileDropTarget(self))

    def _deferred_init_inline_toolbars(self):
        """창 표시 후 인라인 툴바 지연 초기화"""
        if self._inline_toolbars_initialized:
            return
        self._init_inline_toolbars()
        self._inline_toolbars_initialized = True

    def _init_inline_toolbars(self):
        """인라인 툴바 초기화 — PropertyBar에 등록"""
        pb = self._property_bar

        self._speed_toolbar = SpeedToolbar(self, parent=pb)
        pb.register_toolbar('speed', self._speed_toolbar)

        self._resize_toolbar = ResizeToolbar(self, parent=pb)
        pb.register_toolbar('resize', self._resize_toolbar)

        self._effects_toolbar = EffectsToolbar(self, parent=pb)
        pb.register_toolbar('effects', self._effects_toolbar)

        self._text_toolbar = TextToolbar(self, parent=pb)
        pb.register_toolbar('text', self._text_toolbar)

        self._rotate_toolbar = RotateToolbar(self, parent=pb)
        pb.register_toolbar('rotate', self._rotate_toolbar)

        self._sticker_toolbar = StickerToolbar(self, parent=pb)
        pb.register_toolbar('sticker', self._sticker_toolbar)

        self._crop_toolbar = CropToolbar(self, parent=pb)
        pb.register_toolbar('crop', self._crop_toolbar)

        self._mosaic_toolbar = MosaicToolbar(self, parent=pb)
        pb.register_toolbar('mosaic', self._mosaic_toolbar)

        self._speech_bubble_toolbar = SpeechBubbleToolbar(self, parent=pb)
        pb.register_toolbar('speech_bubble', self._speech_bubble_toolbar)

        self._watermark_toolbar = WatermarkToolbar(self, parent=pb)
        pb.register_toolbar('watermark', self._watermark_toolbar)

        self._reduce_toolbar = ReduceToolbar(self, parent=pb)
        pb.register_toolbar('reduce', self._reduce_toolbar)

        self._pencil_toolbar = PencilToolbar(self, parent=pb)
        pb.register_toolbar('pencil', self._pencil_toolbar)

        self._active_inline_toolbar = None

        # 인라인 툴바 이벤트 바인딩
        self._bind_toolbar_events()

    def _bind_toolbar_events(self):
        """인라인 툴바 이벤트 연결"""
        from ..utils.wx_events import EVT_TOOLBAR_APPLIED, EVT_TOOLBAR_CANCELLED

        toolbars = [
            self._speed_toolbar,
            self._resize_toolbar,
            self._effects_toolbar,
            self._text_toolbar,
            self._rotate_toolbar,
            self._sticker_toolbar,
            self._crop_toolbar,
            self._mosaic_toolbar,
            self._speech_bubble_toolbar,
            self._watermark_toolbar,
            self._reduce_toolbar,
            self._pencil_toolbar,
        ]

        for toolbar in toolbars:
            toolbar.Bind(EVT_TOOLBAR_APPLIED, self._on_toolbar_applied)
            toolbar.Bind(EVT_TOOLBAR_CANCELLED, self._on_toolbar_cancelled)

    def _on_toolbar_applied(self, event):
        """인라인 툴바 적용 이벤트"""
        self._hide_active_inline_toolbar()
        self._is_modified = True
        self._update_title()
        self._update_info_bar()
        self._refresh_all()

    def _on_toolbar_cancelled(self, event):
        """인라인 툴바 취소 이벤트"""
        self._hide_active_inline_toolbar()
        self._refresh_all()

    def _setup_ui(self):
        """UI 초기화"""
        self.Freeze()
        self.SetTitle("GIF Editor")
        # 상호작용이 가능한 최소 크기(작업 영역 플로어). 이 아래로는
        # 툴바/프레임목록/캔버스가 사용 불가하므로 정당한 최소값.
        self.SetMinSize((880, 620))
        # 초기 크기는 선호 크기를 화면 작업영역에 클램프
        # (ui.theme.ThemedDialog.fit_to_content 와 동일 패턴).
        preferred_w, preferred_h = 1008, 840
        display_idx = wx.Display.GetFromWindow(self)
        display = wx.Display(display_idx if display_idx >= 0 else 0)
        screen = display.GetClientArea()
        # 화면 작업영역으로 클램프하되 상호작용 최소(880x620) 아래로는 내려가지 않음
        init_w = max(880, min(preferred_w, screen.width - 40))
        init_h = max(620, min(preferred_h, screen.height - 40))
        self.SetSize(init_w, init_h)

        # 중앙 패널
        central_panel = wx.Panel(self)
        central_panel.SetBackgroundColour(Colors.BG_PRIMARY)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(central_panel, 1, wx.EXPAND)
        self.SetSizer(frame_sizer)

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # === 앱 메뉴 스트립 (네이티브 흰 MenuBar 대신 다크 owner-draw) ===
        self._flat_menu_bar = FlatEditorMenuBar(self, central_panel)
        main_sizer.Add(self._flat_menu_bar, 0, wx.EXPAND)

        # === 아이콘 툴바 ===
        self._icon_toolbar = IconToolbar(self, central_panel)
        self._connect_icon_toolbar()
        main_sizer.Add(self._icon_toolbar, 0, wx.EXPAND)

        # === 상단 정보 바 ===
        self._info_bar = wx.Panel(central_panel)
        self._info_bar.SetBackgroundColour(Colors.RAIL_BG)
        info_sizer = wx.BoxSizer(wx.HORIZONTAL)

        app_name_label = wx.StaticText(self._info_bar, label="XGif")
        app_name_label.SetFont(Fonts.get_font(Fonts.SIZE_MD, bold=True))
        app_name_label.SetForegroundColour(Colors.TEXT_PRIMARY)
        info_sizer.Add(app_name_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        version_label = wx.StaticText(self._info_bar, label=f"v{__version__}")
        version_label.SetFont(Fonts.get_font(Fonts.SIZE_SM, bold=True))
        version_label.SetForegroundColour(Colors.VERSION_ACCENT)
        info_sizer.Add(version_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        date_label = wx.StaticText(self._info_bar, label=f"({__last_modified__})")
        date_label.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
        date_label.SetForegroundColour(Colors.TEXT_MUTED)
        info_sizer.Add(date_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        sep_app = wx.StaticLine(self._info_bar, style=wx.LI_VERTICAL, size=(1, 16))
        sep_app.SetBackgroundColour(Colors.DIVIDER_SUBTLE)
        info_sizer.Add(sep_app, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        # 줌 레벨
        self._zoom_label = wx.StaticText(self._info_bar, label="1x")
        self._zoom_label.SetFont(Fonts.get_font(Fonts.SIZE_SM, bold=True))
        self._zoom_label.SetForegroundColour(Colors.VERSION_ACCENT)
        self._zoom_label.SetMinSize((30, -1))
        info_sizer.Add(self._zoom_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        info_sizer.AddStretchSpacer()

        # 영상 크기
        self._size_info = wx.StaticText(self._info_bar, label=self._translations.tr("info_size_empty"))
        self._size_info.SetMinSize((100, -1))
        self._size_info.SetForegroundColour(Colors.TEXT_SECONDARY)
        self._size_info.SetToolTip(self._translations.tr("info_size_tooltip"))
        info_sizer.Add(self._size_info, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        sep1 = wx.StaticLine(self._info_bar, style=wx.LI_VERTICAL, size=(1, 16))
        sep1.SetBackgroundColour(Colors.DIVIDER_SUBTLE)
        info_sizer.Add(sep1, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        # 프레임 수
        self._frame_count_info = wx.StaticText(self._info_bar, label=self._translations.tr("info_frame_count_empty"))
        self._frame_count_info.SetMinSize((80, -1))
        self._frame_count_info.SetForegroundColour(Colors.TEXT_SECONDARY)
        self._frame_count_info.SetToolTip(self._translations.tr("info_frame_count_tooltip"))
        info_sizer.Add(self._frame_count_info, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        sep2 = wx.StaticLine(self._info_bar, style=wx.LI_VERTICAL, size=(1, 16))
        sep2.SetBackgroundColour(Colors.DIVIDER_SUBTLE)
        info_sizer.Add(sep2, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        # 재생 시간
        self._duration_info = wx.StaticText(self._info_bar, label=self._translations.tr("info_duration_empty"))
        self._duration_info.SetMinSize((100, -1))
        self._duration_info.SetForegroundColour(Colors.TEXT_SECONDARY)
        self._duration_info.SetToolTip(self._translations.tr("info_duration_tooltip"))
        info_sizer.Add(self._duration_info, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        sep3 = wx.StaticLine(self._info_bar, style=wx.LI_VERTICAL, size=(1, 16))
        sep3.SetBackgroundColour(Colors.DIVIDER_SUBTLE)
        info_sizer.Add(sep3, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        # 메모리 사용량
        self._memory_info = wx.StaticText(self._info_bar, label=self._translations.tr("info_memory_label"))
        self._memory_info.SetForegroundColour(Colors.TEXT_SECONDARY)
        if not self._is_low_end_mode:
            self._memory_info.Hide()
        info_sizer.Add(self._memory_info, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self._memory_value = wx.StaticText(self._info_bar, label="0MB")
        self._memory_value.SetBackgroundColour(Colors.BG_INPUT_DARK)
        self._memory_value.SetForegroundColour(Colors.TEXT_SECONDARY)
        self._memory_value.SetMinSize((60, -1))
        self._memory_value.SetToolTip(self._translations.tr("info_memory_tooltip"))
        info_sizer.Add(self._memory_value, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        sep4 = wx.StaticLine(self._info_bar, style=wx.LI_VERTICAL, size=(1, 16))
        sep4.SetBackgroundColour(Colors.DIVIDER_SUBTLE)
        info_sizer.Add(sep4, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        # GPU 상태
        self._gpu_label = wx.StaticText(self._info_bar, label="GPU")
        self._gpu_label.SetMinSize((40, -1))
        self._gpu_label.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self._gpu_label.Bind(wx.EVT_LEFT_DOWN, lambda e: self._show_gpu_info())
        self._update_gpu_status()
        info_sizer.Add(self._gpu_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        # 구분선
        sep_lang = wx.StaticLine(self._info_bar, style=wx.LI_VERTICAL, size=(1, 16))
        sep_lang.SetBackgroundColour(Colors.DIVIDER_SUBTLE)
        info_sizer.Add(sep_lang, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        # 언어 토글 버튼 (info_bar 우측)
        initial_lang_text = "En" if self._is_korean else "한"
        self._lang_toggle_btn = wx.Button(self._info_bar, label=initial_lang_text, size=(30, 20))
        self._lang_toggle_btn.SetToolTip(self._translations.tr("lang_toggle_tooltip"))
        self._lang_toggle_btn.SetForegroundColour(Colors.LANG_TOGGLE_FG)
        self._lang_toggle_btn.SetBackgroundColour(Colors.LANG_TOGGLE_BG)
        self._lang_toggle_btn.SetFont(Fonts.get_font(Fonts.SIZE_SMALL, bold=True))
        self._lang_toggle_btn.Bind(wx.EVT_BUTTON, lambda e: self._toggle_language())
        info_sizer.Add(self._lang_toggle_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self._info_bar.SetSizer(info_sizer)
        main_sizer.Add(self._info_bar, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # === 메인 콘텐츠 영역 ===
        content_splitter = wx.SplitterWindow(central_panel, style=wx.SP_LIVE_UPDATE | wx.SP_NOBORDER)
        content_splitter.SetBackgroundColour(Colors.BG_PRIMARY)
        with contextlib.suppress(Exception):
            content_splitter.SetSashInvisible(True)

        # 좌측: 프레임 목록
        self._frame_list = FrameListWidget(self, content_splitter)
        self._frame_list.SetMinSize((92, -1))
        self._frame_list.SetMaxSize((180, -1))

        from ..utils.wx_events import EVT_FRAME_SELECTED, EVT_FRAME_DELAY_CHANGED, EVT_FRAME_DELETED
        self._frame_list.Bind(EVT_FRAME_SELECTED, self._on_frame_selected)
        self._frame_list.Bind(EVT_FRAME_DELAY_CHANGED, self._on_delay_changed)
        self._frame_list.Bind(EVT_FRAME_DELETED, self._on_frames_deleted)

        # 우측: 작업 공간
        self._workspace = wx.Panel(content_splitter)
        self._workspace.SetBackgroundColour(Colors.BG_PRIMARY)
        workspace_sizer = wx.BoxSizer(wx.VERTICAL)

        # PropertyBar (도구 속성 바 — 도구 미선택 시 숨김)
        self._property_bar = PropertyBar(self._workspace)
        workspace_sizer.Add(self._property_bar, 0, wx.EXPAND)

        # 캔버스
        self._canvas = CanvasWidget(self, self._workspace)
        workspace_sizer.Add(self._canvas, 1, wx.EXPAND)

        # 하단 컨트롤 (슬라이더 + 공유 액션 버튼)
        self._bottom_controls = wx.Panel(self._workspace)
        self._bottom_controls.SetBackgroundColour(Colors.RAIL_BG)
        controls_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._play_btn = FlatIconButton(
            "play", self._translations.tr("btn_play_tooltip"), self._bottom_controls, size=(38, 38)
        )
        self._play_btn.Bind(wx.EVT_BUTTON, lambda e: self.toggle_play())
        controls_sizer.Add(self._play_btn, 0, wx.ALL, 5)

        self._frame_slider = wx.Slider(self._bottom_controls, style=wx.SL_HORIZONTAL)
        self._frame_slider.SetBackgroundColour(Colors.RAIL_BG)
        self._frame_slider.SetMin(0)
        self._frame_slider.SetValue(0)
        self._frame_slider.Bind(wx.EVT_SLIDER, lambda e: self._on_slider_changed(e.GetInt()))
        controls_sizer.Add(self._frame_slider, 1, wx.ALL | wx.EXPAND, 5)

        self._frame_indicator = wx.StaticText(self._bottom_controls, label="0/0")
        self._frame_indicator.SetMinSize((60, -1))
        self._frame_indicator.SetForegroundColour(Colors.TEXT_SECONDARY)
        self._frame_indicator.SetFont(Fonts.get_font(Fonts.SIZE_SM, bold=True))
        controls_sizer.Add(self._frame_indicator, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        # 공유 액션 버튼 (도구 활성 시만 표시)
        translations = self._translations

        # TODO: 잔여 if-translations-else 폴백 6곳 — translations는 항상 non-None이므로 후속 정리 대상 (A11 리뷰 M4)
        self._action_clear_btn = self._create_action_button(
            translations.tr("toolbar_clear") if translations else "초기화",
            self._on_action_clear,
        )
        controls_sizer.Add(self._action_clear_btn, 0, wx.ALL, 5)

        self._action_apply_btn = self._create_action_button(
            translations.tr("toolbar_apply") if translations else "적용",
            self._on_action_apply,
            primary=True,
        )
        controls_sizer.Add(self._action_apply_btn, 0, wx.ALL, 5)

        self._action_cancel_btn = self._create_action_button(
            translations.tr("toolbar_cancel") if translations else "취소",
            self._on_action_cancel,
        )
        controls_sizer.Add(self._action_cancel_btn, 0, wx.ALL, 5)

        self._bottom_controls.SetSizer(controls_sizer)
        workspace_sizer.Add(self._bottom_controls, 0, wx.EXPAND)

        self._workspace.SetSizer(workspace_sizer)

        # 스플리터 설정
        content_splitter.SplitVertically(self._frame_list, self._workspace, 168)
        content_splitter.SetMinimumPaneSize(96)
        content_splitter.SetSashGravity(0.0)
        main_sizer.Add(content_splitter, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        # === 하단 버튼 영역 ===
        bottom_bar = wx.Panel(central_panel)
        bottom_bar.SetBackgroundColour(Colors.BG_PRIMARY)
        bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)

        close_text = translations.tr("btn_close_edit") if translations else "편집 종료"
        self._close_btn = wx.Button(bottom_bar, label=close_text)
        self._close_btn.SetBackgroundColour(Colors.BG_INPUT_DARK)
        self._close_btn.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._close_btn.SetToolTip(translations.tr("btn_close_edit_tooltip") if translations else "에디터를 닫습니다")
        self._close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        bottom_sizer.Add(self._close_btn, 0, wx.ALL, 10)

        bottom_sizer.AddStretchSpacer()

        save_text = translations.tr("btn_save") if translations else "저장"
        self._save_btn = wx.Button(bottom_bar, label=save_text)
        self._save_btn.SetBackgroundColour(Colors.ACCENT)
        self._save_btn.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._save_btn.SetToolTip(translations.tr("btn_save_tooltip"))
        self._save_btn.Bind(wx.EVT_BUTTON, lambda e: self.save_file_as())
        bottom_sizer.Add(self._save_btn, 0, wx.ALL, 10)

        bottom_bar.SetSizer(bottom_sizer)
        main_sizer.Add(bottom_bar, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        central_panel.SetSizer(main_sizer)
        central_panel.Layout()
        self.Layout()
        self.Thaw()

    def _setup_menu(self):
        """플랫 메뉴바 설정 (wx.MenuBar 대신 커스텀 FlatMenuBar 사용)"""
        translations = self._translations

        # === wx.Menu 객체 생성 (팝업으로 사용) ===

        # 파일 메뉴
        self._file_menu = wx.Menu()
        self._action_new = self._file_menu.Append(wx.ID_NEW, translations.tr("action_new") + "\tCtrl+N")
        self._file_menu.Bind(wx.EVT_MENU, lambda e: self.new_project(), self._action_new)
        self._action_open = self._file_menu.Append(wx.ID_OPEN, translations.tr("action_open") + "\tCtrl+O")
        self._file_menu.Bind(wx.EVT_MENU, lambda e: self.open_file(), self._action_open)
        self._action_open_sequence = self._file_menu.Append(wx.ID_ANY, translations.tr("action_open_sequence"))
        self._file_menu.Bind(wx.EVT_MENU, lambda e: self.open_image_sequence(), self._action_open_sequence)
        self._recent_menu = wx.Menu()
        self._file_menu.AppendSubMenu(self._recent_menu, translations.tr("menu_recent_files"))
        self._update_recent_files_menu()
        action_clear_recent = self._file_menu.Append(wx.ID_ANY, translations.tr("action_clear_recent"))
        self._file_menu.Bind(wx.EVT_MENU, lambda e: self._clear_recent_files(), action_clear_recent)
        self._file_menu.AppendSeparator()
        self._action_save = self._file_menu.Append(wx.ID_SAVE, translations.tr("action_save") + "\tCtrl+S")
        self._file_menu.Bind(wx.EVT_MENU, lambda e: self.save_file(), self._action_save)
        self._action_save_as = self._file_menu.Append(
            wx.ID_SAVEAS, translations.tr("action_save_as") + "\tCtrl+Shift+S")
        self._file_menu.Bind(wx.EVT_MENU, lambda e: self.save_file_as(), self._action_save_as)
        self._file_menu.AppendSeparator()
        action_exit = self._file_menu.Append(wx.ID_EXIT, translations.tr("action_exit") + "\tCtrl+Q")
        self._file_menu.Bind(wx.EVT_MENU, lambda e: self.Close(), action_exit)

        # 편집 메뉴
        self._edit_menu = wx.Menu()
        action_select_all = self._edit_menu.Append(wx.ID_SELECTALL, translations.tr("action_select_all") + "\tCtrl+A")
        self._edit_menu.Bind(wx.EVT_MENU, lambda e: self._select_all(), action_select_all)
        self._edit_menu.AppendSeparator()
        action_delete = self._edit_menu.Append(wx.ID_DELETE, translations.tr("action_delete") + "\tDel")
        self._edit_menu.Bind(wx.EVT_MENU, lambda e: self._delete_frame(), action_delete)
        action_duplicate = self._edit_menu.Append(wx.ID_ANY, translations.tr("action_duplicate") + "\tCtrl+D")
        self._edit_menu.Bind(wx.EVT_MENU, lambda e: self._duplicate_frame(), action_duplicate)

        # 관리 메뉴
        self._manage_menu = wx.Menu()
        action_remove_dup = self._manage_menu.Append(wx.ID_ANY, translations.tr("action_remove_dup"))
        self._manage_menu.Bind(wx.EVT_MENU, lambda e: self._remove_duplicates(), action_remove_dup)
        self._manage_menu.AppendSeparator()
        action_mosaic = self._manage_menu.Append(wx.ID_ANY, translations.tr("action_mosaic"))
        self._manage_menu.Bind(wx.EVT_MENU, lambda e: self._show_mosaic_toolbar(), action_mosaic)
        action_speech_bubble = self._manage_menu.Append(wx.ID_ANY, translations.tr("action_speech_bubble"))
        self._manage_menu.Bind(wx.EVT_MENU, lambda e: self._show_speech_bubble_toolbar(), action_speech_bubble)
        action_watermark = self._manage_menu.Append(wx.ID_ANY, translations.tr("action_watermark"))
        self._manage_menu.Bind(wx.EVT_MENU, lambda e: self._show_watermark_toolbar(), action_watermark)
        self._manage_menu.AppendSeparator()
        action_split_gif = self._manage_menu.Append(wx.ID_ANY, translations.tr("action_split_gif"))
        self._manage_menu.Bind(wx.EVT_MENU, lambda e: self._split_gif(), action_split_gif)
        action_merge_gif = self._manage_menu.Append(wx.ID_ANY, translations.tr("action_merge_gif"))
        self._manage_menu.Bind(wx.EVT_MENU, lambda e: self._merge_gif(), action_merge_gif)
        action_insert_gif = self._manage_menu.Append(wx.ID_ANY, translations.tr("action_insert_gif"))
        self._manage_menu.Bind(wx.EVT_MENU, lambda e: self._insert_gif(), action_insert_gif)

        # 보기 메뉴
        self._view_menu = wx.Menu()
        self._view_menu.Append(wx.ID_ANY, translations.tr("action_view_actual_size"))
        self._view_menu.Append(wx.ID_ANY, translations.tr("action_view_fit_screen"))

        # 설정 메뉴 (GPU 체크는 지연 초기화 — UI 먼저 표시)
        self._settings_menu = wx.Menu()
        self._action_gpu = self._settings_menu.AppendCheckItem(wx.ID_ANY, translations.tr("action_gpu"))
        self._action_gpu.Check(False)
        self._action_gpu.Enable(False)
        self._settings_menu.Bind(wx.EVT_MENU, lambda e: self._toggle_gpu(e.IsChecked()), self._action_gpu)
        action_gpu_info = self._settings_menu.Append(wx.ID_ANY, translations.tr("action_gpu_info"))
        self._settings_menu.Bind(wx.EVT_MENU, lambda e: self._show_gpu_info(), action_gpu_info)
        # GPU 메뉴 상태를 비동기로 업데이트
        wx.CallLater(500, self._init_gpu_menu_state)

        # 도움말 메뉴
        self._help_menu = wx.Menu()
        action_help = self._help_menu.Append(wx.ID_HELP, translations.tr("action_help"))
        self._help_menu.Bind(wx.EVT_MENU, lambda e: self._show_help_dialog(), action_help)
        self._help_menu.AppendSeparator()
        action_about = self._help_menu.Append(wx.ID_ABOUT, translations.tr("action_about", v=__version__))
        self._help_menu.Bind(wx.EVT_MENU, lambda e: self._show_about_dialog(), action_about)

        # === 다크 owner-drawn 메뉴 스트립 ===
        self._flat_menu_bar.set_items([
            (translations.tr("menu_file"), self._file_menu),
            (translations.tr("menu_edit"), self._edit_menu),
            (translations.tr("menu_manage"), self._manage_menu),
            (translations.tr("menu_view"), self._view_menu),
            (translations.tr("menu_settings"), self._settings_menu),
            (translations.tr("menu_help"), self._help_menu),
        ])

    def _setup_shortcuts(self):
        """키보드 단축키 설정"""
        # wxPython은 accelerator table 또는 메뉴 항목에서 단축키 처리
        pass

    def _connect_icon_toolbar(self):
        """아이콘 툴바 이벤트 연결"""
        # 각 툴바 버튼이 직접 main_window 메서드를 호출하도록 설정됨
        pass

    # ==================== 프로퍼티 ====================

    @property
    def frames(self) -> FrameCollection:
        return self._frames

    @property
    def undo_manager(self) -> UndoManager:
        return self._undo_manager

    @property
    def is_modified(self) -> bool:
        return self._is_modified

    @is_modified.setter
    def is_modified(self, value: bool) -> None:
        if self._is_modified != value:
            self._is_modified = value
            self._update_title()

    # ==================== 파일 조작 ====================

    def new_project(self) -> None:
        """새 프로젝트"""
        if not self._confirm_save():
            return

        self._frames.clear()
        self._current_file_path = None
        self._is_modified = False
        self._update_title()
        self._update_info_bar()
        self._refresh_all()

    def open_file(self, file_path: str = None):
        """파일 열기 (GIF, 비디오 지원)"""
        if not self._confirm_save():
            return

        if file_path is None:
            dlg = wx.FileDialog(
                self,
                self._translations.tr("dlg_open_file_title"),
                self._last_directory,
                "",
                self._translations.tr("dlg_open_filter"),
                wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
            )
            if dlg.ShowModal() == wx.ID_OK:
                file_path = dlg.GetPath()
                self._last_directory = os.path.dirname(file_path)
                self._settings.Write("last_directory", self._last_directory)
            else:
                dlg.Destroy()
                return
            dlg.Destroy()

        if not file_path or not os.path.exists(file_path):
            return

        # 파일 확장자 확인
        ext = os.path.splitext(file_path)[1].lower()

        # 비디오 파일인 경우 비디오 로더 사용
        if ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv']:
            self._open_video_file(file_path)
            return

        # GIF 디코드는 큰 파일 (수천 프레임) 에서 수 초가 걸리므로 비동기 워커 +
        # ProgressDialog 패턴으로 처리. 비디오 로드와 동일한 VideoLoadWorker 사용
        # (이름은 비디오용이나 실제론 generic — load_func 와 progress_callback 만 사용).
        self._open_gif_async(file_path)

    def _open_gif_async(self, file_path: str) -> None:
        """GIF 파일을 백그라운드 워커로 로드하면서 ProgressDialog 를 표시."""
        # 진행률 다이얼로그 (취소 가능)
        self._gif_progress = wx.ProgressDialog(
            self._translations.tr("prog_gif_load_title"),
            self._translations.tr("prog_gif_load_msg"),
            maximum=100,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT,
        )
        self._gif_file_path = file_path

        # 비동기 워커 — VideoLoadWorker 는 generic 한 progress_callback 주입 래퍼.
        worker = VideoLoadWorker(GifDecoder.load, file_path)
        worker.signals.connect('progress', self._on_gif_load_progress)
        worker.signals.connect('finished', self._on_gif_load_finished)
        worker.signals.connect('error', self._on_gif_load_error)
        worker.signals.connect('cancelled', self._on_gif_load_cancelled)
        self._gif_worker = worker
        get_worker_manager().start(worker)

    def _on_gif_load_progress(self, current: int, total: int) -> None:
        """GIF 디코드 진행률 갱신. PD_CAN_ABORT 의 Cancel 버튼은 다이얼로그의 반환값
        으로 확인하므로 여기서 워커 취소 여부도 함께 점검."""
        try:
            if not (hasattr(self, '_gif_progress') and self._gif_progress):
                return
            percent = int((current / total) * 100) if total > 0 else 0
            cont, _ = self._gif_progress.Update(
                percent,
                self._translations.tr(
                    "prog_gif_load_msg_detail", current=current, total=total,
                ),
            )
            if not cont and hasattr(self, '_gif_worker') and self._gif_worker:
                self._gif_worker.cancel()
        except (RuntimeError, wx.PyDeadObjectError):
            pass

    def _on_gif_load_finished(self, result) -> None:
        """GIF 로드 완료 — 컬렉션 세팅 + UI 갱신 + 인덱스 컬러 제안."""
        if hasattr(self, '_gif_progress') and self._gif_progress:
            with contextlib.suppress(Exception):
                self._gif_progress.Destroy()
            self._gif_progress = None

        if not result.success:
            wx.MessageBox(
                self._translations.tr("msg_open_failed_body", e=result.error_message),
                self._translations.tr("msg_error"),
                wx.OK | wx.ICON_ERROR,
            )
            return

        file_path = getattr(self, '_gif_file_path', None)

        if result.frames:
            self._frames = result.frames
            # undo 스택 초기화 — 이전 FrameCollection 에 대한 클로저 참조 무효화 방지
            if hasattr(self, '_undo_manager') and self._undo_manager:
                self._undo_manager.clear()

        if file_path:
            self._current_file_path = file_path
            self._add_recent_file(file_path)

        self._is_modified = False
        # 새 파일이므로 인덱스 컬러 제안 플래그 리셋
        self._index_color_offer_done = False

        self._update_title()
        self._update_info_bar()
        self._refresh_all()
        # 큰 RGBA/RGB GIF 디코드 결과면 인덱스 컬러 변환 제안.
        wx.CallAfter(self._offer_index_color_optimization)

    def _on_gif_load_error(self, error_msg: str, traceback_str: str) -> None:
        """GIF 로드 에러 — 진행 다이얼로그 닫고 사용자에게 보고."""
        if hasattr(self, '_gif_progress') and self._gif_progress:
            with contextlib.suppress(Exception):
                self._gif_progress.Destroy()
            self._gif_progress = None
        wx.MessageBox(
            self._translations.tr("msg_open_failed_body", e=error_msg),
            self._translations.tr("msg_error"),
            wx.OK | wx.ICON_ERROR,
        )

    def _on_gif_load_cancelled(self) -> None:
        """GIF 로드 취소 — 다이얼로그 닫기만."""
        if hasattr(self, '_gif_progress') and self._gif_progress:
            with contextlib.suppress(Exception):
                self._gif_progress.Destroy()
            self._gif_progress = None

    def save_file(self):
        """저장"""
        self._stop_preview_before_save()
        if self._current_file_path:
            self._save_to_path(self._current_file_path)
        else:
            self.save_file_as()

    def save_file_as(self):
        """다른 이름으로 저장 (고급 설정 다이얼로그)"""
        self._stop_preview_before_save()
        dlg = SaveDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            file_path = dlg.get_file_path()
            settings = dlg.get_settings()

            if file_path:
                self._save_to_path_with_settings(file_path, settings)
                self._last_directory = os.path.dirname(file_path)
                self._settings.Write("last_directory", self._last_directory)

        dlg.Destroy()

    def _stop_preview_before_save(self):
        if self._is_playing:
            self.pause()

    def _save_to_path_with_settings(self, file_path: str, settings: EncoderSettings, close_after_save: bool = False):
        """지정된 경로에 설정과 함께 저장 (비동기 처리)"""
        # 진행률 다이얼로그
        self._save_progress = wx.ProgressDialog(
            self._translations.tr("prog_saving_title"),
            self._translations.tr("prog_saving_msg"),
            maximum=100,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
        )

        self._save_file_path = file_path
        self._save_close_after = close_after_save

        # 비동기 워커 생성
        def save_task():
            return GifEncoder.save(self._frames, file_path, settings)

        worker = FunctionWorker(save_task)
        worker.signals.connect('finished', self._on_save_finished)
        worker.signals.connect('error', self._on_save_error)

        self._save_worker = worker

        # 워커 시작
        get_worker_manager().start(worker)

    def _save_to_path(self, file_path: str, close_after_save: bool = False):
        """지정된 경로에 저장 (기본 설정, 비동기 처리)"""
        settings = EncoderSettings()
        self._save_to_path_with_settings(file_path, settings, close_after_save)

    def _on_save_finished(self, result):
        """저장 완료 콜백 (워커 스레드에서 호출 — wx.CallAfter 필수)"""
        wx.CallAfter(self._on_save_finished_ui, result)

    def _on_save_finished_ui(self, result):
        """저장 완료 UI 업데이트 (메인 스레드)"""
        if hasattr(self, '_save_progress') and self._save_progress:
            self._save_progress.Destroy()
            self._save_progress = None

        if not result.success:
            wx.MessageBox(
                self._translations.tr("msg_save_failed_body", e=result.error_message),
                self._translations.tr("msg_error"),
                wx.OK | wx.ICON_ERROR
            )
            return

        file_path = getattr(self, '_save_file_path', None)
        close_after_save = getattr(self, '_save_close_after', False)

        if not file_path:
            return

        self._current_file_path = file_path
        self._is_modified = False
        self._update_title()
        self._update_info_bar()

        wx.MessageBox(
            self._translations.tr("msg_saved_body", kb=result.file_size / 1024),
            self._translations.tr("msg_save_complete"),
            wx.OK | wx.ICON_INFORMATION
        )

        # 저장된 파일 위치 열기
        self._open_file_location(file_path)

        # 저장 후 앱 종료
        if close_after_save:
            self.Close()

    def _on_save_error(self, error_msg: str, traceback: str):
        """저장 에러 콜백 (워커 스레드에서 호출 — wx.CallAfter 필수)"""
        wx.CallAfter(self._on_save_error_ui, error_msg, traceback)

    def _on_save_error_ui(self, error_msg: str, traceback: str):
        """저장 에러 UI 업데이트 (메인 스레드)"""
        if hasattr(self, '_save_progress') and self._save_progress:
            self._save_progress.Destroy()
            self._save_progress = None
        wx.MessageBox(
            self._translations.tr("msg_save_failed_body", e=error_msg),
            self._translations.tr("msg_error"),
            wx.OK | wx.ICON_ERROR
        )

    def _open_file_location(self, file_path: str):
        """파일 탐색기에서 파일 위치 열기"""
        try:
            # 절대 경로로 변환하고 정규화
            abs_path = os.path.abspath(file_path)
            abs_path = os.path.normpath(abs_path)

            if sys.platform == 'win32':
                # Windows: 파일 탐색기에서 해당 파일을 선택한 상태로 열기
                subprocess.Popen(['explorer', '/select,', abs_path])
            elif sys.platform == 'darwin':
                # macOS: Finder에서 해당 파일을 선택한 상태로 열기
                subprocess.Popen(['open', '-R', abs_path])
            else:
                # Linux: 파일의 폴더 열기
                folder = os.path.dirname(abs_path)
                subprocess.Popen(['xdg-open', folder])
        except Exception as e:
            # 오류가 발생해도 무시 (저장은 이미 완료됨)
            self._logger.warning(f"파일 위치 열기 실패: {e}", exc_info=True)

    def _confirm_save(self) -> bool:
        """변경사항 저장 확인"""
        if not self._is_modified:
            return True

        dlg = wx.MessageDialog(
            self,
            self._translations.tr("msg_confirm_save_body"),
            self._translations.tr("msg_confirm"),
            wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION
        )
        result = dlg.ShowModal()
        dlg.Destroy()

        if result == wx.ID_YES:
            self.save_file()
            return True
        return result == wx.ID_NO

    # ==================== UI 업데이트 ====================

    def _update_title(self) -> None:
        """타이틀 업데이트"""
        title = "XGif Editor"
        if self._current_file_path:
            title = f"{os.path.basename(self._current_file_path)} - {title}"
        if self._is_modified:
            title = f"*{title}"
        self.SetTitle(title)

    def _update_info_bar(self):
        """정보 바 업데이트"""
        try:
            if self._frames.is_empty:
                self._size_info.SetLabel(self._translations.tr("info_size_empty"))
                self._frame_count_info.SetLabel(self._translations.tr("info_frame_count_empty"))
                self._duration_info.SetLabel(self._translations.tr("info_duration_empty"))
                if hasattr(self, '_memory_value') and self._memory_value:
                    self._memory_value.SetLabel("0MB")
            else:
                size_str = f"{self._frames.width}x{self._frames.height}"
                self._size_info.SetLabel(self._translations.tr("info_size", size=size_str))
                self._frame_count_info.SetLabel(
                    self._translations.tr("info_frame_count", count=self._frames.frame_count))
                duration = self._frames.total_duration / 1000.0
                self._duration_info.SetLabel(self._translations.tr("info_duration", duration=f"{duration:.1f}"))

                # 메모리 사용량 표시 — mode-aware 정확한 계산 (`w*h*4*N` 추정은 P/RGB
                # 모드 보존 시 최대 4× 과대 추정이므로, FrameCollection.
                # get_memory_usage_mb() 의 mode 별 합산을 사용한다.
                if hasattr(self, '_memory_value') and self._memory_value:
                    memory_mb = self._frames.get_memory_usage_mb()
                    self._memory_value.SetLabel(f"{memory_mb:.1f}MB")

                    # 자동 unload: 큰 GIF (200+ 프레임 & 메모리 800MB+) 에서 비활성
                    # 프레임의 _image (decompressed PIL) 을 해제. _image_bytes (PNG
                    # 압축) 는 유지되어 다음 paint 시 _decompress_image 로 복원된다.
                    # current_index / selected 프레임은 즉시 표시되므로 keep.
                    # (paint 빈도 vs decompress 비용 트레이드오프 — 비활성 프레임에만
                    # 적용하므로 사용자 체감 거의 없음.)
                    if (memory_mb > 800 and self._frames.frame_count > 200):
                        with contextlib.suppress(Exception):
                            self._frames.lazy_load_enabled = True
                            unloaded = self._frames.unload_frames(
                                keep_current=True, keep_selected=True,
                            )
                            if unloaded > 0 and hasattr(self, '_logger') and self._logger:
                                self._logger.debug(
                                    "auto-unload: 비활성 프레임 %d개 해제 "
                                    "(memory=%.1fMB, frame_count=%d)",
                                    unloaded, memory_mb, self._frames.frame_count,
                                )
                            # 캔버스 paint LRU 도 함께 비움 — 큰 GIF 의 zoom 토글
                            # 캐시 (각 ~8MB) 가 누적되면 메모리 압박을 가중시킴.
                            if hasattr(self, '_canvas') and self._canvas and hasattr(
                                self._canvas, 'clear_bitmap_cache'
                            ):
                                self._canvas.clear_bitmap_cache()

                    # 메모리 제한 체크 (1GB 초과 시)
                    if memory_mb > 1024 and not self._memory_limit_expanded:
                        self._check_memory_limit(memory_mb)

                    # 경고 색상 설정
                    if memory_mb > 500:
                        self._memory_value.SetBackgroundColour(Colors.DANGER)
                        self._memory_value.SetForegroundColour(Colors.TEXT_PRIMARY)
                    elif memory_mb > 300:
                        self._memory_value.SetBackgroundColour(Colors.WARNING)
                        self._memory_value.SetForegroundColour(Colors.TEXT_PRIMARY)
                    else:
                        self._memory_value.SetBackgroundColour(Colors.BG_INPUT_DARK)
                        self._memory_value.SetForegroundColour(Colors.TEXT_SECONDARY)
                    self._memory_value.Refresh()

                    # 저사양 모드 라벨 표시/숨기기
                    if hasattr(self, '_memory_info') and self._memory_info and self._is_low_end_mode:
                        self._memory_info.Show()
                        # 라벨은 숨기지 않음 - 값은 항상 표시

                # 프레임 수가 많으면 자동으로 저사양 모드 활성화.
                # 임계 200 → 500 으로 상향: 200~500 프레임은 일반적인 캡처/녹화
                # 범위라 사용자 입장에서 "상대적으로 작은 용량" 임에도 알림이 떴다는
                # 보고가 있었다. 500+ 부터 의미 있는 성능 영향이 시작되므로 그 시점만
                # 알림.
                if self._frames.frame_count > 500 and not self._is_low_end_mode:
                    self._enable_low_end_mode_for_large_gif()

            # GPU 상태 업데이트
            self._update_gpu_status()

            # 정보바 레이아웃 갱신
            self._info_bar.Layout()
            self._info_bar.Refresh()
        except Exception as e:
            self._logger.error(f"정보 바 업데이트 오류: {e}", exc_info=True)

    def _refresh_all(self) -> None:
        """전체 UI 새로고침"""
        if hasattr(self, '_frame_list') and self._frame_list:
            self._frame_list.refresh()  # 프레임 데이터 업데이트
        if hasattr(self, '_canvas') and self._canvas:
            self._canvas.Refresh()  # 캔버스 다시 그리기
        self._update_slider()

    def _update_slider(self) -> None:
        """슬라이더 업데이트 (원본 PyQt6의 blockSignals 패턴 구현)"""
        self._updating_slider = True  # 슬라이더 이벤트 차단
        try:
            if self._frames.is_empty:
                self._frame_slider.SetRange(0, 1)
                self._frame_slider.SetValue(0)
                self._frame_slider.Disable()
                self._frame_indicator.SetLabel("0/0")
            else:
                self._frame_slider.Enable()
                self._frame_slider.SetMax(self._frames.frame_count - 1)
                current_idx = max(0, min(self._frames.current_index, self._frames.frame_count - 1))
                self._frame_slider.SetValue(current_idx)
                self._frame_indicator.SetLabel(f"{current_idx + 1}/{self._frames.frame_count}")
        finally:
            self._updating_slider = False  # 슬라이더 이벤트 재활성화

    def _update_play_button_icon(self, is_playing: bool):
        """재생 버튼 아이콘 업데이트"""
        if hasattr(self, '_play_btn') and hasattr(self._play_btn, 'set_icon_type'):
            self._play_btn.set_icon_type("pause" if is_playing else "play")

    def _update_gpu_status(self, event=None):
        """GPU 상태 업데이트"""
        try:
            gpu_info = gpu_utils.get_gpu_info()
            is_gpu_mode = gpu_utils.is_gpu_enabled()

            if is_gpu_mode and gpu_info.get('available', False):
                self._gpu_label.SetLabel("GPU")
                self._gpu_label.SetForegroundColour(Colors.GPU_ON)
            else:
                self._gpu_label.SetLabel("CPU")
                self._gpu_label.SetForegroundColour(Colors.GPU_OFF)

            # 상세 GPU 정보 툴팁
            status_text = "GPU" if is_gpu_mode else "CPU"
            tooltip_lines = [self._translations.tr("gpu_tooltip_mode", mode=status_text)]
            if is_gpu_mode and gpu_info.get('available', False):
                tooltip_lines.append(self._translations.tr("gpu_tooltip_gpu", name=gpu_info.get('name', 'N/A')))
                tooltip_lines.append(self._translations.tr(
                    "gpu_tooltip_memory", total=f"{gpu_info.get('memory_total', 0):,}"))
                tooltip_lines.append(self._translations.tr(
                    "gpu_tooltip_memory_used", used=f"{gpu_info.get('memory_used', 0):,}"))
                tooltip_lines.append(self._translations.tr(
                    "gpu_tooltip_memory_free", free=f"{gpu_info.get('memory_free', 0):,}"))
                tooltip_lines.append(self._translations.tr(
                    "gpu_tooltip_cuda", version=gpu_info.get('cuda_version', 'N/A')))
                tooltip_lines.append(self._translations.tr(
                    "gpu_tooltip_compute", capability=gpu_info.get('compute_capability', 'N/A')))
            else:
                if gpu_info.get('error'):
                    tooltip_lines.append(self._translations.tr("gpu_tooltip_error", error=gpu_info.get('error')))
                else:
                    tooltip_lines.append(self._translations.tr("gpu_tooltip_unavailable"))
                    tooltip_lines.append(self._translations.tr("gpu_tooltip_requirements"))

            self._gpu_label.SetToolTip("\n".join(tooltip_lines))
        except Exception as e:
            self._logger.error(f"GPU 상태 업데이트 오류: {e}", exc_info=True)

    # ==================== 재생 제어 ====================

    def toggle_play(self):
        """재생/일시정지 토글"""
        if self._is_playing:
            self.pause()
        else:
            self.play()

    def play(self):
        """재생 시작"""
        if self._frames.is_empty:
            return

        self._is_playing = True
        self._update_play_button_icon(True)  # 재생 중 -> 일시정지 아이콘

        # 첫 5 프레임 preload — 자동 unload 후 재생 시작 시점에 decompress 비용
        # ((PNG → PIL) × N) 을 한꺼번에 치러 첫 몇 프레임의 dropped/지연 방지.
        with contextlib.suppress(Exception):
            current = self._frames.current_index
            self._frames.preload_range(current, current + 4)

        frame = self._frames.current_frame
        delay = 100  # 기본값
        if frame and hasattr(frame, 'delay_ms'):
            delay = max(10, frame.delay_ms)  # 최소 10ms
        self._play_timer.Start(delay)

    def pause(self):
        """일시정지"""
        self._is_playing = False
        self._play_timer.Stop()
        self._update_play_button_icon(False)

    def stop(self):
        """정지 (첫 프레임으로 이동)"""
        self.pause()
        if not self._frames.is_empty:
            self._frames.go_to_first()
            self._refresh_all()

    def _on_play_timer(self, event):
        """재생 타이머"""
        if not self._is_playing or self._frames.is_empty:
            return

        if self._frames.frame_count == 0:
            return
        next_idx = (self._frames.current_index + 1) % self._frames.frame_count

        # current_index 직접 변경 (select_frame은 selected_indices만 변경함)
        self._frames.current_index = next_idx

        # 다음 2 프레임 미리 decompress — 재생이 자동 unload 와 만나 dropped frame
        # 을 유발하는 것을 방지. preload_range 는 _ensure_image_loaded 만 트리거
        # 하므로 추가 메모리는 최대 2 프레임 분.
        with contextlib.suppress(Exception):
            self._frames.preload_range(next_idx + 1, next_idx + 2)

        self._update_slider()
        self._canvas.Refresh()

        current = self._frames.current_frame
        if current:
            delay = current.delay_ms
        else:
            delay = 100
        self._play_timer.Start(max(delay, 1), wx.TIMER_ONE_SHOT)

    def _on_slider_changed(self, value: int) -> None:
        """슬라이더 변경 (사용자가 직접 조작한 경우만 처리)"""
        # 프로그래밍 방식의 업데이트는 무시 (원본 PyQt6의 blockSignals 패턴)
        if self._updating_slider:
            return

        if 0 <= value < self._frames.frame_count:
            # 슬라이더를 직접 움직였을 때는 current_index 직접 설정
            self._frames.current_index = value
            # 선택도 업데이트
            self._frames.deselect_all()
            self._frames.select_frame(value, add_to_selection=True)
            # 프레임 리스트 UI 업데이트
            if hasattr(self, '_frame_list') and self._frame_list:
                self._frame_list.refresh()
            # 캔버스 업데이트
            self._canvas.Refresh()
            self._canvas.Update()

    # ==================== 편집 기능 (스텁) ====================

    def _select_all(self):
        """모두 선택"""
        self._frames.select_all()
        if hasattr(self, '_frame_list') and self._frame_list:
            self._frame_list.refresh()

    def _delete_frame(self) -> None:
        """선택된 프레임 삭제"""
        if hasattr(self, '_frame_list') and self._frame_list:
            self._frame_list.delete_selected_frames()

    def _duplicate_frame(self) -> None:
        """선택된 프레임 복제"""
        if self._frames.is_empty:
            return

        if not self._frames._is_valid_index(self._frames.current_index):
            wx.MessageBox(
                self._translations.tr("msg_invalid_frame_index"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
            return

        try:
            # 메모리 사용량 체크 (100MB 이상이면 히스토리 저장 건너뛰기)
            current_memory_mb = self._frames.get_memory_usage_mb()
            if current_memory_mb > 100:
                self._frames.duplicate_frame(self._frames.current_index)
                self._refresh_all()
                self._is_modified = True
                wx.MessageBox(
                    self._translations.tr("msg_dup_no_undo", mb=current_memory_mb),
                    self._translations.tr("common_notice"),
                    wx.OK | wx.ICON_INFORMATION
                )
                return

            # Undo 등록
            old_frames = self._frames.clone()
            current_idx = self._frames.current_index
            memory_usage = old_frames.get_memory_usage()

            def execute():
                try:
                    if not self._frames._is_valid_index(current_idx):
                        raise IndexError(f"유효하지 않은 인덱스: {current_idx}")
                    self._frames.duplicate_frame(current_idx)
                    self._refresh_all()
                except Exception as e:
                    wx.MessageBox(
                        self._translations.tr("msg_frame_duplicate_error") + f":\n{e}",
                        self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR)
                    raise

            def undo():
                try:
                    self._frames = old_frames
                    self._refresh_all()
                except Exception as e:
                    wx.MessageBox(
                        self._translations.tr("msg_undo_error", e=e),
                        self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR)
                    raise

            self._undo_manager.execute_lambda("프레임 복제", execute, undo, memory_usage)
            self._is_modified = True
        except MemoryError:
            wx.MessageBox(
                self._translations.tr("msg_out_of_memory"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
        except Exception as e:
            wx.MessageBox(
                self._translations.tr("msg_frame_duplicate_error") + f": {e}",
                self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR)

    def _remove_duplicates(self):
        """중복 프레임 제거 — ProgressDialog 표시."""
        if self._frames.is_empty:
            return

        def _work(progress):
            self._frames.remove_duplicates(
                progress_callback=lambda c, t: progress(
                    c, t, self._translations.tr(
                        "prog_general_msg_detail", current=c, total=t,
                    ),
                ),
            )

        self._run_undoable_with_progress(
            title_key="prog_dedupe_title",
            description="중복 프레임 제거",
            work_fn=_work,
            no_undo_msg_key="msg_dup_removed_no_undo",
            error_key="msg_duplicate_remove_error",
        )

    def _show_mosaic_toolbar(self):
        """모자이크 인라인 툴바 표시"""
        if self._frames.is_empty:
            wx.MessageBox(
                self._translations.tr("msg_gif_open_required"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
            return
        self._show_inline_toolbar(self._mosaic_toolbar, show_target_frame_hint=True)

    def _show_speech_bubble_toolbar(self):
        """말풍선 인라인 툴바 표시"""
        if self._frames.is_empty:
            wx.MessageBox(
                self._translations.tr("msg_gif_open_required"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
            return
        self._show_inline_toolbar(self._speech_bubble_toolbar, show_target_frame_hint=True)

    def _show_watermark_toolbar(self):
        """워터마크 인라인 툴바 표시"""
        if self._frames.is_empty:
            wx.MessageBox(
                self._translations.tr("msg_gif_open_required"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
            return
        self._show_inline_toolbar(self._watermark_toolbar)

    def open_image_sequence(self):
        """이미지 시퀀스 폴더 열기"""
        if not self._confirm_save():
            return

        # 폴더 선택 다이얼로그
        dlg = wx.DirDialog(
            self,
            self._translations.tr("dlg_img_seq_folder_title"),
            self._last_directory if self._last_directory else "",
            wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST
        )

        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return

        folder_path = dlg.GetPath()
        dlg.Destroy()

        # 딜레이 설정 다이얼로그
        delay_dlg = wx.NumberEntryDialog(
            self,
            self._translations.tr("dlg_frame_delay_msg"),
            self._translations.tr("dlg_frame_delay_prompt"),
            self._translations.tr("dlg_frame_delay_title"),
            100,
            10,
            5000
        )

        if delay_dlg.ShowModal() != wx.ID_OK:
            delay_dlg.Destroy()
            return

        delay = delay_dlg.GetValue()
        delay_dlg.Destroy()

        try:
            # 이미지 시퀀스 로딩
            result = GifDecoder.load_from_folder(folder_path, pattern="*", default_delay=delay)

            if not result.success:
                wx.MessageBox(
                    self._translations.tr("msg_img_seq_load_failed_body", e=result.error_message),
                    self._translations.tr("msg_error"),
                    wx.OK | wx.ICON_ERROR
                )
                return

            self._last_directory = folder_path
            self._settings.Write("last_directory", self._last_directory)

            self._frames = result.frames
            self._undo_manager.clear()
            self._current_file_path = None
            self._is_modified = True

            self._refresh_all()
            self._update_title()
            self._update_info_bar()

            wx.MessageBox(
                self._translations.tr("msg_img_seq_loaded_body", count=self._frames.frame_count),
                self._translations.tr("common_done"),
                wx.OK | wx.ICON_INFORMATION
            )

        except Exception as e:
            wx.MessageBox(
                self._translations.tr("msg_img_seq_load_failed_body", e=str(e)),
                self._translations.tr("msg_error"),
                wx.OK | wx.ICON_ERROR
            )

    def _open_video_file(self, file_path: str):
        """비디오 파일 열기 (비동기 처리)"""
        try:
            from ..core.video_decoder import VideoDecoder
        except ImportError:
            wx.MessageBox(
                self._translations.tr("msg_video_decoder_unavailable"),
                self._translations.tr("msg_error"),
                wx.OK | wx.ICON_ERROR
            )
            return

        # 비디오 정보 확인
        video_info = VideoDecoder.get_video_info(file_path)
        if not video_info:
            wx.MessageBox(
                self._translations.tr("msg_video_info_unavailable"),
                self._translations.tr("msg_error"),
                wx.OK | wx.ICON_ERROR
            )
            return

        # FPS 설정 다이얼로그
        dlg = wx.NumberEntryDialog(
            self,
            self._translations.tr(
                "dlg_video_fps_msg", w=video_info.width, h=video_info.height, dur=video_info.duration),
            self._translations.tr("dlg_video_fps_prompt"),
            self._translations.tr("dlg_video_fps_title"),
            10,
            1,
            30
        )

        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return

        fps = dlg.GetValue()
        dlg.Destroy()

        # 진행률 대화상자
        self._video_progress = wx.ProgressDialog(
            self._translations.tr("prog_video_conv_title"),
            self._translations.tr("prog_video_conv_msg"),
            maximum=100,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT
        )
        self._video_file_path = file_path

        # 비동기 워커 생성
        worker = VideoLoadWorker(
            GifDecoder.load,
            file_path,
            video_fps=fps,
            video_max_frames=500
        )

        # 시그널 연결 (wxPython 스타일)
        worker.signals.connect('progress', self._on_video_load_progress)
        worker.signals.connect('finished', self._on_video_load_finished)
        worker.signals.connect('error', self._on_video_load_error)
        worker.signals.connect('cancelled', self._on_video_load_cancelled)

        # 취소 버튼 연결
        self._video_worker = worker

        # 워커 시작
        get_worker_manager().start(worker)

    def _on_video_load_progress(self, current: int, total: int):
        """비디오 로드 진행률 업데이트 (이미 wx.CallAfter 경유로 메인 스레드)"""
        try:
            if hasattr(self, '_video_progress') and self._video_progress:
                percent = int((current / total) * 100) if total > 0 else 0
                self._video_progress.Update(
                    percent,
                    self._translations.tr("prog_extract_frames_msg", current=current, total=total))
        except (RuntimeError, wx.PyDeadObjectError):
            pass

    def _on_video_load_finished(self, result):
        """비디오 로드 완료"""
        if hasattr(self, '_video_progress') and self._video_progress:
            wx.CallAfter(self._video_progress.Destroy)
            self._video_progress = None

        if not result.success:
            wx.CallAfter(
                wx.MessageBox,
                self._translations.tr("msg_video_load_failed", e=result.error_message),
                self._translations.tr("msg_error"),
                wx.OK | wx.ICON_ERROR
            )
            return

        # 마지막 경로 저장 및 최근 파일 추가
        file_path = getattr(self, '_video_file_path', None)
        if file_path:
            self._last_directory = str(Path(file_path).parent)
            self._add_recent_file(file_path)
        self._settings.Write("last_directory", self._last_directory)

        self._frames = result.frames
        self._undo_manager.clear()
        self._current_file_path = None  # 비디오 파일은 원본으로 저장 불가
        self._is_modified = True  # 변환된 상태이므로 저장 필요

        wx.CallAfter(self._refresh_all)
        wx.CallAfter(self._update_title)
        wx.CallAfter(self._update_info_bar)

        wx.CallAfter(
            wx.MessageBox,
            self._translations.tr("msg_video_converted_body", count=self._frames.frame_count),
            self._translations.tr("msg_video_converted_title"),
            wx.OK | wx.ICON_INFORMATION
        )

    def _on_video_load_error(self, error_msg: str, traceback: str):
        """비디오 로드 에러"""
        if hasattr(self, '_video_progress') and self._video_progress:
            wx.CallAfter(self._video_progress.Destroy)
            self._video_progress = None

        wx.CallAfter(
            wx.MessageBox,
            self._translations.tr("msg_video_load_failed", e=error_msg),
            self._translations.tr("msg_error"),
            wx.OK | wx.ICON_ERROR
        )

    def _on_video_load_cancelled(self):
        """비디오 로드 취소"""
        if hasattr(self, '_video_progress') and self._video_progress:
            wx.CallAfter(self._video_progress.Destroy)
            self._video_progress = None

    def _flip_frames(self, direction: str):
        """프레임 뒤집기 (가로/세로) — ProgressDialog 표시."""
        if self._frames.is_empty:
            return
        direction_name = "가로" if direction == 'h' else "세로"
        op = 'flip_horizontal' if direction == 'h' else 'flip_vertical'

        def _work(progress):
            n = self._frames.frame_count
            for i, frame in enumerate(self._frames):
                if frame:
                    getattr(frame, op)()
                if i % 8 == 0 or i == n - 1:
                    progress(i + 1, n, self._translations.tr(
                        "prog_general_msg_detail", current=i + 1, total=n,
                    ))

        self._run_undoable_with_progress(
            title_key="prog_flip_title",
            description=f"프레임 뒤집기 ({direction_name})",
            work_fn=_work,
            error_key="msg_flip_error",
        )

    def _reverse_frames(self):
        """역재생 (프레임 순서 뒤집기) — ProgressDialog 표시."""
        if self._frames.is_empty or self._frames.frame_count < 2:
            return

        def _work(progress):
            self._frames.reverse_frames(
                progress_callback=lambda c, t: progress(
                    c, t, self._translations.tr(
                        "prog_general_msg_detail", current=c, total=t,
                    ),
                ),
            )

        self._run_undoable_with_progress(
            title_key="prog_reverse_title",
            description="프레임 순서 반전",
            work_fn=_work,
            error_key="msg_reverse_error",
        )

    def _delete_selected_frames(self):
        """선택한 프레임 삭제"""
        if self._frames.is_empty:
            return

        selected = self._frames.selected_indices
        if not selected:
            selected = [self._frames.current_index]

        if len(selected) >= self._frames.frame_count:
            wx.MessageBox(
                self._translations.tr("msg_min_one_frame_body"),
                self._translations.tr("common_warning"),
                wx.OK | wx.ICON_WARNING
            )
            return

        try:
            self._frames.delete_frames(selected)
            self._is_modified = True
            self._refresh_all()
        except Exception as e:
            wx.MessageBox(
                self._translations.tr("msg_frame_reduce_error") + f": {e}",
                self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR)

    def _run_undoable_with_progress(
        self,
        *,
        title_key: str,
        description: str,
        work_fn,
        no_undo_msg_key: Optional[str] = None,
        error_key: str = "msg_error",
        large_threshold_mb: float = 100.0,
    ) -> None:
        """undo 가능한 frame 일괄 작업의 표준 진입점.

        - work_fn(progress) 을 background thread (run_with_progress) 에서 실행.
        - 메모리 100MB+ 면 clone 생략 (OOM 회피) + no_undo_msg_key 알림.
        - 100MB- 면 LambdaAction + push_executed 로 undo history 등록.
        - 모든 long-running frame 변형 작업이 동일 UX 를 갖도록 한다 (사용자
          요청: "프로세스가 오래 걸릴 때 무조건 프로그래시브 바가 나오는 로직").
        """
        if self._frames is None or self._frames.is_empty:
            return

        from ..utils.progress import run_with_progress
        from ..core.undo_manager import LambdaAction

        current_memory_mb = self._frames.get_memory_usage_mb()
        large_mode = current_memory_mb > large_threshold_mb
        total = self._frames.frame_count
        old_count_box = {'count': total}

        def _wrapper(progress):
            cloned = None if large_mode else self._frames.clone()
            old_count_box['count'] = self._frames.frame_count
            work_fn(progress)
            return cloned

        try:
            cloned, cancelled = run_with_progress(
                parent=self,
                title=self._translations.tr(title_key),
                work_func=_wrapper,
                total_hint=max(1, total),
                can_abort=False,
            )
        except MemoryError:
            wx.MessageBox(
                self._translations.tr("msg_out_of_memory"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING,
            )
            return
        except Exception as e:
            wx.MessageBox(
                self._translations.tr(error_key) + f":\n{e}",
                self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR,
            )
            return

        if cancelled:
            return

        self._is_modified = True

        if large_mode:
            if no_undo_msg_key:
                removed = old_count_box['count'] - self._frames.frame_count
                with contextlib.suppress(Exception):
                    wx.MessageBox(
                        self._translations.tr(
                            no_undo_msg_key, removed=removed, mb=current_memory_mb,
                        ),
                        self._translations.tr("common_done"),
                        wx.OK | wx.ICON_INFORMATION,
                    )
            self._refresh_all()
            return

        # undo 등록 — work_fn 은 thread 에서 이미 실행됐으므로 push_executed.
        old_frames = cloned
        memory_usage = old_frames.get_memory_usage() if old_frames else 0

        def execute():
            try:
                # redo 시점 — progress 는 no-op 으로 무시.
                work_fn(lambda *a, **k: None)
                self._refresh_all()
            except Exception as e:
                wx.MessageBox(
                    self._translations.tr(error_key) + f":\n{e}",
                    self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR,
                )
                raise

        def undo():
            try:
                self._frames = old_frames
                self._refresh_all()
            except Exception as e:
                wx.MessageBox(
                    self._translations.tr("msg_undo_error", e=e),
                    self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR,
                )
                raise

        action = LambdaAction(description, execute, undo, memory_usage)
        self._undo_manager.push_executed(action)
        self._refresh_all()

    def _reduce_frames(self):
        """프레임 감소 (매 2번째 프레임만 유지)."""
        def _work(progress):
            self._frames.reduce_frames(
                2,
                progress_callback=lambda c, t: progress(
                    c, t, self._translations.tr(
                        "prog_general_msg_detail", current=c, total=t,
                    ),
                ),
            )
        self._run_undoable_with_progress(
            title_key="prog_reduce_title",
            description="프레임 감소",
            work_fn=_work,
            no_undo_msg_key="msg_reduce_no_undo",
            error_key="msg_frame_reduce_error",
        )

    def _scale_speed(self, factor: float):
        """속도 조절 (딜레이에 역수 적용)

        Args:
            factor: 속도 배율 (2.0 = 2배속, 0.5 = 0.5배속)
        """
        if self._frames.is_empty:
            return

        try:
            old_delays = [f.delay_ms for f in self._frames]
            factor_str = f"{int(factor * 100)}%"

            def execute():
                try:
                    self._frames.scale_delays(1.0 / factor)
                    self._refresh_all()
                except Exception as e:
                    wx.MessageBox(
                        self._translations.tr("msg_speed_error") + f":\n{e}",
                        self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR)
                    raise

            def undo():
                try:
                    for i, delay in enumerate(old_delays):
                        if i < self._frames.frame_count:
                            self._frames[i].delay_ms = delay
                    self._refresh_all()
                except Exception as e:
                    wx.MessageBox(
                        self._translations.tr("msg_undo_error", e=e),
                        self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR)
                    raise

            self._undo_manager.execute_lambda(f"속도 조절 ({factor_str})", execute, undo, 0)
            self._is_modified = True

        except MemoryError:
            wx.MessageBox(
                self._translations.tr("msg_out_of_memory"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
        except Exception as e:
            wx.MessageBox(
                self._translations.tr("msg_speed_error") + f": {e}",
                self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR)

    def _set_all_delays(self):
        """모든 프레임 딜레이 일괄 설정"""
        if self._frames.is_empty:
            return

        # 현재 프레임의 딜레이를 기본값으로 사용
        current_frame = self._frames.current_frame
        current_delay = current_frame.delay_ms if current_frame and hasattr(current_frame, 'delay_ms') else 100

        # 딜레이 입력 다이얼로그
        dlg = wx.NumberEntryDialog(
            self,
            self._translations.tr("dlg_all_delay_msg"),
            self._translations.tr("dlg_all_delay_prompt"),
            self._translations.tr("dlg_all_delay_title"),
            current_delay,
            10,
            10000
        )

        if dlg.ShowModal() == wx.ID_OK:
            delay = dlg.GetValue()

            try:
                old_delays = [f.delay_ms for f in self._frames]

                def execute():
                    try:
                        self._frames.set_delay_for_all(delay)
                        self._refresh_all()
                    except Exception as e:
                        wx.MessageBox(
                            self._translations.tr("msg_delay_error") + f":\n{e}",
                            self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR)
                        raise

                def undo():
                    try:
                        for i, old_delay in enumerate(old_delays):
                            if i < self._frames.frame_count:
                                self._frames[i].delay_ms = old_delay
                        self._refresh_all()
                    except Exception as e:
                        wx.MessageBox(
                            self._translations.tr("msg_undo_error", e=e),
                            self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR)
                        raise

                self._undo_manager.execute_lambda(f"모든 프레임 딜레이 설정 ({delay}ms)", execute, undo, 0)
                self._is_modified = True

            except MemoryError:
                wx.MessageBox(
                    self._translations.tr("msg_out_of_memory"),
                    self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
            except Exception as e:
                wx.MessageBox(
                    self._translations.tr("msg_delay_error") + f": {e}",
                    self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR)

        dlg.Destroy()

    def _apply_yoyo(self):
        """요요 효과 (순방향 + 역방향) — ProgressDialog 표시."""
        if self._frames.is_empty or self._frames.frame_count < 2:
            return

        def _work(progress):
            self._frames.apply_yoyo_effect(
                progress_callback=lambda c, t: progress(
                    c, t, self._translations.tr(
                        "prog_general_msg_detail", current=c, total=t,
                    ),
                ),
            )

        self._run_undoable_with_progress(
            title_key="prog_yoyo_title",
            description="요요 효과 적용",
            work_fn=_work,
            error_key="msg_yoyo_error",
        )
        return

    def _show_speed_dialog(self):
        """속도 조절 툴바 표시"""
        if self._frames.is_empty:
            wx.MessageBox(
                self._translations.tr("msg_gif_open_required"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
            return
        self._show_inline_toolbar(self._speed_toolbar)

    def _show_reduce_toolbar(self):
        """프레임 줄이기 툴바 표시"""
        if self._frames.is_empty:
            wx.MessageBox(
                self._translations.tr("msg_gif_open_required"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
            return
        self._show_inline_toolbar(self._reduce_toolbar)

    def _split_gif(self):
        """선택한 프레임들을 별도 GIF로 저장 (비동기 처리)"""
        if self._frames.is_empty:
            wx.MessageBox(
                self._translations.tr("msg_gif_open_required"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
            return

        selected = self._frames.selected_indices
        if not selected:
            wx.MessageBox(
                self._translations.tr("msg_select_frames_to_split_body"),
                self._translations.tr("common_warning"),
                wx.OK | wx.ICON_WARNING
            )
            return

        # 저장 경로 선택
        dlg = wx.FileDialog(
            self,
            self._translations.tr("dlg_split_gif_title"),
            self._last_directory,
            "",
            self._translations.tr("dlg_gif_filter"),
            wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )

        if dlg.ShowModal() == wx.ID_OK:
            file_path = dlg.GetPath()
            if not file_path.lower().endswith('.gif'):
                file_path += '.gif'

            try:
                # 선택된 프레임으로 새 컬렉션 생성
                from ..core import FrameCollection, Frame
                new_collection = FrameCollection()

                for idx in sorted(selected):
                    if 0 <= idx < len(self._frames._frames):
                        frame = self._frames._frames[idx]
                        new_frame = Frame(frame.image.copy(), frame.delay_ms)
                        new_collection.add_frame(new_frame)

                if new_collection.is_empty:
                    wx.MessageBox(
                        self._translations.tr("msg_no_frames_to_save"),
                        self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
                    dlg.Destroy()
                    return

                # 진행 다이얼로그 생성
                progress = wx.ProgressDialog(
                    self._translations.tr("prog_split_gif_title"),
                    self._translations.tr("prog_split_gif_msg"),
                    style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
                )
                self._split_progress = progress
                self._split_file_path = file_path
                self._split_frame_count = len(selected)

                # 비동기 저장 작업 시작
                from ..core import get_worker_manager
                worker = FunctionWorker(GifEncoder.save, new_collection, file_path)
                worker.signals.connect('finished', self._on_split_gif_finished)
                worker.signals.connect('error', self._on_split_gif_error)
                get_worker_manager().start(worker)

            except Exception as e:
                wx.MessageBox(
                    self._translations.tr("msg_split_save_error", e=e),
                    self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR)

        dlg.Destroy()

    def _merge_gif(self):
        """다른 GIF 파일을 현재 GIF 끝에 병합 (비동기 처리, Undo 지원)"""
        if self._frames.is_empty:
            wx.MessageBox(
                self._translations.tr("msg_gif_open_required"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
            return

        # 파일 선택
        dlg = wx.FileDialog(
            self,
            self._translations.tr("dlg_merge_gif_title"),
            self._last_directory,
            "",
            self._translations.tr("dlg_gif_filter"),
            wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )

        if dlg.ShowModal() == wx.ID_OK:
            file_path = dlg.GetPath()

            # 진행 다이얼로그 생성
            progress = wx.ProgressDialog(
                self._translations.tr("prog_merge_gif_title"),
                self._translations.tr("prog_merge_gif_msg"),
                style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
            )

            # 비동기 로딩 작업 시작
            from ..core import FunctionWorker, get_worker_manager
            worker = FunctionWorker(GifDecoder.load, file_path)
            worker.signals.connect('finished', lambda result: self._on_merge_gif_finished(result, file_path, progress))
            worker.signals.connect('error', lambda msg, tb: self._on_merge_gif_error(msg, progress))
            get_worker_manager().start(worker)

        dlg.Destroy()

    def _insert_gif(self):
        """다른 GIF 파일을 현재 위치에 삽입 (비동기 처리, Undo 지원)"""
        if self._frames.is_empty:
            wx.MessageBox(
                self._translations.tr("msg_gif_open_required"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
            return

        # 파일 선택
        dlg = wx.FileDialog(
            self,
            self._translations.tr("dlg_insert_gif_title"),
            self._last_directory,
            "",
            self._translations.tr("dlg_gif_filter"),
            wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )

        if dlg.ShowModal() == wx.ID_OK:
            file_path = dlg.GetPath()
            insert_index = self._frames.current_index + 1

            # 진행 다이얼로그 생성
            progress = wx.ProgressDialog(
                self._translations.tr("prog_insert_gif_title"),
                self._translations.tr("prog_insert_gif_msg"),
                style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
            )

            # 비동기 로딩 작업 시작
            from ..core import FunctionWorker, get_worker_manager
            worker = FunctionWorker(GifDecoder.load, file_path)
            worker.signals.connect(
                'finished',
                lambda result: self._on_insert_gif_finished(result, file_path, insert_index, progress))
            worker.signals.connect('error', lambda msg, tb: self._on_insert_gif_error(msg, progress))
            get_worker_manager().start(worker)

        dlg.Destroy()

    # ==================== 기타 ====================

    def _detect_low_end_mode(self) -> bool:
        """저사양 모드 감지"""
        return False

    def _enable_low_end_mode_for_large_gif(self):
        """큰 GIF에 대해 저사양 모드 활성화.

        한 번 알림을 본 사용자에게는 다시 표시하지 않는다 (settings 영구 기록).
        활성화 자체는 매번 자동 수행되어 성능 효과는 동일.
        """
        if self._is_low_end_mode:
            return  # 이미 활성화됨

        self._is_low_end_mode = True
        self._preview_delay = 300

        # 인라인 툴바에 설정 전파
        for toolbar in [
            self._text_toolbar, self._sticker_toolbar, self._effects_toolbar,
            self._mosaic_toolbar, self._speech_bubble_toolbar,
            self._resize_toolbar, self._watermark_toolbar, self._rotate_toolbar,
        ]:
            if hasattr(toolbar, '_is_low_end_mode'):
                toolbar._is_low_end_mode = True
            if hasattr(toolbar, '_preview_delay'):
                toolbar._preview_delay = 300

        # 이전에 알림을 본 사용자에겐 재표시하지 않는다 (오픈할 때마다 같은 다이얼로그가
        # 뜨면 피로하다는 보고에 대한 응답). 활성화 자체는 매번 자동 수행.
        with contextlib.suppress(Exception):
            if self._settings.ReadBool("low_end_mode_notified", False):
                return

        wx.MessageBox(
            self._translations.tr("msg_low_end_mode_body", count=self._frames.frame_count),
            self._translations.tr("msg_low_end_mode_title"),
            wx.OK | wx.ICON_INFORMATION
        )
        with contextlib.suppress(Exception):
            self._settings.WriteBool("low_end_mode_notified", True)

    def _add_recent_file(self, file_path: str):
        """최근 파일 추가"""
        # 절대 경로로 변환
        file_path = str(Path(file_path).resolve())
        if file_path in self._recent_files:
            self._recent_files.remove(file_path)
        self._recent_files.insert(0, file_path)
        self._recent_files = self._recent_files[:self._max_recent_files]
        self._settings.Write("recent_files", '|'.join(self._recent_files))
        self._update_recent_files_menu()

    def _update_recent_files_menu(self):
        """최근 파일 메뉴 업데이트"""
        # 기존 항목 제거
        for item in self._recent_menu.GetMenuItems():
            self._recent_menu.Delete(item)

        # 새 항목 추가
        if not self._recent_files:
            item = self._recent_menu.Append(wx.ID_ANY, self._translations.tr("recent_files_none"))
            item.Enable(False)
        else:
            for i, file_path in enumerate(self._recent_files, 1):
                label = f"{i}. {os.path.basename(file_path)}"
                item = self._recent_menu.Append(wx.ID_ANY, label, file_path)
                self._recent_menu.Bind(wx.EVT_MENU, lambda e, path=file_path: self.open_file(path), item)

    def _clear_recent_files(self):
        """최근 파일 목록 지우기"""
        dlg = wx.MessageDialog(
            self,
            self._translations.tr("msg_clear_recent_confirm"),
            self._translations.tr("msg_confirm"),
            wx.YES_NO | wx.ICON_QUESTION
        )

        if dlg.ShowModal() == wx.ID_YES:
            self._recent_files.clear()
            self._settings.Write("recent_files", "")
            self._update_recent_files_menu()
            wx.MessageBox(
                self._translations.tr("msg_recent_cleared"),
                self._translations.tr("common_done"), wx.OK | wx.ICON_INFORMATION)

        dlg.Destroy()

    def _offer_index_color_optimization(self) -> None:
        """대용량 RGBA/RGB 컬렉션을 인덱스 컬러 (P, 256색) 로 변환할지 사용자에게 제안.

        조건: 한 파일 당 1회, 메모리 500MB 초과, 비-P 프레임 존재. yes 응답 시
        ProgressDialog 와 함께 일괄 변환 후 메모리·캔버스 새로고침.
        화질은 256색으로 손실되지만 원본 파일은 변경되지 않는다.
        """
        if self._index_color_offer_done:
            return
        if self._frames is None or self._frames.is_empty:
            return

        try:
            memory_mb = self._frames.get_memory_usage_mb()
        except Exception:
            return

        # 임계: 500MB. 작은 GIF 는 변환 비용·화질 손실 대비 이득이 적다.
        if memory_mb < 500:
            return

        # 모든 프레임이 이미 P 모드면 변환 효과 없음 — 다이얼로그 생략.
        try:
            has_non_p = self._frames.has_non_p_mode_frames()
        except Exception:
            has_non_p = True
        if not has_non_p:
            self._index_color_offer_done = True
            return

        self._index_color_offer_done = True

        expected_mb = memory_mb / 4.0
        dlg = wx.MessageDialog(
            self,
            self._translations.tr(
                "msg_index_color_offer_body", mb=memory_mb, expected=expected_mb,
            ),
            self._translations.tr("msg_index_color_offer_title"),
            wx.YES_NO | wx.ICON_QUESTION,
        )
        choice = dlg.ShowModal()
        dlg.Destroy()
        if choice != wx.ID_YES:
            return

        # 진행률 다이얼로그 + 배치 변환
        total = self._frames.frame_count
        progress = wx.ProgressDialog(
            self._translations.tr("prog_index_color_title"),
            self._translations.tr("prog_index_color_msg", current=0, total=total),
            maximum=total,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_SMOOTH,
        )

        def _cb(current: int, total_count: int) -> None:
            progress.Update(
                current,
                self._translations.tr(
                    "prog_index_color_msg", current=current, total=total_count,
                ),
            )

        try:
            converted = self._frames.convert_all_to_p_mode(progress_callback=_cb)
        except Exception as e:
            progress.Destroy()
            wx.MessageBox(
                self._translations.tr("msg_index_color_failed", e=str(e)),
                self._translations.tr("common_error"),
                wx.OK | wx.ICON_ERROR,
            )
            return
        finally:
            with contextlib.suppress(Exception):
                progress.Destroy()

        # 변환 후 메모리·UI 새로고침
        self._update_info_bar()
        self._refresh_all()
        try:
            new_mb = self._frames.get_memory_usage_mb()
        except Exception:
            new_mb = expected_mb
        wx.MessageBox(
            self._translations.tr(
                "msg_index_color_converted",
                converted=converted,
                before=memory_mb,
                after=new_mb,
            ),
            self._translations.tr("common_done"),
            wx.OK | wx.ICON_INFORMATION,
        )

    def _check_memory_limit(self, memory_mb: float) -> None:
        """메모리 사용량이 1GB를 초과할 때 사용자에게 메모리 제한 확대 여부를 물어봄

        Args:
            memory_mb: 현재 메모리 사용량 (MB)
        """
        # 이미 메모리 제한이 확대되었으면 다시 묻지 않음
        if self._memory_limit_expanded:
            return

        # 1GB(1024MB) 초과 시 경고
        if memory_mb > 1024:
            dlg = wx.MessageDialog(
                self,
                self._translations.tr("msg_memory_limit_body", mb=memory_mb),
                self._translations.tr("msg_memory_warning_title"),
                wx.YES_NO | wx.ICON_WARNING
            )

            if dlg.ShowModal() == wx.ID_YES:
                # 메모리 제한 2배 확대
                # FrameMemoryManager 의 실제 메서드는 *_mb 접미사. (set_memory_limit/
                # get_memory_limit 이라는 이름은 존재하지 않아 AttributeError 회귀를 유발했다.)
                self._memory_manager.set_memory_limit_mb(self._memory_manager.get_memory_limit_mb() * 2)
                self._memory_limit_expanded = True
                wx.MessageBox(
                    self._translations.tr("msg_memory_limit_expanded", mb=self._memory_manager.get_memory_limit_mb()),
                    self._translations.tr("common_done"),
                    wx.OK | wx.ICON_INFORMATION
                )
            else:
                self._memory_limit_expanded = True  # 다시 묻지 않음

            dlg.Destroy()

    def _show_help_dialog(self):
        """도움말 다이얼로그 표시"""
        from .dialogs.help_dialog_wx import HelpDialog
        dlg = HelpDialog(self)
        dlg.ShowModal()
        dlg.Destroy()

    def _show_about_dialog(self):
        """정보 다이얼로그 표시"""
        from .dialogs.help_dialog_wx import AboutDialog

        dlg = AboutDialog(self)
        dlg.ShowModal()
        dlg.Destroy()

    def _init_gpu_menu_state(self):
        """GPU 메뉴 상태 비동기 초기화 (에디터 UI 표시 후 호출)"""
        import threading

        def _check_gpu_bg():
            try:
                available = gpu_utils.is_gpu_available()
                enabled = gpu_utils.is_gpu_enabled()
            except Exception:
                available = False
                enabled = False
            wx.CallAfter(self._apply_gpu_menu_state, available, enabled)

        threading.Thread(target=_check_gpu_bg, daemon=True).start()

    def _apply_gpu_menu_state(self, available, enabled):
        """GPU 메뉴 상태 적용 (메인 스레드)"""
        try:
            if not self._action_gpu:
                return
            text = self._translations.tr("action_gpu") if available else self._translations.tr("action_gpu_no_gpu")
            self._action_gpu.SetItemLabel(text)
            self._action_gpu.Check(enabled)
            self._action_gpu.Enable(available)
        except (RuntimeError, wx.PyDeadObjectError):
            pass

    def _toggle_gpu(self, checked: bool):
        """GPU 토글"""
        gpu_utils.set_gpu_enabled(checked)
        self._update_gpu_status()

    def _show_gpu_info(self):
        """GPU 정보 표시"""
        if not gpu_utils.is_gpu_available():
            # CuPy 미설치 + NVIDIA GPU 존재 → 설치 가이드
            init_error = gpu_utils.get_gpu_init_error() or ""
            if ("CuPy" in init_error or "cupy" in init_error.lower()) and gpu_utils.has_nvidia_gpu_hardware():
                self._offer_cupy_install()
            else:
                # NVIDIA GPU 없음
                wx.MessageBox(
                    self._translations.tr("cupy_guide_no_nvidia"),
                    self._translations.tr("msg_gpu_info"),
                    wx.OK | wx.ICON_INFORMATION
                )
            return

        gpu_info = gpu_utils.get_gpu_info()
        info_text = self._translations.tr(
            "msg_gpu_info_detail",
            name=gpu_info.get('name', 'Unknown'),
            memory=gpu_info.get('memory_total', 0),
            capability=gpu_info.get('compute_capability', 'Unknown'),
            status=("GPU" if gpu_utils.is_gpu_enabled() else "CPU")
        )
        wx.MessageBox(info_text, self._translations.tr("msg_gpu_info"), wx.OK | wx.ICON_INFORMATION)

    # ==================== CuPy 설치 ====================

    def _check_cupy_install_offer(self):
        """시작 시 CuPy 설치 제안 (조건 확인)"""
        try:
            if gpu_utils.is_gpu_available():
                return
            if self._settings.ReadBool("cupy_install_dismissed", False):
                return
            if not gpu_utils.has_nvidia_gpu_hardware():
                return
            init_error = gpu_utils.get_gpu_init_error() or ""
            if "CuPy" not in init_error and "cupy" not in init_error.lower():
                return
            self._offer_cupy_install()
        except Exception as e:
            self._logger.debug(f"CuPy install check skipped: {e}")

    def _offer_cupy_install(self):
        """CuPy 설치 가이드 다이얼로그 표시"""
        from ui.dependency_dialogs import CuPyInstallGuideDialog
        dlg = CuPyInstallGuideDialog(self)
        ret = dlg.ShowModal()
        dlg.Destroy()

        if ret == wx.ID_OK:
            # 설치 성공 → GPU 재초기화
            gpu_utils.initialize_gpu(force=True)
            self._update_gpu_status()
        else:
            self._settings.WriteBool("cupy_install_dismissed", True)

    # ==================== 이벤트 핸들러 ====================

    def OnSize(self, event):
        """크기 변경"""
        event.Skip()

    def OnShow(self, event):
        """표시"""
        event.Skip()
        if event.IsShown():
            apply_dark_title_bar(self)

    def closeEvent(self, event):
        """종료"""
        if not self._confirm_save():
            event.Veto()
            return

        self._play_timer.Stop()
        self._gpu_update_timer.Stop()
        self._cleanup_workers()

        from ..core.worker_wx import shutdown_worker_manager
        shutdown_worker_manager()

        # 마지막 주요 창이 닫힌 경우, 잔여 툴/오버레이 창까지 정리하여 앱 종료 보장
        wx.CallLater(120, ensure_exit_if_no_primary_windows, "editor_window_close")

        event.Skip()

    def _cleanup_workers(self):
        """Worker 시그널 해제 및 참조 정리 (메모리 누수 방지)"""
        worker_attrs = [
            '_video_worker',
            '_split_worker',
            '_merge_worker',
            '_insert_worker',
            '_save_worker',
        ]

        for attr in worker_attrs:
            if hasattr(self, attr):
                worker = getattr(self, attr, None)
                if worker is not None:
                    try:
                        # wxPython worker의 시그널 정리
                        if hasattr(worker, 'signals'):
                            signals = worker.signals
                            # 콜백 리스트 초기화
                            if hasattr(signals, 'finished_callbacks'):
                                signals.finished_callbacks.clear()
                            if hasattr(signals, 'error_callbacks'):
                                signals.error_callbacks.clear()
                            if hasattr(signals, 'progress_callbacks'):
                                signals.progress_callbacks.clear()
                            if hasattr(signals, 'progress_message_callbacks'):
                                signals.progress_message_callbacks.clear()
                            if hasattr(signals, 'started_callbacks'):
                                signals.started_callbacks.clear()
                            if hasattr(signals, 'cancelled_callbacks'):
                                signals.cancelled_callbacks.clear()

                        # Worker 취소 시도
                        if hasattr(worker, 'cancel'):
                            worker.cancel()
                    except Exception as e:
                        self._logger.debug(f"Worker {attr} 정리 중 오류: {e}")
                    finally:
                        # 참조 제거
                        setattr(self, attr, None)

    def OnKeyDown(self, event):
        """키보드 이벤트 처리"""
        key = event.GetKeyCode()

        # Space: 재생/일시정지
        if key == wx.WXK_SPACE:
            self.toggle_play()
            return

        # Ctrl 조합
        if event.ControlDown():
            # Ctrl+O: 파일 열기
            if key == ord('O'):
                self.open_file()
                return
            # Ctrl+S: 저장
            elif key == ord('S'):
                if event.ShiftDown():
                    self.save_file_as()
                else:
                    self.save_file()
                return
            # Ctrl+N: 새 프로젝트
            elif key == ord('N'):
                self.new_project()
                return
            # Ctrl+A: 모두 선택
            elif key == ord('A'):
                self._select_all()
                return
            # Ctrl+D: 복제
            elif key == ord('D'):
                self._duplicate_frame()
                return

        # Delete: 프레임 삭제
        if key == wx.WXK_DELETE:
            self._delete_frame()
            return

        # Left/Right: 프레임 네비게이션
        if key == wx.WXK_LEFT:
            if self._frames.previous_frame():
                self._refresh_all()
            return
        if key == wx.WXK_RIGHT:
            if self._frames.next_frame():
                self._refresh_all()
            return

        event.Skip()

    # ==================== 툴바 표시 메서드 ====================

    def _hide_active_inline_toolbar(self):
        """현재 활성 인라인 툴바 숨기기"""
        if self._active_inline_toolbar:
            self._active_inline_toolbar.deactivate()
            self._active_inline_toolbar = None

        # PropertyBar 숨기기
        self._property_bar.hide_all()

        # 공유 액션 버튼 숨기기
        self._hide_action_buttons()

        # 툴바 버튼 다시 활성화
        if hasattr(self, '_icon_toolbar'):
            self._icon_toolbar.set_edit_mode(False)

        # 저장 버튼 다시 활성화
        self._set_save_buttons_enabled(True)

        # 모든 캔버스 모드 종료
        if hasattr(self, '_canvas') and self._canvas:
            canvas = self._canvas
            if hasattr(canvas, 'stop_text_edit_mode'):
                canvas.stop_text_edit_mode()
            if hasattr(canvas, 'stop_sticker_mode'):
                canvas.stop_sticker_mode()
            if hasattr(canvas, 'stop_speech_bubble_mode'):
                canvas.stop_speech_bubble_mode()
            if hasattr(canvas, 'stop_mosaic_mode'):
                canvas.stop_mosaic_mode()
            if hasattr(canvas, 'stop_crop_mode'):
                canvas.stop_crop_mode()
            if hasattr(canvas, 'stop_drawing_mode'):
                canvas.stop_drawing_mode()

    def _maybe_show_target_frame_hint(self) -> None:
        """대상 프레임 선택 안내 팝업 표시 ("다시 보지 않기" 토글 포함)"""

        if not TargetFrameHintDialog.should_show(self._settings):
            return

        dlg = TargetFrameHintDialog(
            parent=self,
            settings=self._settings,
        )
        dlg.ShowModal()
        dlg.Destroy()

    def _get_toolbar_mode_name(self, toolbar) -> str:
        """툴바 객체에서 모드 이름 반환"""
        if not hasattr(self, '_text_toolbar'):
            return ""

        toolbar_map = {
            self._text_toolbar: 'text',
            self._sticker_toolbar: 'sticker',
            self._crop_toolbar: 'crop',
            self._resize_toolbar: 'resize',
            self._effects_toolbar: 'effects',
            self._speed_toolbar: 'speed',
            self._rotate_toolbar: 'rotate',
            self._mosaic_toolbar: 'mosaic',
            self._speech_bubble_toolbar: 'speech_bubble',
            self._watermark_toolbar: 'watermark',
            self._reduce_toolbar: 'reduce',
            self._pencil_toolbar: 'pencil',
        }
        return toolbar_map.get(toolbar, "")

    def _set_save_buttons_enabled(self, enabled: bool):
        """저장 버튼 활성/비활성 설정"""
        if hasattr(self, '_save_btn'):
            self._save_btn.Enable(enabled)
        if hasattr(self, '_action_save'):
            self._action_save.Enable(enabled)
        if hasattr(self, '_action_save_as'):
            self._action_save_as.Enable(enabled)

    def _create_action_button(self, label: str, handler, *, primary: bool = False) -> wx.Button:
        """하단 공유 액션 버튼 생성"""
        button = wx.Button(self._bottom_controls, label=label)
        apply_button_style(button, primary=primary)
        button.SetMinSize((74, 30))
        button.Bind(wx.EVT_BUTTON, handler)
        button.Hide()
        return button

    def _show_action_buttons(self, toolbar):
        """공유 액션 버튼 표시"""
        if not getattr(toolbar, 'has_action_buttons', True):
            self._hide_action_buttons()
            return
        if hasattr(toolbar, 'has_clear_button') and toolbar.has_clear_button:
            self._action_clear_btn.Show()
        else:
            self._action_clear_btn.Hide()
        self._action_apply_btn.Show()
        self._action_cancel_btn.Show()
        self._bottom_controls.Layout()

    def _hide_action_buttons(self):
        """공유 액션 버튼 숨기기"""
        self._action_clear_btn.Hide()
        self._action_apply_btn.Hide()
        self._action_cancel_btn.Hide()
        self._bottom_controls.Layout()

    def _on_action_apply(self, event):
        """공유 적용 버튼 클릭 → 활성 툴바에 위임"""
        if self._active_inline_toolbar:
            self._active_inline_toolbar._on_apply(event)

    def _on_action_cancel(self, event):
        """공유 취소 버튼 클릭 → 활성 툴바에 위임"""
        if self._active_inline_toolbar:
            self._active_inline_toolbar._on_cancel(event)

    def _on_action_clear(self, event):
        """공유 초기화 버튼 클릭 → 활성 툴바에 위임"""
        if self._active_inline_toolbar:
            self._active_inline_toolbar._on_clear(event)

    def _show_inline_toolbar(self, toolbar, show_target_frame_hint: bool = False):
        """인라인 툴바 표시"""
        # 지연 초기화가 아직 안 됐으면 즉시 실행
        if not self._inline_toolbars_initialized:
            self._deferred_init_inline_toolbars()
        if show_target_frame_hint:
            self._maybe_show_target_frame_hint()

        self._hide_active_inline_toolbar()

        mode_name = self._get_toolbar_mode_name(toolbar)
        if hasattr(self, '_icon_toolbar') and mode_name:
            active_btn = self._icon_toolbar.get_button_by_mode(mode_name)
            self._icon_toolbar.set_edit_mode(True, active_btn)

        self._set_save_buttons_enabled(False)
        self._active_inline_toolbar = toolbar

        # PropertyBar에 표시
        if mode_name:
            self._property_bar.show_toolbar(mode_name)
        toolbar.activate()

        # 공유 액션 버튼 표시
        self._show_action_buttons(toolbar)

    def _show_text_dialog(self):
        """텍스트 인라인 툴바 표시"""
        if self._frames.is_empty:
            wx.MessageBox(
                self._translations.tr("msg_gif_open_required"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
            return
        self._show_inline_toolbar(self._text_toolbar, show_target_frame_hint=True)

    def _show_sticker_dialog(self):
        """스티커 인라인 툴바 표시"""
        if self._frames.is_empty:
            wx.MessageBox(
                self._translations.tr("msg_gif_open_required"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
            return
        self._show_inline_toolbar(self._sticker_toolbar, show_target_frame_hint=True)

    def _show_crop_dialog(self):
        """자르기 인라인 툴바 표시"""
        if self._frames.is_empty:
            wx.MessageBox(
                self._translations.tr("msg_gif_open_required"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
            return
        self._show_inline_toolbar(self._crop_toolbar)

    def _show_resize_dialog(self):
        """크기 조절 인라인 툴바 표시"""
        if self._frames.is_empty:
            wx.MessageBox(
                self._translations.tr("msg_gif_open_required"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
            return
        self._show_inline_toolbar(self._resize_toolbar)

    def _show_effects_dialog(self):
        """효과 인라인 툴바 표시"""
        if self._frames.is_empty:
            wx.MessageBox(
                self._translations.tr("msg_gif_open_required"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
            return
        self._show_inline_toolbar(self._effects_toolbar, show_target_frame_hint=True)

    def _show_rotate_toolbar(self):
        """회전 인라인 툴바 표시"""
        if self._frames.is_empty:
            wx.MessageBox(
                self._translations.tr("msg_gif_open_required"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
            return
        self._show_inline_toolbar(self._rotate_toolbar)

    def _rotate_frames(self, angle: int):
        """프레임 회전 — ProgressDialog 표시.

        Args:
            angle: 회전 각도 (0, 90, 180, 270)
        """
        if self._frames.is_empty or angle == 0:
            return

        def _work(progress):
            n = self._frames.frame_count
            for i, frame in enumerate(self._frames):
                if frame:
                    frame.rotate(angle)
                if i % 8 == 0 or i == n - 1:
                    progress(i + 1, n, self._translations.tr(
                        "prog_general_msg_detail", current=i + 1, total=n,
                    ))

        self._run_undoable_with_progress(
            title_key="prog_rotate_title",
            description=f"프레임 회전 ({angle}도)",
            work_fn=_work,
            error_key="msg_rotate_error",
        )

    def _show_pencil_dialog(self):
        """펜슬 인라인 툴바 표시"""
        if self._frames.is_empty:
            wx.MessageBox(
                self._translations.tr("msg_gif_open_required"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
            return
        self._show_inline_toolbar(self._pencil_toolbar, show_target_frame_hint=True)

    # ==================== 프레임 이벤트 핸들러 ====================

    def _on_frame_selected(self, event):
        """프레임 선택 이벤트 핸들러 (프레임 리스트에서 선택 시)"""
        try:
            # FrameSelectedEvent는 indices 리스트를 가짐
            indices = event.indices if hasattr(event, 'indices') else []
            if not indices:
                return

            first_index = indices[0]
            if 0 <= first_index < self._frames.frame_count:
                # current_index는 이미 frame_list_widget에서 설정됨
                # 여기서는 캔버스와 슬라이더만 업데이트
                if hasattr(self, '_canvas') and self._canvas:
                    self._canvas.Refresh()
                    self._canvas.Update()  # 즉시 그리기
                self._update_slider()  # 슬라이더 위치 업데이트
        except Exception:
            pass

    def _on_delay_changed(self, event):
        """프레임 딜레이 변경 이벤트 핸들러"""
        with contextlib.suppress(Exception):
            self._update_info_bar()

    def _on_frames_deleted(self, event):
        """프레임 삭제 이벤트 핸들러"""
        with contextlib.suppress(Exception):
            self._update_info_bar()
            self._refresh_all()

    # ==================== 언어 전환 ====================

    def _toggle_language(self):
        """언어 토글 (En <-> 한)"""
        # 활성화된 인라인 툴바 숨기기
        self._hide_active_inline_toolbar()

        # 언어 전환
        self._is_korean = not self._is_korean
        self._translations.set_language(self._is_korean)

        if hasattr(self, '_canvas') and self._canvas:
            self._canvas.Refresh()

        # 언어 토글 버튼 텍스트 및 툴팁 업데이트
        if hasattr(self, '_lang_toggle_btn') and self._lang_toggle_btn:
            self._lang_toggle_btn.SetLabel("En" if self._is_korean else "한")
            self._lang_toggle_btn.SetToolTip(self._translations.tr("lang_toggle_tooltip"))

        # 모든 UI 텍스트 업데이트
        self._update_all_ui_texts()

    def _update_all_ui_texts(self):
        """모든 UI 텍스트를 현재 언어로 업데이트"""
        # 윈도우 타이틀 업데이트
        self._update_title()

        # 메뉴 업데이트
        self._update_menu_texts()

        # 툴바 업데이트
        if hasattr(self, '_icon_toolbar') and hasattr(self._icon_toolbar, 'update_texts'):
            self._icon_toolbar.update_texts(self._translations)

        # 프레임 리스트 업데이트
        if hasattr(self, '_frame_list') and hasattr(self._frame_list, 'update_texts'):
            self._frame_list.update_texts(self._translations)

        # 인라인 툴바 업데이트
        self._update_inline_toolbar_texts()

        # 하단 버튼 텍스트 업데이트
        if hasattr(self, '_close_btn') and self._close_btn:
            self._close_btn.SetLabel(self._translations.tr("btn_close_edit"))
            self._close_btn.SetToolTip(self._translations.tr("btn_close_edit_tooltip"))
        if hasattr(self, '_save_btn') and self._save_btn:
            self._save_btn.SetLabel(self._translations.tr("btn_save"))
            self._save_btn.SetToolTip(self._translations.tr("btn_save_tooltip"))

        # 공유 액션 버튼 텍스트 업데이트
        if hasattr(self, '_action_clear_btn'):
            self._action_clear_btn.SetLabel(self._translations.tr("toolbar_clear"))
        if hasattr(self, '_action_apply_btn'):
            self._action_apply_btn.SetLabel(self._translations.tr("toolbar_apply"))
        if hasattr(self, '_action_cancel_btn'):
            self._action_cancel_btn.SetLabel(self._translations.tr("toolbar_cancel"))

        # 재생 버튼 툴팁 업데이트
        if hasattr(self, '_play_btn') and self._play_btn:
            tip_key = "btn_play_tooltip" if not self._is_playing else "btn_pause_tooltip"
            self._play_btn.SetToolTip(self._translations.tr(tip_key))

        # 정보 바 라벨 툴팁 업데이트
        if hasattr(self, '_size_info') and self._size_info:
            self._size_info.SetToolTip(self._translations.tr("info_size_tooltip"))
        if hasattr(self, '_frame_count_info') and self._frame_count_info:
            self._frame_count_info.SetToolTip(self._translations.tr("info_frame_count_tooltip"))
        if hasattr(self, '_duration_info') and self._duration_info:
            self._duration_info.SetToolTip(self._translations.tr("info_duration_tooltip"))
        if hasattr(self, '_memory_value') and self._memory_value:
            self._memory_value.SetToolTip(self._translations.tr("info_memory_tooltip"))

        # 정보 바 업데이트 (내부에서 GPU 상태도 업데이트)
        self._update_info_bar()

        # 최근 파일 메뉴 업데이트
        self._update_recent_files_menu()

    def _update_menu_texts(self):
        """메뉴 텍스트 업데이트"""
        # wxPython에서는 각 메뉴 항목을 개별적으로 업데이트해야 합니다
        # 메뉴바가 있으면 처리
        if not hasattr(self, '_menubar'):
            return

        menubar = self._menubar

        # 메뉴 제목 업데이트
        menu_count = menubar.GetMenuCount()
        for i in range(menu_count):
            menu = menubar.GetMenu(i)
            label = menubar.GetMenuLabel(i)

            # 메뉴 제목 업데이트
            if "파일" in label or "File" in label:
                menubar.SetMenuLabel(i, self._translations.tr("menu_file"))
            elif "편집" in label or "Edit" in label:
                menubar.SetMenuLabel(i, self._translations.tr("menu_edit"))
            elif "관리" in label or "Manage" in label:
                menubar.SetMenuLabel(i, self._translations.tr("menu_manage"))
            elif "보기" in label or "View" in label:
                menubar.SetMenuLabel(i, self._translations.tr("menu_view"))
            elif "설정" in label or "Settings" in label:
                menubar.SetMenuLabel(i, self._translations.tr("menu_settings"))
            elif "도움말" in label or "Help" in label:
                menubar.SetMenuLabel(i, self._translations.tr("menu_help"))

            # 메뉴 항목 업데이트
            self._update_menu_items(menu)

    def _update_menu_items(self, menu):
        """메뉴 항목 텍스트 및 도움말 업데이트"""
        if not menu:
            return

        tr = self._translations.tr

        # 메뉴 항목 순회
        for item in menu.GetMenuItems():
            if item.IsSeparator():
                continue

            label = item.GetItemLabelText()

            # 파일 메뉴 항목
            if "새로 만들기" in label or "New" in label:
                item.SetItemLabel(tr("action_new"))
                item.SetHelp(tr("action_new_tooltip"))
            elif "열기" in label or "Open" in label:
                if "이미지 시퀀스" in label or "Image Sequence" in label:
                    item.SetItemLabel(tr("action_open_sequence"))
                    item.SetHelp(tr("action_open_sequence_tooltip"))
                else:
                    item.SetItemLabel(tr("action_open"))
                    item.SetHelp(tr("action_open_tooltip"))
            elif "저장" in label or "Save" in label:
                if "다른 이름" in label or "As" in label:
                    item.SetItemLabel(tr("action_save_as"))
                    item.SetHelp(tr("action_save_as_tooltip"))
                else:
                    item.SetItemLabel(tr("action_save"))
                    item.SetHelp(tr("action_save_tooltip"))
            elif "종료" in label or "Exit" in label:
                item.SetItemLabel(tr("action_exit"))
                item.SetHelp(tr("action_exit_tooltip"))

            # 편집 메뉴 항목
            elif "실행 취소" in label or "Undo" in label:
                item.SetItemLabel(tr("action_undo"))
            elif "다시 실행" in label or "Redo" in label:
                item.SetItemLabel(tr("action_redo"))
            elif "모두 선택" in label or "Select All" in label:
                item.SetItemLabel(tr("action_select_all"))
                item.SetHelp(tr("action_select_all_tooltip"))
            elif "삭제" in label or "Delete" in label:
                item.SetItemLabel(tr("action_delete"))
                item.SetHelp(tr("action_delete_tooltip"))
            elif "복제" in label or "Duplicate" in label:
                item.SetItemLabel(tr("action_duplicate"))
                item.SetHelp(tr("action_duplicate_tooltip"))

            # 관리 메뉴 항목
            elif "중복 프레임" in label or "Remove Duplicate" in label:
                item.SetItemLabel(tr("action_remove_dup"))
                item.SetHelp(tr("action_remove_dup_tooltip"))
            elif "모자이크" in label or "Mosaic" in label:
                item.SetItemLabel(tr("action_mosaic"))
                item.SetHelp(tr("action_mosaic_tooltip"))
            elif "말풍선" in label or "Speech Bubble" in label:
                item.SetItemLabel(tr("action_speech_bubble"))
                item.SetHelp(tr("action_speech_bubble_tooltip"))
            elif "워터마크" in label or "Watermark" in label:
                item.SetItemLabel(tr("action_watermark"))
                item.SetHelp(tr("action_watermark_tooltip"))
            elif "분할 저장" in label or "Split" in label:
                item.SetItemLabel(tr("action_split_gif"))
                item.SetHelp(tr("action_split_gif_tooltip"))
            elif "병합" in label or "Merge" in label:
                item.SetItemLabel(tr("action_merge_gif"))
                item.SetHelp(tr("action_merge_gif_tooltip"))
            elif "삽입" in label or "Insert" in label:
                item.SetItemLabel(tr("action_insert_gif"))
                item.SetHelp(tr("action_insert_gif_tooltip"))

            # 설정 메뉴 항목
            elif "GPU 가속" in label or "GPU Accel" in label:
                item.SetItemLabel(tr("action_gpu"))
                if gpu_utils.is_gpu_available():
                    gpu_info = gpu_utils.get_gpu_info()
                    item.SetHelp(tr("action_gpu_tooltip_available",
                        name=gpu_info.get('name', 'Unknown'),
                        memory=gpu_info.get('memory', 0)))
                else:
                    item.SetHelp(tr("action_gpu_tooltip_unavailable"))
            elif "GPU 정보" in label or "GPU Info" in label:
                item.SetItemLabel(tr("action_gpu_info"))
                item.SetHelp(tr("action_gpu_info_tooltip"))

            # 서브메뉴 처리
            if item.IsSubMenu():
                submenu = item.GetSubMenu()
                self._update_menu_items(submenu)

    def _update_inline_toolbar_texts(self):
        """인라인 툴바 텍스트 업데이트"""
        toolbars = [
            self._speed_toolbar,
            self._resize_toolbar,
            self._effects_toolbar,
            self._text_toolbar,
            self._rotate_toolbar,
            self._sticker_toolbar,
            self._crop_toolbar,
            self._mosaic_toolbar,
            self._speech_bubble_toolbar,
            self._watermark_toolbar,
            self._reduce_toolbar,
            self._pencil_toolbar,
        ]

        for toolbar in toolbars:
            if toolbar and hasattr(toolbar, 'update_texts'):
                try:
                    toolbar.update_texts(self._translations)
                except Exception as e:
                    self._logger.error(f"인라인 툴바 텍스트 업데이트 오류: {e}", exc_info=True)

    # ==================== GIF 조작 콜백 메서드들 ====================

    def _on_split_gif_finished(self, result):
        """분할 GIF 저장 완료"""
        if hasattr(self, '_split_progress') and self._split_progress:
            self._split_progress.Destroy()
            self._split_progress = None

        file_path = getattr(self, '_split_file_path', None)
        frame_count = getattr(self, '_split_frame_count', 0)

        if not result.success:
            wx.MessageBox(
                self._translations.tr("msg_split_failed_body", e=result.error_message),
                self._translations.tr("msg_error"),
                wx.OK | wx.ICON_ERROR
            )
            return

        if file_path:
            wx.MessageBox(
                self._translations.tr("msg_split_saved_body", count=frame_count, path=file_path),
                self._translations.tr("msg_split_done_title"),
                wx.OK | wx.ICON_INFORMATION
            )

    def _on_split_gif_error(self, error_msg, traceback):
        """분할 GIF 저장 에러"""
        if hasattr(self, '_split_progress') and self._split_progress:
            self._split_progress.Destroy()
            self._split_progress = None
        wx.MessageBox(
            self._translations.tr("msg_split_failed_body", e=error_msg),
            self._translations.tr("msg_error"),
            wx.OK | wx.ICON_ERROR
        )

    def _on_merge_gif_finished(self, result, file_path, progress):
        """GIF 병합 완료 (Undo 지원)"""
        if progress:
            progress.Destroy()

        if not result.success:
            wx.MessageBox(
                self._translations.tr("msg_gif_open_failed_body", e=result.error_message),
                self._translations.tr("msg_error"),
                wx.OK | wx.ICON_ERROR
            )
            return

        try:
            # Undo 등록
            old_frames = self._frames.clone()
            memory_usage = old_frames.get_memory_usage()

            # 프레임 추가
            added_count = 0
            frames_to_add = []
            for frame in result.frames:
                from ..core import Frame
                new_frame = Frame(frame.image.copy(), frame.delay_ms)
                frames_to_add.append(new_frame)
                added_count += 1

            def execute():
                try:
                    for new_frame in frames_to_add:
                        self._frames.add_frame(new_frame)
                    self._refresh_all()
                except Exception as e:
                    wx.MessageBox(
                        self._translations.tr("msg_merge_error") + f"\n{e}",
                        self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR)
                    raise

            def undo():
                try:
                    self._frames = old_frames
                    self._refresh_all()
                except Exception as e:
                    wx.MessageBox(
                        self._translations.tr("msg_undo_error", e=e),
                        self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR)
                    raise

            self._undo_manager.execute_lambda(f"GIF 병합 ({added_count}개 프레임)", execute, undo, memory_usage)
            self._is_modified = True
            self._last_directory = str(Path(file_path).parent)
            self._settings.Write("last_directory", self._last_directory)
            self._refresh_all()

            wx.MessageBox(
                self._translations.tr("msg_merge_frames_done", count=added_count, total=self._frames.frame_count),
                self._translations.tr("msg_merge_done_title"),
                wx.OK | wx.ICON_INFORMATION
            )
        except MemoryError:
            wx.MessageBox(
                self._translations.tr("msg_out_of_memory"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
        except Exception as e:
            wx.MessageBox(
                self._translations.tr("msg_merge_error") + f"\n{e}",
                self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR)

    def _on_merge_gif_error(self, error_msg, progress):
        """GIF 병합 에러"""
        if progress:
            progress.Destroy()
        wx.MessageBox(
            self._translations.tr("msg_load_gif_failed", e=error_msg),
            self._translations.tr("msg_error"),
            wx.OK | wx.ICON_ERROR
        )

    def _on_insert_gif_finished(self, result, file_path, insert_index, progress):
        """GIF 삽입 완료 (Undo 지원)"""
        if progress:
            progress.Destroy()

        if not result.success:
            wx.MessageBox(
                self._translations.tr("msg_gif_open_failed_body", e=result.error_message),
                self._translations.tr("msg_error"),
                wx.OK | wx.ICON_ERROR
            )
            return

        try:
            # Undo 등록
            old_frames = self._frames.clone()
            memory_usage = old_frames.get_memory_usage()

            # 현재 위치에 프레임 삽입
            added_count = 0
            frames_to_insert = []
            for frame in result.frames:
                from ..core import Frame
                new_frame = Frame(frame.image.copy(), frame.delay_ms)
                frames_to_insert.append(new_frame)
                added_count += 1

            def execute():
                try:
                    for i, new_frame in enumerate(frames_to_insert):
                        self._frames.insert_frame(insert_index + i, new_frame)
                    self._refresh_all()
                except Exception as e:
                    wx.MessageBox(
                        self._translations.tr("msg_insert_error") + f"\n{e}",
                        self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR)
                    raise

            def undo():
                try:
                    self._frames = old_frames
                    self._refresh_all()
                except Exception as e:
                    wx.MessageBox(
                        self._translations.tr("msg_undo_error", e=e),
                        self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR)
                    raise

            self._undo_manager.execute_lambda(f"GIF 삽입 ({added_count}개 프레임)", execute, undo, memory_usage)
            self._is_modified = True
            self._last_directory = str(Path(file_path).parent)
            self._settings.Write("last_directory", self._last_directory)
            self._refresh_all()

            wx.MessageBox(
                self._translations.tr(
                    "msg_insert_frames_done",
                    count=added_count, pos=insert_index + 1, total=self._frames.frame_count),
                self._translations.tr("msg_insert_done_title"),
                wx.OK | wx.ICON_INFORMATION
            )
        except MemoryError:
            wx.MessageBox(
                self._translations.tr("msg_out_of_memory"),
                self._translations.tr("common_warning"), wx.OK | wx.ICON_WARNING)
        except Exception as e:
            wx.MessageBox(
                self._translations.tr("msg_insert_error") + f"\n{e}",
                self._translations.tr("msg_error"), wx.OK | wx.ICON_ERROR)

    def _on_insert_gif_error(self, error_msg, progress):
        """GIF 삽입 에러"""
        if progress:
            progress.Destroy()
        wx.MessageBox(
            self._translations.tr("msg_load_gif_failed", e=error_msg),
            self._translations.tr("msg_error"),
            wx.OK | wx.ICON_ERROR
        )
