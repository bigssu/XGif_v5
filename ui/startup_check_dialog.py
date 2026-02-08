"""
첫 실행 환경 진단 다이얼로그
의존성 상태를 리스트로 표시하고 개별 설치 버튼 제공
Windows 11 Dark Theme 스타일
"""

import logging
import wx

from ui.theme import Colors, Fonts
from ui.i18n import tr
from ui.capture_control_bar import FlatButton
from core.dependency_checker import DependencyState, DependencyStatus

logger = logging.getLogger(__name__)


# 의존성별 설명 키와 대안 라벨 매핑
_DEP_INFO = {
    "FFmpeg": {
        "desc_key": "dep_ffmpeg_desc",
        "disable_key": "dep_use_gif_instead",
    },
    "CuPy": {
        "desc_key": "dep_cupy_desc",
        "disable_key": "dep_use_cpu_instead",
    },
    "dxcam": {
        "desc_key": "dep_dxcam_desc",
        "disable_key": "dep_use_gdi_instead",
    },
}


class StartupCheckDialog(wx.Dialog):
    """첫 실행 환경 진단 다이얼로그"""

    def __init__(self, parent, dep_results):
        """
        Args:
            parent: 부모 윈도우
            dep_results: list[DependencyStatus] — check_all() 결과
        """
        title = tr('dep_startup_title')
        wx.Dialog.__init__(self, parent, title=title, size=(500, 380),
                          style=wx.DEFAULT_DIALOG_STYLE)
        self.SetBackgroundColour(Colors.BG_PANEL)
        self.dep_results = dep_results
        self._installed = {}  # name -> bool (설치 흐름 후 갱신)
        self._build_ui()
        self.CenterOnParent()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # 설명
        desc = wx.StaticText(self, label=tr('dep_startup_desc'))
        desc.SetForegroundColour(Colors.TEXT_SECONDARY)
        desc.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
        desc.Wrap(460)
        sizer.Add(desc, 0, wx.ALL, 16)

        # 구분선
        line = wx.Panel(self, size=(-1, 1))
        line.SetBackgroundColour(Colors.BORDER)
        sizer.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 16)

        # 의존성 항목들
        self._item_panels = {}
        for dep in self.dep_results:
            row = self._create_dep_row(dep)
            sizer.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 16)

        sizer.AddStretchSpacer()

        # 하단 버튼
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()

        skip_btn = FlatButton(self, label=tr('dep_skip_btn'), size=(100, 32),
                               bg_color=Colors.BG_TERTIARY.Get()[:3],
                               fg_color=Colors.TEXT_PRIMARY.Get()[:3],
                               hover_color=Colors.BG_HOVER.Get()[:3])
        skip_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
        btn_sizer.Add(skip_btn, 0)

        sizer.Add(btn_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 16)
        self.SetSizer(sizer)

    def _create_dep_row(self, dep):
        """개별 의존성 행 생성"""
        panel = wx.Panel(self)
        panel.SetBackgroundColour(Colors.BG_PANEL)
        row_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 상태 아이콘
        state = dep.state
        if state == DependencyState.INSTALLED:
            icon_text = "  OK  "
            icon_color = Colors.STATUS_SUCCESS
        elif state == DependencyState.MISSING:
            icon_text = "  --  "
            icon_color = Colors.STATUS_ERROR
        elif state == DependencyState.VERSION_LOW:
            icon_text = "  !!  "
            icon_color = Colors.STATUS_WARNING
        else:
            icon_text = "  ??  "
            icon_color = Colors.STATUS_ERROR

        icon_label = wx.StaticText(panel, label=icon_text)
        icon_label.SetForegroundColour(icon_color)
        icon_label.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT, bold=True))
        row_sizer.Add(icon_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        # 이름 + 설명
        info = _DEP_INFO.get(dep.name, {})
        desc_text = tr(info.get("desc_key", "")) if info.get("desc_key") else dep.name
        name_text = f"{dep.name} — {desc_text}"
        name_label = wx.StaticText(panel, label=name_text)
        name_label.SetForegroundColour(Colors.TEXT_PRIMARY)
        name_label.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
        row_sizer.Add(name_label, 1, wx.ALIGN_CENTER_VERTICAL)

        # 설치 버튼 (미설치/버전낮음/에러 시에만)
        if state != DependencyState.INSTALLED:
            install_btn = FlatButton(panel, label=tr('dep_install_btn'), size=(70, 26),
                                      bg_color=Colors.ACCENT.Get()[:3],
                                      fg_color=Colors.TEXT_PRIMARY.Get()[:3],
                                      hover_color=Colors.ACCENT_HOVER.Get()[:3],
                                      pressed_color=Colors.ACCENT_PRESSED.Get()[:3])
            install_btn.Bind(wx.EVT_BUTTON, lambda e, d=dep, p=panel, il=icon_label, ib=install_btn:
                            self._on_install_clicked(d, p, il, ib))
            row_sizer.Add(install_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)

        panel.SetSizer(row_sizer)
        self._item_panels[dep.name] = panel
        return panel

    def _on_install_clicked(self, dep, panel, icon_label, install_btn):
        """개별 설치 버튼 클릭"""
        from ui.dependency_dialogs import show_install_flow
        success = show_install_flow(self, dep.name, dep)
        if success:
            icon_label.SetLabel("  OK  ")
            icon_label.SetForegroundColour(Colors.STATUS_SUCCESS)
            install_btn.Enable(False)
            self._installed[dep.name] = True
            panel.Layout()
