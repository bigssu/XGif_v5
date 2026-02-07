"""
의존성 설치 다이얼로그
3버튼 모달 (설치/대안/취소) + 재검사 다이얼로그 + 설치 흐름 헬퍼
Windows 11 Dark Theme 스타일
"""

import logging
import wx

from ui.constants import THEME_MID, get_ui_font, FONT_SIZE_DEFAULT, FONT_SIZE_LABEL
from ui.i18n import tr
from ui.capture_control_bar import FlatButton
from core.dependency_checker import DependencyState, DependencyStatus

logger = logging.getLogger(__name__)

# 커스텀 반환 ID
ID_INSTALL = wx.NewIdRef()
ID_DISABLE = wx.NewIdRef()
ID_CANCEL_DEP = wx.NewIdRef()


class DependencyInstallDialog(wx.Dialog):
    """3버튼 의존성 설치 모달 다이얼로그"""

    def __init__(self, parent, dep_status, feature_description,
                 disable_label=None, show_dont_ask=True):
        """
        Args:
            parent: 부모 윈도우
            dep_status: DependencyStatus
            feature_description: 기능 설명 메시지
            disable_label: 대안 버튼 텍스트 (None이면 숨김)
            show_dont_ask: "다시 묻지 않기" 체크박스 표시 여부
        """
        title = tr('dep_dialog_title')
        wx.Dialog.__init__(self, parent, title=title, size=(460, 300),
                          style=wx.DEFAULT_DIALOG_STYLE)
        self.dep_status = dep_status
        self.result_id = ID_CANCEL_DEP
        self.dont_ask_again = False

        self.SetBackgroundColour(wx.Colour(*THEME_MID.BG_PANEL))
        self._build_ui(feature_description, disable_label, show_dont_ask)
        self.CenterOnParent()

    def _build_ui(self, feature_description, disable_label, show_dont_ask):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # 제목 (의존성 이름)
        name_label = wx.StaticText(self, label=self.dep_status.name)
        name_label.SetFont(get_ui_font(14, bold=True))
        name_label.SetForegroundColour(wx.Colour(*THEME_MID.FG_TEXT))
        sizer.Add(name_label, 0, wx.ALL, 16)

        # 상태
        state = self.dep_status.state
        if state == DependencyState.MISSING:
            state_text = tr('dep_state_missing')
            state_color = (239, 68, 68)
        elif state == DependencyState.VERSION_LOW:
            state_text = tr('dep_state_version_low').format(self.dep_status.installed_version)
            state_color = (245, 158, 11)
        elif state == DependencyState.ERROR:
            state_text = tr('dep_state_error')
            state_color = (239, 68, 68)
        else:
            state_text = tr('dep_state_installed')
            state_color = (34, 197, 94)

        state_label = wx.StaticText(self, label=state_text)
        state_label.SetForegroundColour(wx.Colour(*state_color))
        state_label.SetFont(get_ui_font(FONT_SIZE_DEFAULT, bold=True))
        sizer.Add(state_label, 0, wx.LEFT | wx.RIGHT, 16)

        sizer.Add((0, 8))

        # 설명 텍스트
        desc = wx.StaticText(self, label=feature_description)
        desc.SetForegroundColour(wx.Colour(*THEME_MID.FG_TEXT_SECONDARY))
        desc.SetFont(get_ui_font(FONT_SIZE_DEFAULT))
        desc.Wrap(420)
        sizer.Add(desc, 0, wx.LEFT | wx.RIGHT, 16)

        sizer.AddStretchSpacer()

        # "다시 묻지 않기" 체크박스
        if show_dont_ask:
            self._dont_ask_cb = wx.CheckBox(self, label=tr('dep_dont_ask_again'))
            self._dont_ask_cb.SetForegroundColour(wx.Colour(*THEME_MID.FG_TEXT_SECONDARY))
            sizer.Add(self._dont_ask_cb, 0, wx.LEFT | wx.BOTTOM, 16)
        else:
            self._dont_ask_cb = None

        # 버튼 행
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 설치/다운로드 버튼 (Accent)
        install_label = tr('dep_download_btn') if self.dep_status.name == "FFmpeg" else tr('dep_install_btn')
        self.install_btn = FlatButton(self, label=install_label, size=(110, 32),
                                       bg_color=THEME_MID.ACCENT,
                                       fg_color=(255, 255, 255),
                                       hover_color=THEME_MID.ACCENT_HOVER,
                                       pressed_color=THEME_MID.ACCENT_PRESSED)
        self.install_btn.Bind(wx.EVT_BUTTON, self._on_install)
        btn_sizer.Add(self.install_btn, 0, wx.RIGHT, 8)

        # 대안 버튼
        if disable_label:
            self.disable_btn = FlatButton(self, label=disable_label, size=(140, 32),
                                           bg_color=THEME_MID.BG_BUTTON,
                                           fg_color=THEME_MID.FG_TEXT,
                                           hover_color=THEME_MID.BG_BUTTON_HOVER)
            self.disable_btn.Bind(wx.EVT_BUTTON, self._on_disable)
            btn_sizer.Add(self.disable_btn, 0, wx.RIGHT, 8)

        # 취소 버튼
        self.cancel_btn = FlatButton(self, label=tr('cancel'), size=(80, 32),
                                      bg_color=THEME_MID.BG_BUTTON,
                                      fg_color=THEME_MID.FG_TEXT,
                                      hover_color=THEME_MID.BG_BUTTON_HOVER)
        self.cancel_btn.Bind(wx.EVT_BUTTON, self._on_cancel)
        btn_sizer.Add(self.cancel_btn, 0)

        sizer.Add(btn_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 16)
        self.SetSizer(sizer)

    def _on_install(self, event):
        self.dont_ask_again = self._dont_ask_cb.GetValue() if self._dont_ask_cb else False
        self.result_id = ID_INSTALL
        self.EndModal(ID_INSTALL.GetId())

    def _on_disable(self, event):
        self.dont_ask_again = self._dont_ask_cb.GetValue() if self._dont_ask_cb else False
        self.result_id = ID_DISABLE
        self.EndModal(ID_DISABLE.GetId())

    def _on_cancel(self, event):
        self.dont_ask_again = self._dont_ask_cb.GetValue() if self._dont_ask_cb else False
        self.result_id = ID_CANCEL_DEP
        self.EndModal(ID_CANCEL_DEP.GetId())


class DependencyRescanDialog(wx.Dialog):
    """설치 안내 + 재검사 버튼 다이얼로그"""

    def __init__(self, parent, dep_name, guide_text):
        title = tr('dep_rescan_title')
        wx.Dialog.__init__(self, parent, title=title, size=(440, 280),
                          style=wx.DEFAULT_DIALOG_STYLE)
        self.SetBackgroundColour(wx.Colour(*THEME_MID.BG_PANEL))
        self._build_ui(dep_name, guide_text)
        self.CenterOnParent()

    def _build_ui(self, dep_name, guide_text):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # 제목
        name_label = wx.StaticText(self, label=dep_name)
        name_label.SetFont(get_ui_font(14, bold=True))
        name_label.SetForegroundColour(wx.Colour(*THEME_MID.FG_TEXT))
        sizer.Add(name_label, 0, wx.ALL, 16)

        # 안내 텍스트
        guide = wx.StaticText(self, label=guide_text)
        guide.SetForegroundColour(wx.Colour(*THEME_MID.FG_TEXT_SECONDARY))
        guide.SetFont(get_ui_font(FONT_SIZE_DEFAULT))
        guide.Wrap(400)
        sizer.Add(guide, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 16)

        # 버튼 행
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()

        rescan_btn = FlatButton(self, label=tr('dep_rescan_btn'), size=(100, 32),
                                 bg_color=THEME_MID.ACCENT,
                                 fg_color=(255, 255, 255),
                                 hover_color=THEME_MID.ACCENT_HOVER,
                                 pressed_color=THEME_MID.ACCENT_PRESSED)
        rescan_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))
        btn_sizer.Add(rescan_btn, 0, wx.RIGHT, 8)

        close_btn = FlatButton(self, label=tr('dep_close_btn'), size=(80, 32),
                                bg_color=THEME_MID.BG_BUTTON,
                                fg_color=THEME_MID.FG_TEXT,
                                hover_color=THEME_MID.BG_BUTTON_HOVER)
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
        btn_sizer.Add(close_btn, 0)

        sizer.Add(btn_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 16)
        self.SetSizer(sizer)


def show_install_flow(parent, dep_name, dep_status, settings=None):
    """의존성별 설치 흐름 실행

    Args:
        parent: 부모 윈도우
        dep_name: "FFmpeg", "CuPy", "dxcam"
        dep_status: DependencyStatus
        settings: configparser (skip 플래그 저장용)

    Returns:
        True=설치됨/해결됨, False=설치 안 함
    """
    if dep_name == "FFmpeg":
        return _install_ffmpeg(parent, dep_status)
    elif dep_name == "CuPy":
        return _install_cupy(parent, dep_status)
    elif dep_name == "dxcam":
        return _install_dxcam(parent, dep_status)
    return False


def _install_ffmpeg(parent, dep_status):
    """FFmpeg 설치 흐름 — 기존 FFmpegDownloader 재사용"""
    from core.ffmpeg_installer import FFmpegDownloader, FFmpegManager

    if FFmpegManager.is_available():
        return True

    progress = wx.ProgressDialog(
        tr('ffmpeg_install_title'),
        tr('ffmpeg_downloading'),
        maximum=100,
        parent=parent,
        style=wx.PD_APP_MODAL | wx.PD_CAN_ABORT
    )

    result = {'success': False, 'message': '', 'done': False}

    def on_progress(downloaded, total):
        if total > 0:
            percent = int((downloaded / total) * 100)
            dl_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            keep_going, _ = progress.Update(
                percent,
                f"FFmpeg 다운로드 중...\n{dl_mb:.1f} MB / {total_mb:.1f} MB"
            )
            if not keep_going:
                downloader.cancel()

    def on_status(status):
        try:
            progress.Update(progress.GetValue(), status)
        except Exception:
            pass

    def on_finished(success, message):
        result['success'] = success
        result['message'] = message
        result['done'] = True

    downloader = FFmpegDownloader(
        progress_callback=on_progress,
        status_callback=on_status,
        finished_callback=on_finished,
    )
    downloader.start()

    # 완료 대기 (이벤트 루프 유지)
    while not result['done']:
        wx.MilliSleep(100)
        wx.SafeYield(parent, True)

    try:
        progress.Destroy()
    except Exception:
        pass

    if result['success']:
        wx.MessageBox(
            tr('ffmpeg_install_success'),
            tr('install_complete'),
            wx.OK | wx.ICON_INFORMATION
        )
        return True
    else:
        # 실패 시 브라우저 열기 제안
        dlg = wx.MessageDialog(
            parent,
            tr('dep_ffmpeg_download_failed'),
            tr('install_failed'),
            wx.YES_NO | wx.ICON_WARNING
        )
        if dlg.ShowModal() == wx.ID_YES:
            import webbrowser
            webbrowser.open(tr('dep_ffmpeg_manual_url'))
        dlg.Destroy()
        return False


def _install_cupy(parent, dep_status):
    """CuPy 설치 흐름 — 브라우저 + 재검사"""
    import webbrowser
    webbrowser.open("https://docs.cupy.dev/en/stable/install.html")

    dlg = DependencyRescanDialog(parent, "CuPy", tr('dep_cupy_install_guide'))
    while True:
        ret = dlg.ShowModal()
        if ret == wx.ID_OK:
            from core.dependency_checker import check_cupy
            status = check_cupy()
            if status.state == DependencyState.INSTALLED:
                dlg.Destroy()
                wx.MessageBox(
                    tr('dep_cupy_installed_ok'),
                    tr('info'),
                    wx.OK | wx.ICON_INFORMATION
                )
                return True
            else:
                wx.MessageBox(
                    tr('dep_cupy_still_missing'),
                    tr('warning'),
                    wx.OK | wx.ICON_WARNING
                )
        else:
            break
    dlg.Destroy()
    return False


def _install_dxcam(parent, dep_status):
    """dxcam 설치 흐름 — 논블로킹 pip install (wx.CallAfter 패턴)"""
    import sys
    import subprocess
    import threading

    if getattr(sys, 'frozen', False):
        wx.MessageBox(
            "패키징된 환경에서는 pip install을 실행할 수 없습니다.\n"
            "개발 환경에서 dxcam을 설치한 후 다시 빌드해주세요.",
            tr('warning'), wx.OK | wx.ICON_WARNING
        )
        return False

    # 진행 다이얼로그 (취소 가능)
    progress = wx.ProgressDialog(
        tr('dxcam_installing'),
        "dxcam 패키지 설치 중...",
        maximum=100,
        parent=parent,
        style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
    )
    progress.Pulse()

    result = {'success': False, 'message': '', 'done': False}

    def do_install():
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", "dxcam"],
                capture_output=True, text=True, timeout=120
            )
            result['success'] = proc.returncode == 0
            result['message'] = proc.stdout if result['success'] else proc.stderr
        except Exception as e:
            result['success'] = False
            result['message'] = str(e)
        result['done'] = True
        wx.CallAfter(_on_install_done, result, progress)

    def _on_install_done(res, dlg):
        try:
            dlg.Destroy()
        except Exception:
            pass
        if res['success']:
            wx.MessageBox(
                tr('dxcam_install_success'),
                tr('install_complete'),
                wx.OK | wx.ICON_INFORMATION
            )
        else:
            wx.MessageBox(
                tr('dxcam_install_failed').format(res['message'][:300]),
                tr('install_failed'),
                wx.OK | wx.ICON_WARNING
            )

    threading.Thread(target=do_install, daemon=True).start()
    return result.get('success', False)
