"""
PropertiesPanel - 속성 패널 (wxPython 버전)
"""
import wx
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main_window import MainWindow
    from ..utils.translations import Translations

try:
    from .style_constants_wx import Colors, Spacing, apply_panel_style, apply_spin_ctrl_style, ThemedPanel
except ImportError:
    Colors = None
    Spacing = None
    apply_panel_style = lambda p: None
    apply_spin_ctrl_style = lambda s: None
    ThemedPanel = wx.Panel


class PropertiesPanel(ThemedPanel):
    """속성 편집 패널 (wxPython)"""

    def __init__(self, main_window: 'MainWindow'):
        super().__init__(main_window, bg_color=Colors.BG_SECONDARY if Colors else None)
        self._main_window = main_window
        self._updating = False

        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self):
        """UI 설정"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 번역 시스템 가져오기
        translations = getattr(self._main_window, '_translations', None)

        # === 프레임 정보 그룹 ===
        frame_group_title = translations.tr("panel_frame_info") if translations else "Frame Info"
        frame_box = wx.StaticBox(self, label=frame_group_title)
        frame_sizer = wx.StaticBoxSizer(frame_box, wx.VERTICAL)

        # Frame: -/-
        frame_text = translations.tr("panel_frame") if translations else "Frame: -/-"
        self._frame_label = wx.StaticText(self, label=frame_text)
        frame_sizer.Add(self._frame_label, 0, wx.ALL | wx.EXPAND, 5)

        # Size: -x-
        size_text = translations.tr("panel_size") if translations else "Size: -x-"
        self._size_label = wx.StaticText(self, label=size_text)
        frame_sizer.Add(self._size_label, 0, wx.ALL | wx.EXPAND, 5)

        main_sizer.Add(frame_sizer, 0, wx.ALL | wx.EXPAND, 10)

        # === 타이밍 그룹 ===
        timing_group_title = translations.tr("panel_timing") if translations else "Timing"
        timing_box = wx.StaticBox(self, label=timing_group_title)
        timing_sizer = wx.StaticBoxSizer(timing_box, wx.VERTICAL)

        # Delay 입력
        delay_row = wx.BoxSizer(wx.HORIZONTAL)

        delay_label_text = translations.tr("panel_delay") if translations else "Delay:"
        delay_label = wx.StaticText(self, label=delay_label_text)
        delay_row.Add(delay_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self._delay_spin = wx.SpinCtrl(self, min=10, max=10000, initial=100)
        self._delay_spin.Bind(wx.EVT_SPINCTRL, self._on_delay_changed)
        self._delay_spin.Bind(wx.EVT_TEXT, self._on_delay_changed)  # 텍스트 입력도 감지
        delay_row.Add(self._delay_spin, 1, wx.EXPAND)

        delay_ms_label = wx.StaticText(self, label=" ms")
        delay_row.Add(delay_ms_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)

        timing_sizer.Add(delay_row, 0, wx.ALL | wx.EXPAND, 5)

        main_sizer.Add(timing_sizer, 0, wx.ALL | wx.EXPAND, 10)

        # === 컬렉션 정보 그룹 ===
        collection_group_title = translations.tr("panel_collection") if translations else "Collection"
        collection_box = wx.StaticBox(self, label=collection_group_title)
        collection_sizer = wx.StaticBoxSizer(collection_box, wx.VERTICAL)

        # Total: 0 frames
        total_text = translations.tr("panel_total_frames") if translations else "Total: 0 frames"
        self._total_frames_label = wx.StaticText(self, label=total_text)
        collection_sizer.Add(self._total_frames_label, 0, wx.ALL | wx.EXPAND, 5)

        # Duration: 0.0s
        duration_text = translations.tr("panel_duration") if translations else "Duration: 0.0s"
        self._duration_label = wx.StaticText(self, label=duration_text)
        collection_sizer.Add(self._duration_label, 0, wx.ALL | wx.EXPAND, 5)

        main_sizer.Add(collection_sizer, 0, wx.ALL | wx.EXPAND, 10)

        # 아래 여백
        main_sizer.AddStretchSpacer()

        self.SetSizer(main_sizer)

        # 참조 저장
        self._frame_box = frame_box
        self._timing_box = timing_box
        self._collection_box = collection_box

    def _apply_styling(self):
        """다크 테마 스타일 적용"""
        if Colors:
            self.SetBackgroundColour(Colors.BG_SECONDARY)
            self.SetForegroundColour(Colors.TEXT_PRIMARY)

            # StaticBox (GroupBox) 스타일
            for box in [self._frame_box, self._timing_box, self._collection_box]:
                box.SetForegroundColour(Colors.TEXT_SECONDARY)

            # Labels
            for label in [self._frame_label, self._size_label, self._total_frames_label, self._duration_label]:
                label.SetForegroundColour(Colors.TEXT_SECONDARY)

            # SpinCtrl
            if apply_spin_ctrl_style:
                apply_spin_ctrl_style(self._delay_spin)
            else:
                self._delay_spin.SetBackgroundColour(Colors.BG_TERTIARY)
                self._delay_spin.SetForegroundColour(Colors.TEXT_PRIMARY)

    def update_properties(self):
        """속성 업데이트"""
        frames = getattr(self._main_window, 'frames', None)
        if not frames:
            return

        translations = getattr(self._main_window, '_translations', None)

        if getattr(frames, 'is_empty', True):
            frame_text = translations.tr("panel_frame") if translations else "Frame: -/-"
            self._frame_label.SetLabel(frame_text)

            size_text = translations.tr("panel_size") if translations else "Size: -x-"
            self._size_label.SetLabel(size_text)

            self._updating = True
            self._delay_spin.SetValue(100)
            self._updating = False

            total_text = translations.tr("panel_total_frames") if translations else "Total: 0 frames"
            self._total_frames_label.SetLabel(total_text)

            duration_text = translations.tr("panel_duration") if translations else "Duration: 0.0s"
            self._duration_label.SetLabel(duration_text)
            return

        # 프레임 정보
        current_index = getattr(frames, 'current_index', 0)
        frame_count = getattr(frames, 'frame_count', 0)
        width = getattr(frames, 'width', 0)
        height = getattr(frames, 'height', 0)

        if translations:
            frame_label = translations.tr("panel_frame")
            frame_label = frame_label.replace("-/-", f"{current_index + 1}/{frame_count}")
            self._frame_label.SetLabel(frame_label)

            size_label = translations.tr("panel_size")
            size_label = size_label.replace("-x-", f"{width}x{height}")
            self._size_label.SetLabel(size_label)
        else:
            self._frame_label.SetLabel(f"Frame: {current_index + 1}/{frame_count}")
            self._size_label.SetLabel(f"Size: {width}x{height}")

        # 딜레이
        frame = getattr(frames, 'current_frame', None)
        if frame:
            delay_ms = getattr(frame, 'delay_ms', 100)
            self._updating = True
            self._delay_spin.SetValue(delay_ms)
            self._updating = False

        # 컬렉션 정보
        total_duration = getattr(frames, 'total_duration', 0)
        if translations:
            total_label = translations.tr("panel_total_frames")
            # {0} 플레이스홀더 또는 리터럴 "0" 치환 (첫 번째 매치만)
            total_label = total_label.replace("{0}", str(frame_count), 1)
            if "{0}" not in translations.tr("panel_total_frames"):
                total_label = translations.tr("panel_total_frames").replace("0", str(frame_count), 1)
            self._total_frames_label.SetLabel(total_label)

            duration = total_duration / 1000.0
            duration_label = translations.tr("panel_duration")
            duration_label = duration_label.replace("{0}", f"{duration:.1f}", 1)
            if "{0}" not in translations.tr("panel_duration"):
                duration_label = translations.tr("panel_duration").replace("0.0", f"{duration:.1f}", 1)
            self._duration_label.SetLabel(duration_label)
        else:
            self._total_frames_label.SetLabel(f"Total: {frame_count} frames")
            duration = total_duration / 1000.0
            self._duration_label.SetLabel(f"Duration: {duration:.1f}s")

        # 레이아웃 갱신
        self.Layout()

    def update_texts(self, translations: 'Translations'):
        """텍스트 업데이트"""
        self._frame_box.SetLabel(translations.tr("panel_frame_info"))
        self._timing_box.SetLabel(translations.tr("panel_timing"))
        self._collection_box.SetLabel(translations.tr("panel_collection"))

        # 라벨 업데이트는 update_properties에서 처리됨
        self.update_properties()

    def _on_delay_changed(self, event):
        """딜레이 변경 콜백"""
        if self._updating:
            return

        frames = getattr(self._main_window, 'frames', None)
        if not frames:
            return

        frame = getattr(frames, 'current_frame', None)
        if frame:
            value = self._delay_spin.GetValue()
            frame.delay_ms = value

            if hasattr(self._main_window, '_is_modified'):
                self._main_window._is_modified = True
            if hasattr(self._main_window, '_update_info_bar'):
                self._main_window._update_info_bar()
