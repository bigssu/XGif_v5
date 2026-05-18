"""
Editor help and about dialogs.

The editor uses custom wx panels instead of wx.adv.AboutBox so long metadata
and expanded details do not overlap on Windows.
"""
import wx

from core.version import APP_DEVELOPER, APP_LAST_MODIFIED, APP_VERSION, EDITOR_VERSION
from ui.i18n import tr
from ..style_constants_wx import Colors, Fonts, ThemedDialog, apply_button_style


class HelpDialog(ThemedDialog):
    def __init__(self, parent=None):
        super().__init__(
            parent,
            title=tr("help_dialog_title", "XGif Editor 도움말"),
            size=(640, 560),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._wrap_labels = []
        # Per-page label index avoids the O(L·D) parent chain walk that
        # _wrap_visible_labels used to do for every label on every EVT_SIZE.
        self._page_wrap_labels: dict[wx.Window, list] = {}
        # Last-applied wrap width per page (and for the dialog as a whole),
        # so noisy resize events that don't actually change width skip the work.
        self._last_wrap_widths: dict[object, int] = {}
        self._setup_ui()
        self.SetMinSize((560, 480))
        self.Bind(wx.EVT_SIZE, self._on_size)
        self.CenterOnParent()

    def _setup_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        header = wx.Panel(self)
        header.SetBackgroundColour(Colors.RAIL_BG)
        header_sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(header, label="XGif Editor")
        title.SetFont(Fonts.get_font(18, bold=True))
        title.SetForegroundColour(Colors.TEXT_PRIMARY)
        header_sizer.Add(title, 0, wx.LEFT | wx.RIGHT | wx.TOP, 18)

        subtitle = wx.StaticText(
            header,
            label=tr("help_editor_summary", "XGif Editor는 녹화된 GIF를 프레임, 시간, 크기, 효과, 텍스트, 도형, 펜슬 오버레이 단위로 빠르게 수정하는 내장 편집 화면입니다."),
        )
        subtitle.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
        subtitle.SetForegroundColour(Colors.TEXT_SECONDARY)
        header_sizer.Add(subtitle, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 18)
        self._wrap_labels.append((subtitle, 560))

        meta = wx.StaticText(
            header,
            label=(
                f"Editor v{EDITOR_VERSION}  |  App v{APP_VERSION}  |  "
                f"{APP_LAST_MODIFIED}  |  {APP_DEVELOPER}"
            ),
        )
        meta.SetFont(Fonts.get_font(Fonts.SIZE_SMALL, bold=True))
        meta.SetForegroundColour(Colors.VERSION_ACCENT)
        header_sizer.Add(meta, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 18)

        header.SetSizer(header_sizer)
        main_sizer.Add(header, 0, wx.EXPAND | wx.ALL, 10)

        notebook = wx.Notebook(self)
        notebook.SetBackgroundColour(Colors.BG_PRIMARY)
        notebook.SetForegroundColour(Colors.TEXT_PRIMARY)
        notebook.AddPage(self._create_overview_page(notebook), tr("help_tab_overview", "요약"))
        notebook.AddPage(self._create_tools_page(notebook), tr("help_tab_tools", "편집 기능"))
        notebook.AddPage(self._create_shortcuts_page(notebook), tr("help_tab_shortcuts", "단축키"))
        notebook.AddPage(self._create_info_page(notebook), tr("help_tab_info", "정보"))
        main_sizer.Add(notebook, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()
        ok_btn = wx.Button(self, wx.ID_OK, label=tr("common_ok", "확인"))
        apply_button_style(ok_btn, primary=True)
        ok_btn.SetMinSize((86, 32))
        btn_sizer.Add(ok_btn, 0, wx.ALL, 10)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND)

        self.SetSizer(main_sizer)

    def _create_page(self, parent):
        page = wx.ScrolledWindow(parent, style=wx.VSCROLL | wx.BORDER_NONE)
        page.SetBackgroundColour(Colors.BG_PRIMARY)
        page.SetScrollRate(0, 12)
        page.SetSizer(wx.BoxSizer(wx.VERTICAL))
        page.Bind(wx.EVT_SIZE, lambda event, p=page: self._on_page_size(event, p))
        return page

    def _create_overview_page(self, parent):
        page = self._create_page(parent)
        self._add_section(
            page,
            tr("help_sec_app_summary_title", "앱 요약"),
            [
                # help_app_summary는 이 섹션의 body0 역할 (헤더에서도 재사용됨)
                tr("help_app_summary", "XGif는 Windows 화면을 GIF 또는 MP4로 녹화하고, 녹화 결과를 프레임 단위로 다듬어 저장하는 경량 캡처/편집 앱입니다."),
                tr("help_sec_app_summary_body1", "레코더는 캡처 영역, FPS, 해상도, GIF/MP4 출력, GPU 사용 여부를 빠르게 선택하도록 설계되었습니다."),
                tr("help_sec_app_summary_body2", "에디터는 녹화 직후 프레임 삭제, 시간 직접 입력, 텍스트/스티커/펜슬 추가, 크롭/리사이즈/필터 적용, 저장 최적화를 처리합니다."),
            ],
        )
        self._add_section(
            page,
            tr("help_sec_flow_title", "권장 흐름"),
            [
                tr("help_sec_flow_body0", "1. 메인 화면에서 캡처 영역과 출력 형식을 정합니다."),
                tr("help_sec_flow_body1", "2. 녹화 후 편집 버튼으로 에디터를 열어 불필요한 프레임과 시간을 정리합니다."),
                tr("help_sec_flow_body2", "3. 필요한 오버레이나 효과를 적용한 뒤 저장합니다. 재생 중인 프리뷰는 저장을 누르면 자동으로 멈춥니다."),
            ],
        )
        return page

    def _create_tools_page(self, parent):
        page = self._create_page(parent)
        self._add_section(
            page,
            tr("help_sec_frames_title", "프레임과 시간"),
            [
                tr("help_sec_frames_body0", "프레임 목록에서 선택 프레임을 삭제하거나, 시간 필드 안에서 재생 시간을 직접 입력할 수 있습니다."),
                tr("help_sec_frames_body1", "속도 조절은 전체 프레임 또는 선택 프레임 대상으로 적용됩니다."),
                tr("help_sec_frames_body2", "프레임 줄이기는 중복/불필요한 프레임을 정리해 파일 크기를 줄이는 작업에 사용합니다."),
            ],
        )
        self._add_section(
            page,
            tr("help_sec_image_title", "이미지 편집"),
            [
                tr("help_sec_image_body0", "크롭, 리사이즈, 회전, 좌우/상하 반전, 역재생, 요요 재생을 지원합니다."),
                tr("help_sec_image_body1", "필터는 밝기, 대비, 색상, 흐림 등 기본 이미지 보정 작업을 처리합니다."),
                tr("help_sec_image_body2", "미리보기는 적용 전 결과를 확인하기 위한 작업 화면이며, 적용/취소로 원본 보존 여부를 결정합니다."),
            ],
        )
        self._add_section(
            page,
            tr("help_sec_overlay_title", "오버레이"),
            [
                tr("help_sec_overlay_body0", "텍스트 추가는 글꼴, 크기, 색상, 외곽선, 애니메이션, 깜빡임 옵션을 제공합니다."),
                tr("help_sec_overlay_body1", "스티커/도형과 말풍선은 강조 지점을 표시할 때 사용합니다."),
                tr("help_sec_overlay_body2", "펜슬 그리기는 프레임 위에 직접 선을 그리는 주석 도구입니다."),
            ],
        )
        return page

    def _create_shortcuts_page(self, parent):
        page = self._create_page(parent)
        self._add_section(
            page,
            tr("help_sec_sc_file_title", "파일과 재생"),
            [
                tr("help_sec_sc_file_body0", "Ctrl+O    파일 열기"),
                tr("help_sec_sc_file_body1", "Ctrl+S    저장"),
                tr("help_sec_sc_file_body2", "Space     재생 / 일시정지"),
                tr("help_sec_sc_file_body3", "Left/Right 프레임 이동"),
            ],
        )
        self._add_section(
            page,
            tr("help_sec_sc_edit_title", "편집"),
            [
                tr("help_sec_sc_edit_body0", "Ctrl+Z    실행 취소"),
                tr("help_sec_sc_edit_body1", "Ctrl+Y    다시 실행"),
                tr("help_sec_sc_edit_body2", "Ctrl+A    전체 프레임 선택"),
                tr("help_sec_sc_edit_body3", "Delete    선택한 프레임 삭제"),
            ],
        )
        self._add_section(
            page,
            tr("help_sec_sc_tools_title", "도구"),
            [
                tr("help_sec_sc_tools_body0", "T         텍스트 추가"),
                tr("help_sec_sc_tools_body1", "P         펜슬 그리기"),
                tr("help_sec_sc_tools_body2", "C         자르기"),
                tr("help_sec_sc_tools_body3", "R         크기 조절"),
                tr("help_sec_sc_tools_body4", "E         필터/효과"),
            ],
        )
        return page

    def _create_info_page(self, parent):
        page = self._create_page(parent)
        self._add_section(
            page,
            tr("help_sec_product_title", "제품 정보"),
            [
                tr("help_sec_product_body0", "앱 이름: XGif"),
                tr("help_sec_product_body1", "앱 버전: {v}", v=APP_VERSION),
                tr("help_sec_product_body2", "에디터 버전: {v}", v=EDITOR_VERSION),
                tr("help_sec_product_body3", "마지막 수정일: {v}", v=APP_LAST_MODIFIED),
                tr("help_sec_product_body4", "개발자: {v}", v=APP_DEVELOPER),
            ],
        )
        self._add_section(
            page,
            tr("help_sec_design_title", "설계 방향"),
            [
                tr("help_sec_design_body0", "Windows용 wxPython 앱 구조를 유지해 번들 크기 증가를 피했습니다."),
                tr("help_sec_design_body1", "UI는 다크 테마, 통일된 아이콘, 명확한 카드 깊이, 성능에 부담이 적은 레이어 구조를 기준으로 정리했습니다."),
                tr("help_sec_design_body2", "Defender 회피나 Windows 보안 상태 변경 기능은 설치/빌드 흐름에서 제거했습니다."),
            ],
        )
        return page

    def _add_section(self, page, title, lines):
        card = wx.Panel(page)
        card.SetBackgroundColour(Colors.BG_CARD)
        card_sizer = wx.BoxSizer(wx.VERTICAL)

        heading = wx.StaticText(card, label=title)
        heading.SetFont(Fonts.get_font(Fonts.SIZE_MD, bold=True))
        heading.SetForegroundColour(Colors.TEXT_PRIMARY)
        card_sizer.Add(heading, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 14)

        page_labels = self._page_wrap_labels.setdefault(page, [])
        for line in lines:
            label = wx.StaticText(card, label=line)
            label.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
            label.SetForegroundColour(Colors.TEXT_SECONDARY)
            card_sizer.Add(label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 14)
            entry = (label, 500)
            self._wrap_labels.append(entry)
            page_labels.append(entry)

        card_sizer.AddSpacer(14)
        card.SetSizer(card_sizer)
        page.GetSizer().Add(card, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

    def _on_page_size(self, event, page):
        self._wrap_visible_labels(page)
        page.Layout()
        page.FitInside()
        event.Skip()

    def _on_size(self, event):
        self._wrap_all_labels()
        event.Skip()

    def _wrap_visible_labels(self, page):
        width = max(260, page.GetClientSize().GetWidth() - 54)
        if self._last_wrap_widths.get(page) == width:
            return
        self._last_wrap_widths[page] = width
        for label, max_width in self._page_wrap_labels.get(page, ()):
            label.Wrap(min(width, max_width))

    def _wrap_all_labels(self):
        width = max(260, self.GetClientSize().GetWidth() - 80)
        if self._last_wrap_widths.get("__all__") == width:
            return
        self._last_wrap_widths["__all__"] = width
        for label, max_width in self._wrap_labels:
            label.Wrap(min(width, max_width))


class AboutDialog(ThemedDialog):
    def __init__(self, parent=None):
        super().__init__(
            parent,
            title=tr("help_about_title", "XGif Editor 정보"),
            size=(500, 360),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._setup_ui()
        self.SetMinSize((440, 320))
        self.CenterOnParent()

    def _setup_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(self, label="XGif Editor")
        title.SetFont(Fonts.get_font(20, bold=True))
        title.SetForegroundColour(Colors.TEXT_PRIMARY)
        sizer.Add(title, 0, wx.LEFT | wx.RIGHT | wx.TOP, 18)

        summary = wx.StaticText(
            self,
            label=tr("help_editor_summary", "XGif Editor는 녹화된 GIF를 프레임, 시간, 크기, 효과, 텍스트, 도형, 펜슬 오버레이 단위로 빠르게 수정하는 내장 편집 화면입니다."),
        )
        summary.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
        summary.SetForegroundColour(Colors.TEXT_SECONDARY)
        summary.Wrap(440)
        sizer.Add(summary, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 18)

        details = wx.Panel(self)
        details.SetBackgroundColour(Colors.BG_CARD)
        details_sizer = wx.BoxSizer(wx.VERTICAL)
        for line in (
            tr("help_sec_product_body1", "앱 버전: {v}", v=APP_VERSION),
            tr("help_sec_product_body2", "에디터 버전: {v}", v=EDITOR_VERSION),
            tr("help_sec_product_body3", "마지막 수정일: {v}", v=APP_LAST_MODIFIED),
            tr("help_sec_product_body4", "개발자: {v}", v=APP_DEVELOPER),
        ):
            label = wx.StaticText(details, label=line)
            label.SetForegroundColour(Colors.TEXT_SECONDARY)
            label.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
            details_sizer.Add(label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        details_sizer.AddSpacer(12)
        details.SetSizer(details_sizer)
        sizer.Add(details, 0, wx.EXPAND | wx.ALL, 18)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()
        ok_btn = wx.Button(self, wx.ID_OK, label=tr("common_ok", "확인"))
        apply_button_style(ok_btn, primary=True)
        ok_btn.SetMinSize((86, 32))
        btn_sizer.Add(ok_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 18)
        sizer.Add(btn_sizer, 0, wx.EXPAND)

        self.SetSizer(sizer)
