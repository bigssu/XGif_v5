"""
의존성 설치 다이얼로그
3버튼 모달 (설치/대안/취소) + 재검사 다이얼로그 + 설치 흐름 헬퍼
Windows 11 Dark Theme 스타일
"""

import logging
import sys
import wx

from ui.theme import Colors, Fonts, ThemedDialog
from ui.i18n import tr
from ui.capture_control_bar import FlatButton
from core.dependency_checker import DependencyState, DependencyStatus

logger = logging.getLogger(__name__)

# 커스텀 반환 ID
ID_INSTALL = wx.NewIdRef()
ID_DISABLE = wx.NewIdRef()
ID_CANCEL_DEP = wx.NewIdRef()


class DependencyInstallDialog(ThemedDialog):
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
        ThemedDialog.__init__(self, parent, title=title, size=(460, 300),
                          style=wx.DEFAULT_DIALOG_STYLE)
        self.dep_status = dep_status
        self.result_id = ID_CANCEL_DEP
        self.dont_ask_again = False

        self.SetBackgroundColour(Colors.BG_PANEL)
        self._build_ui(feature_description, disable_label, show_dont_ask)
        self.CenterOnParent()

    def _build_ui(self, feature_description, disable_label, show_dont_ask):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # 제목 (의존성 이름)
        name_label = wx.StaticText(self, label=self.dep_status.name)
        name_label.SetFont(Fonts.get_font(Fonts.SIZE_LG, bold=True))
        name_label.SetForegroundColour(Colors.TEXT_PRIMARY)
        sizer.Add(name_label, 0, wx.ALL, 16)

        # 상태
        state = self.dep_status.state
        if state == DependencyState.MISSING:
            state_text = tr('dep_state_missing')
            state_color = Colors.STATUS_ERROR
        elif state == DependencyState.VERSION_LOW:
            state_text = tr('dep_state_version_low').format(self.dep_status.installed_version)
            state_color = Colors.STATUS_WARNING
        elif state == DependencyState.ERROR:
            state_text = tr('dep_state_error')
            state_color = Colors.STATUS_ERROR
        else:
            state_text = tr('dep_state_installed')
            state_color = Colors.STATUS_SUCCESS

        state_label = wx.StaticText(self, label=state_text)
        state_label.SetForegroundColour(state_color)
        state_label.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT, bold=True))
        sizer.Add(state_label, 0, wx.LEFT | wx.RIGHT, 16)

        sizer.Add((0, 8))

        # 설명 텍스트
        desc = wx.StaticText(self, label=feature_description)
        desc.SetForegroundColour(Colors.TEXT_SECONDARY)
        desc.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
        desc.Wrap(420)
        sizer.Add(desc, 0, wx.LEFT | wx.RIGHT, 16)

        sizer.AddStretchSpacer()

        # "다시 묻지 않기" 체크박스
        if show_dont_ask:
            self._dont_ask_cb = wx.CheckBox(self, label=tr('dep_dont_ask_again'))
            self._dont_ask_cb.SetForegroundColour(Colors.TEXT_SECONDARY)
            sizer.Add(self._dont_ask_cb, 0, wx.LEFT | wx.BOTTOM, 16)
        else:
            self._dont_ask_cb = None

        # 버튼 행
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 설치/다운로드 버튼 (Accent)
        install_label = tr('dep_download_btn') if self.dep_status.name == "FFmpeg" else tr('dep_install_btn')
        self.install_btn = FlatButton(self, label=install_label, size=(110, 32),
                                       bg_color=Colors.ACCENT.Get()[:3],
                                       fg_color=Colors.TEXT_PRIMARY.Get()[:3],
                                       hover_color=Colors.ACCENT_HOVER.Get()[:3],
                                       pressed_color=Colors.ACCENT_PRESSED.Get()[:3])
        self.install_btn.Bind(wx.EVT_BUTTON, self._on_install)
        btn_sizer.Add(self.install_btn, 0, wx.RIGHT, 8)

        # 대안 버튼
        if disable_label:
            self.disable_btn = FlatButton(self, label=disable_label, size=(140, 32),
                                           bg_color=Colors.BG_TERTIARY.Get()[:3],
                                           fg_color=Colors.TEXT_PRIMARY.Get()[:3],
                                           hover_color=Colors.BG_HOVER.Get()[:3])
            self.disable_btn.Bind(wx.EVT_BUTTON, self._on_disable)
            btn_sizer.Add(self.disable_btn, 0, wx.RIGHT, 8)

        # 취소 버튼
        self.cancel_btn = FlatButton(self, label=tr('cancel'), size=(80, 32),
                                      bg_color=Colors.BG_TERTIARY.Get()[:3],
                                      fg_color=Colors.TEXT_PRIMARY.Get()[:3],
                                      hover_color=Colors.BG_HOVER.Get()[:3])
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


class DependencyRescanDialog(ThemedDialog):
    """설치 안내 + 재검사 버튼 다이얼로그"""

    def __init__(self, parent, dep_name, guide_text):
        title = tr('dep_rescan_title')
        ThemedDialog.__init__(self, parent, title=title, size=(440, 280),
                          style=wx.DEFAULT_DIALOG_STYLE)
        self.SetBackgroundColour(Colors.BG_PANEL)
        self._build_ui(dep_name, guide_text)
        self.CenterOnParent()

    def _build_ui(self, dep_name, guide_text):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # 제목
        name_label = wx.StaticText(self, label=dep_name)
        name_label.SetFont(Fonts.get_font(Fonts.SIZE_LG, bold=True))
        name_label.SetForegroundColour(Colors.TEXT_PRIMARY)
        sizer.Add(name_label, 0, wx.ALL, 16)

        # 안내 텍스트
        guide = wx.StaticText(self, label=guide_text)
        guide.SetForegroundColour(Colors.TEXT_SECONDARY)
        guide.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
        guide.Wrap(400)
        sizer.Add(guide, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 16)

        # 버튼 행
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()

        rescan_btn = FlatButton(self, label=tr('dep_rescan_btn'), size=(100, 32),
                                 bg_color=Colors.ACCENT.Get()[:3],
                                 fg_color=Colors.TEXT_PRIMARY.Get()[:3],
                                 hover_color=Colors.ACCENT_HOVER.Get()[:3],
                                 pressed_color=Colors.ACCENT_PRESSED.Get()[:3])
        rescan_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))
        btn_sizer.Add(rescan_btn, 0, wx.RIGHT, 8)

        close_btn = FlatButton(self, label=tr('dep_close_btn'), size=(80, 32),
                                bg_color=Colors.BG_TERTIARY.Get()[:3],
                                fg_color=Colors.TEXT_PRIMARY.Get()[:3],
                                hover_color=Colors.BG_HOVER.Get()[:3])
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
        btn_sizer.Add(close_btn, 0)

        sizer.Add(btn_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 16)
        self.SetSizer(sizer)


def _detect_nvidia_gpu_name():
    """NVIDIA GPU 이름 감지 (pynvml 사용)"""
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode('utf-8')
        pynvml.nvmlShutdown()
        return name
    except Exception:
        return None


def _detect_cuda_driver_version():
    """CUDA 드라이버 버전 감지 (pynvml 사용)"""
    try:
        import pynvml
        pynvml.nvmlInit()
        try:
            cuda_ver = pynvml.nvmlSystemGetCudaDriverVersion_v2()
        except AttributeError:
            cuda_ver = pynvml.nvmlSystemGetCudaDriverVersion()
        pynvml.nvmlShutdown()
        major = cuda_ver // 1000
        minor = (cuda_ver % 1000) // 10
        return (major, minor)
    except Exception:
        return None


def _get_cupy_package_name():
    """CUDA 드라이버 버전에 맞는 CuPy 패키지명 반환"""
    version = _detect_cuda_driver_version()
    if version is None:
        return "cupy-cuda12x"
    major, _ = version
    if major >= 12:
        return "cupy-cuda12x"
    elif major >= 11:
        return "cupy-cuda11x"
    else:
        return "cupy-cuda12x"


def _has_nvidia_gpu_hardware():
    """NVIDIA GPU 하드웨어 존재 여부 확인"""
    try:
        import pynvml
        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        pynvml.nvmlShutdown()
        return count > 0
    except Exception:
        return False


class CuPyInstallGuideDialog(ThemedDialog):
    """CuPy 설치 가이드 다이얼로그

    NVIDIA GPU 정보, CUDA 드라이버 버전, 설치 명령어를 보여주고
    명령어 복사 및 재검사 기능 제공.
    dev 모드에서는 직접 설치 버튼도 제공.
    """

    def __init__(self, parent):
        title = tr('cupy_guide_title')
        ThemedDialog.__init__(self, parent, title=title, size=(500, 380),
                          style=wx.DEFAULT_DIALOG_STYLE)
        self.SetBackgroundColour(Colors.BG_PANEL)
        self._is_frozen = getattr(sys, 'frozen', False)
        self._package_name = _get_cupy_package_name()
        self._build_ui()
        self.CenterOnParent()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # GPU / CUDA 정보 감지
        gpu_name = _detect_nvidia_gpu_name() or "N/A"
        cuda_ver = _detect_cuda_driver_version()
        cuda_ver_str = f"{cuda_ver[0]}.{cuda_ver[1]}" if cuda_ver else "N/A"

        # 제목
        title_label = wx.StaticText(self, label=tr('cupy_guide_title'))
        title_label.SetFont(Fonts.get_font(Fonts.SIZE_LG, bold=True))
        title_label.SetForegroundColour(Colors.TEXT_PRIMARY)
        sizer.Add(title_label, 0, wx.ALL, 16)

        # GPU 정보 + 안내 메시지
        info_text = tr('cupy_guide_msg', gpu_name=gpu_name, cuda_version=cuda_ver_str)
        if self._is_frozen:
            info_text += "\n\n" + tr('cupy_guide_frozen_msg')
        else:
            info_text += "\n\n" + tr('cupy_guide_dev_msg')

        desc = wx.StaticText(self, label=info_text)
        desc.SetForegroundColour(Colors.TEXT_SECONDARY)
        desc.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
        desc.Wrap(460)
        sizer.Add(desc, 0, wx.LEFT | wx.RIGHT, 16)

        sizer.Add((0, 12))

        # 명령어 영역
        cmd_text = tr('cupy_guide_cmd', package=self._package_name)
        cmd_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._cmd_ctrl = wx.TextCtrl(
            self, value=cmd_text,
            style=wx.TE_READONLY | wx.BORDER_SIMPLE
        )
        self._cmd_ctrl.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
        self._cmd_ctrl.SetBackgroundColour(wx.Colour(40, 40, 40))
        self._cmd_ctrl.SetForegroundColour(wx.Colour(220, 220, 220))
        cmd_sizer.Add(self._cmd_ctrl, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        copy_btn = FlatButton(self, label=tr('cupy_guide_copy'), size=(110, 30),
                               bg_color=Colors.ACCENT.Get()[:3],
                               fg_color=Colors.TEXT_PRIMARY.Get()[:3],
                               hover_color=Colors.ACCENT_HOVER.Get()[:3],
                               pressed_color=Colors.ACCENT_PRESSED.Get()[:3])
        copy_btn.Bind(wx.EVT_BUTTON, self._on_copy)
        cmd_sizer.Add(copy_btn, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(cmd_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 16)

        sizer.AddStretchSpacer()

        # 하단 버튼 행
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()

        # dev 모드에서만 직접 설치 버튼
        if not self._is_frozen:
            direct_btn = FlatButton(self, label=tr('cupy_guide_direct_install'), size=(110, 32),
                                     bg_color=Colors.ACCENT.Get()[:3],
                                     fg_color=Colors.TEXT_PRIMARY.Get()[:3],
                                     hover_color=Colors.ACCENT_HOVER.Get()[:3],
                                     pressed_color=Colors.ACCENT_PRESSED.Get()[:3])
            direct_btn.Bind(wx.EVT_BUTTON, self._on_direct_install)
            btn_sizer.Add(direct_btn, 0, wx.RIGHT, 8)

        # 재검사 버튼
        recheck_btn = FlatButton(self, label=tr('cupy_guide_recheck'), size=(90, 32),
                                  bg_color=Colors.BG_TERTIARY.Get()[:3],
                                  fg_color=Colors.TEXT_PRIMARY.Get()[:3],
                                  hover_color=Colors.BG_HOVER.Get()[:3])
        recheck_btn.Bind(wx.EVT_BUTTON, self._on_recheck)
        btn_sizer.Add(recheck_btn, 0, wx.RIGHT, 8)

        # CPU 모드로 계속 버튼
        cpu_btn = FlatButton(self, label=tr('dep_use_cpu_instead'), size=(140, 32),
                              bg_color=Colors.BG_TERTIARY.Get()[:3],
                              fg_color=Colors.TEXT_PRIMARY.Get()[:3],
                              hover_color=Colors.BG_HOVER.Get()[:3])
        cpu_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
        btn_sizer.Add(cpu_btn, 0)

        sizer.Add(btn_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 16)
        self.SetSizer(sizer)

    def _on_copy(self, event):
        """명령어를 클립보드에 복사"""
        cmd_text = self._cmd_ctrl.GetValue()
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(cmd_text))
            wx.TheClipboard.Close()
        # 복사됨 피드백
        btn = event.GetEventObject()
        btn.SetLabel(tr('cupy_guide_copied'))

        def _restore_label():
            try:
                btn.SetLabel(tr('cupy_guide_copy'))
            except Exception:
                pass

        wx.CallLater(1500, _restore_label)

    def _on_recheck(self, event):
        """CuPy 재검사"""
        from core.dependency_checker import check_cupy
        status = check_cupy()
        if status.state == DependencyState.INSTALLED:
            wx.MessageBox(
                tr('dep_cupy_installed_ok'),
                tr('info'),
                wx.OK | wx.ICON_INFORMATION
            )
            self.EndModal(wx.ID_OK)
        else:
            wx.MessageBox(
                tr('dep_cupy_still_missing'),
                tr('warning'),
                wx.OK | wx.ICON_WARNING
            )

    def _on_direct_install(self, event):
        """dev 모드에서 pip install 직접 실행"""
        import subprocess
        import threading

        busy = wx.BusyInfo(f"Installing {self._package_name}...")

        def do_install():
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", self._package_name],
                    capture_output=True, text=True, timeout=600
                )
                success = result.returncode == 0
                msg = result.stdout if success else result.stderr
                wx.CallAfter(_on_done, success, msg, busy)
            except subprocess.TimeoutExpired:
                wx.CallAfter(_on_done, False, "Installation timed out.", busy)
            except Exception as e:
                wx.CallAfter(_on_done, False, str(e), busy)

        def _on_done(success, message, busy_ref):
            del busy_ref
            if success:
                wx.MessageBox(
                    tr('dep_cupy_installed_ok'),
                    tr('info'),
                    wx.OK | wx.ICON_INFORMATION
                )
                self.EndModal(wx.ID_OK)
            else:
                wx.MessageBox(
                    tr('cupy_install_failed').format(message[:500]),
                    tr('install_failed'),
                    wx.OK | wx.ICON_WARNING
                )

        threading.Thread(target=do_install, daemon=True).start()


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
    """CuPy 설치 흐름 — 설치 가이드 다이얼로그 표시"""
    dlg = CuPyInstallGuideDialog(parent)
    ret = dlg.ShowModal()
    dlg.Destroy()
    return ret == wx.ID_OK


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
