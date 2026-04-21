"""
설정 다이얼로그
Windows 11 Dark Theme 스타일
GPU/인코더/캡처 백엔드 설정 포함
"""

import logging
import wx
import wx.lib.scrolledpanel as scrolled

from ui.constants import (
    ENCODER_OPTIONS, ENCODER_OPTIONS_MAP,
    CODEC_OPTIONS, CODEC_OPTIONS_MAP,
    CAPTURE_BACKEND_OPTIONS, CAPTURE_BACKEND_OPTIONS_MAP,
    VERSION,
)
from ui.theme import Colors, Fonts, ThemedDialog
from ui.i18n import tr, get_trans_manager
from ui.capture_control_bar import FlatButton
from core.settings import AppSettings

logger = logging.getLogger(__name__)


class SettingsDialog(ThemedDialog):
    """설정 다이얼로그 - Windows 11 Dark Theme"""

    DEFAULT_SETTINGS = AppSettings().to_dict()

    def __init__(self, parent=None, settings=None):
        ThemedDialog.__init__(self, parent, title=tr('settings'), size=(520, 580),
                              style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        # settings는 AppSettings 인스턴스 또는 configparser.ConfigParser
        self.settings = settings
        self._is_app_settings = isinstance(settings, AppSettings)
        self.trans = get_trans_manager()
        self.trans.register_callback(self.retranslateUi)

        self.SetMinSize((400, 420))
        self.status_label = None
        self._init_ui()

        # 설정 다이얼로그 열 때 HDR 캐시 무효화 (디스플레이 설정 변경 반영)
        try:
            from core.hdr_utils import clear_hdr_cache
            clear_hdr_cache()
        except ImportError:
            pass

        # 다이얼로그 닫을 때 번역 콜백 해제 (메모리 누수 방지)
        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _init_ui(self):
        """UI 초기화 (Windows 11 Dark Theme)"""
        self.SetBackgroundColour(Colors.BG_PANEL)
        self.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 스크롤 패널
        self.scroll_panel = scrolled.ScrolledPanel(self)
        self.scroll_panel.SetBackgroundColour(Colors.BG_PANEL)
        self.scroll_panel.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)

        # === 언어 설정 그룹 ===
        self.lang_box = wx.StaticBox(self.scroll_panel, label=tr('language'))
        self.lang_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.lang_box.SetFont(Fonts.get_font(Fonts.SIZE_LABEL, bold=True))
        lang_sizer = wx.StaticBoxSizer(self.lang_box, wx.HORIZONTAL)

        self.lang_label = wx.StaticText(self.scroll_panel, label=tr('language') + ":")
        self.lang_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        self.lang_label.SetMinSize((130, -1))
        self.lang_combo = wx.Choice(self.scroll_panel, choices=[tr('language_ko'), tr('language_en')])
        self.lang_combo.SetToolTip(tr('language_tooltip'))
        self._style_choice(self.lang_combo)

        lang_sizer.Add(self.lang_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 8)
        lang_sizer.Add(self.lang_combo, 0, wx.ALL, 8)
        lang_sizer.AddStretchSpacer()
        scroll_sizer.Add(lang_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # === 미리보기 및 HDR 그룹 ===
        self.preview_box = wx.StaticBox(self.scroll_panel, label=tr('preview'))
        self.preview_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.preview_box.SetFont(Fonts.get_font(Fonts.SIZE_LABEL, bold=True))
        preview_sizer = wx.StaticBoxSizer(self.preview_box, wx.VERTICAL)

        self.preview_cb = wx.CheckBox(self.scroll_panel, label=tr('realtime_preview'))
        self.preview_cb.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.preview_cb.SetToolTip(tr('realtime_preview_tooltip'))
        preview_sizer.Add(self.preview_cb, 0, wx.ALL, 8)

        self.hdr_correction_cb = wx.CheckBox(self.scroll_panel, label="HDR 모니터 보정 (캡처가 너무 밝을 때)")
        self.hdr_correction_cb.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.hdr_correction_cb.SetToolTip("HDR 모니터에서 캡처가 비정상적으로 밝게 나오면 켜세요. 톤 매핑을 적용합니다.")
        preview_sizer.Add(self.hdr_correction_cb, 0, wx.ALL, 8)

        scroll_sizer.Add(preview_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # === 메모리 설정 그룹 ===
        self.memory_box = wx.StaticBox(self.scroll_panel, label=tr('memory_management'))
        self.memory_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.memory_box.SetFont(Fonts.get_font(Fonts.SIZE_LABEL, bold=True))
        memory_sizer = wx.StaticBoxSizer(self.memory_box, wx.VERTICAL)

        memory_row = wx.BoxSizer(wx.HORIZONTAL)
        self.memory_label = wx.StaticText(self.scroll_panel, label=tr('max_memory'))
        self.memory_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        self.memory_label.SetMinSize((130, -1))
        self.memory_limit_combo = wx.Choice(self.scroll_panel,
            choices=["1 GB (" + tr('auto') + ")", "2 GB", "3 GB", "4 GB"])
        self.memory_limit_combo.SetToolTip(tr('max_memory_tooltip'))
        self._style_choice(self.memory_limit_combo)

        memory_row.Add(self.memory_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 8)
        memory_row.Add(self.memory_limit_combo, 0, wx.ALL, 8)
        memory_row.AddStretchSpacer()
        memory_sizer.Add(memory_row, 0, wx.EXPAND)

        scroll_sizer.Add(memory_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # === GPU 및 인코더 그룹 ===
        self.gpu_box = wx.StaticBox(self.scroll_panel, label=tr('gpu_encoder'))
        self.gpu_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.gpu_box.SetFont(Fonts.get_font(Fonts.SIZE_LABEL, bold=True))
        gpu_sizer = wx.StaticBoxSizer(self.gpu_box, wx.VERTICAL)

        # 캡처 백엔드
        backend_row = wx.BoxSizer(wx.HORIZONTAL)
        self.backend_label = wx.StaticText(self.scroll_panel, label=tr('capture_backend'))
        self.backend_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        self.backend_label.SetMinSize((130, -1))
        self.backend_combo = wx.Choice(self.scroll_panel, choices=CAPTURE_BACKEND_OPTIONS)
        self.backend_combo.SetToolTip(tr('capture_backend_tooltip'))
        self.backend_combo.Bind(wx.EVT_CHOICE, self._on_backend_changed)
        self._style_choice(self.backend_combo)
        backend_row.Add(self.backend_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 8)
        backend_row.Add(self.backend_combo, 0, wx.ALL, 8)
        backend_row.AddStretchSpacer()
        gpu_sizer.Add(backend_row, 0, wx.EXPAND)

        # 인코더
        encoder_row = wx.BoxSizer(wx.HORIZONTAL)
        self.encoder_label = wx.StaticText(self.scroll_panel, label=tr('encoder'))
        self.encoder_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        self.encoder_label.SetMinSize((130, -1))
        self.encoder_combo = wx.Choice(self.scroll_panel, choices=ENCODER_OPTIONS)
        self.encoder_combo.SetToolTip(tr('encoder_tooltip'))
        self._style_choice(self.encoder_combo)
        encoder_row.Add(self.encoder_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 8)
        encoder_row.Add(self.encoder_combo, 0, wx.ALL, 8)
        encoder_row.AddStretchSpacer()
        gpu_sizer.Add(encoder_row, 0, wx.EXPAND)

        # 코덱
        codec_row = wx.BoxSizer(wx.HORIZONTAL)
        self.codec_label = wx.StaticText(self.scroll_panel, label=tr('codec'))
        self.codec_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        self.codec_label.SetMinSize((130, -1))
        self.codec_combo = wx.Choice(self.scroll_panel, choices=CODEC_OPTIONS)
        self.codec_combo.SetToolTip(tr('codec_tooltip'))
        self._style_choice(self.codec_combo)
        codec_row.Add(self.codec_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 8)
        codec_row.Add(self.codec_combo, 0, wx.ALL, 8)
        codec_row.AddStretchSpacer()
        gpu_sizer.Add(codec_row, 0, wx.EXPAND)

        scroll_sizer.Add(gpu_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # === 오디오 그룹 ===
        self.audio_box = wx.StaticBox(self.scroll_panel, label=tr('audio'))
        self.audio_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.audio_box.SetFont(Fonts.get_font(Fonts.SIZE_LABEL, bold=True))
        audio_sizer = wx.StaticBoxSizer(self.audio_box, wx.VERTICAL)

        self.mic_audio_cb = wx.CheckBox(self.scroll_panel, label=tr('mic_recording'))
        self.mic_audio_cb.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.mic_audio_cb.SetToolTip(tr('mic_recording_tooltip'))
        audio_sizer.Add(self.mic_audio_cb, 0, wx.ALL, 8)

        scroll_sizer.Add(audio_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # === 오버레이 그룹 ===
        self.overlay_box = wx.StaticBox(self.scroll_panel, label=tr('overlay'))
        self.overlay_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.overlay_box.SetFont(Fonts.get_font(Fonts.SIZE_LABEL, bold=True))
        overlay_sizer = wx.StaticBoxSizer(self.overlay_box, wx.VERTICAL)

        self.watermark_cb = wx.CheckBox(self.scroll_panel, label=tr('watermark'))
        self.watermark_cb.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.watermark_cb.SetToolTip(tr('watermark_tooltip'))
        overlay_sizer.Add(self.watermark_cb, 0, wx.ALL, 8)

        scroll_sizer.Add(overlay_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # === 인터랙션 그룹 ===
        self.interaction_box = wx.StaticBox(self.scroll_panel, label=tr('interaction'))
        self.interaction_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.interaction_box.SetFont(Fonts.get_font(Fonts.SIZE_LABEL, bold=True))
        interaction_sizer = wx.StaticBoxSizer(self.interaction_box, wx.VERTICAL)

        self.click_highlight_cb = wx.CheckBox(self.scroll_panel, label=tr('click_highlight'))
        self.click_highlight_cb.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.click_highlight_cb.SetToolTip(tr('click_highlight_tooltip'))
        interaction_sizer.Add(self.click_highlight_cb, 0, wx.ALL, 8)

        self.keyboard_display_cb = wx.CheckBox(self.scroll_panel, label=tr('keyboard_display'))
        self.keyboard_display_cb.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.keyboard_display_cb.SetToolTip(tr('keyboard_display_tooltip'))
        interaction_sizer.Add(self.keyboard_display_cb, 0, wx.ALL, 8)

        scroll_sizer.Add(interaction_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # 스크롤 패널 설정
        self.scroll_panel.SetSizer(scroll_sizer)
        self.scroll_panel.SetupScrolling(scroll_x=False)
        main_sizer.Add(self.scroll_panel, 1, wx.EXPAND | wx.ALL, 0)

        # === 하단 고정 영역 ===
        bottom_panel = wx.Panel(self)
        bottom_panel.SetBackgroundColour(Colors.BG_PANEL)
        bottom_sizer = wx.BoxSizer(wx.VERTICAL)

        # 상태 레이블
        self.status_label = wx.StaticText(bottom_panel, label="")
        self.status_label.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.status_label.Hide()
        bottom_sizer.Add(self.status_label, 0, wx.ALL | wx.ALIGN_CENTER, 8)

        # 버튼 행 (FlatButton 사용)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 기본값 복원 버튼
        self.reset_btn = FlatButton(bottom_panel, label=tr('reset_defaults'), size=(120, 30),
                                    bg_color=Colors.BG_TERTIARY.Get()[:3],
                                    fg_color=Colors.TEXT_PRIMARY.Get()[:3],
                                    hover_color=Colors.BG_HOVER.Get()[:3])
        self.reset_btn.SetToolTip(tr('reset_tooltip'))
        self.reset_btn.Bind(wx.EVT_BUTTON, self._on_reset)
        btn_sizer.Add(self.reset_btn, 0, wx.ALL, 8)

        # 의존성 확인 초기화 버튼
        self.reset_dep_btn = FlatButton(bottom_panel, label=tr('dep_reset_skip_flags'), size=(150, 30),
                                         bg_color=Colors.BG_TERTIARY.Get()[:3],
                                         fg_color=Colors.TEXT_PRIMARY.Get()[:3],
                                         hover_color=Colors.BG_HOVER.Get()[:3])
        self.reset_dep_btn.SetToolTip(tr('dep_reset_skip_flags_tooltip'))
        self.reset_dep_btn.Bind(wx.EVT_BUTTON, self._on_reset_dep_flags)
        btn_sizer.Add(self.reset_dep_btn, 0, wx.ALL, 8)

        btn_sizer.AddStretchSpacer()

        # 확인 버튼 (Accent 색상)
        ok_label = tr('ok') if callable(tr) else "확인"
        self.ok_btn = FlatButton(bottom_panel, label=ok_label, size=(80, 30),
                                 bg_color=Colors.ACCENT.Get()[:3],
                                 fg_color=Colors.TEXT_PRIMARY.Get()[:3],
                                 hover_color=Colors.ACCENT_HOVER.Get()[:3],
                                 pressed_color=Colors.ACCENT_PRESSED.Get()[:3])
        self.ok_btn.Bind(wx.EVT_BUTTON, self._on_ok)
        btn_sizer.Add(self.ok_btn, 0, wx.ALL, 8)

        # 취소 버튼
        cancel_label = tr('cancel') if callable(tr) else "취소"
        self.cancel_btn = FlatButton(bottom_panel, label=cancel_label, size=(80, 30),
                                     bg_color=Colors.BG_TERTIARY.Get()[:3],
                                     fg_color=Colors.TEXT_PRIMARY.Get()[:3],
                                     hover_color=Colors.BG_HOVER.Get()[:3])
        self.cancel_btn.Bind(wx.EVT_BUTTON, self._on_cancel)
        btn_sizer.Add(self.cancel_btn, 0, wx.ALL, 8)

        bottom_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 8)

        # 버전 정보
        version_label = wx.StaticText(bottom_panel, label=f"v{VERSION}")
        version_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        version_label.SetFont(Fonts.get_font(Fonts.SIZE_SMALL))
        bottom_sizer.Add(version_label, 0, wx.ALL | wx.ALIGN_RIGHT, 8)

        bottom_panel.SetSizer(bottom_sizer)
        main_sizer.Add(bottom_panel, 0, wx.EXPAND | wx.ALL, 0)

        self.SetSizer(main_sizer)
        self.load_settings()

    def _style_choice(self, choice):
        """Choice 컨트롤 다크 테마 스타일"""
        choice.SetBackgroundColour(Colors.BG_TOOLBAR)
        choice.SetForegroundColour(Colors.TEXT_PRIMARY)
        choice.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))

    def _on_backend_changed(self, event):
        """캡처 백엔드 변경 시 dxcam 설치 확인 (3버튼 모달)"""
        idx = self.backend_combo.GetSelection()
        if idx < 0 or idx >= len(CAPTURE_BACKEND_OPTIONS):
            return
        selected_key = CAPTURE_BACKEND_OPTIONS[idx]
        selected_val = CAPTURE_BACKEND_OPTIONS_MAP.get(selected_key, "auto")

        if selected_val == "dxcam":
            try:
                import dxcam  # noqa: F401
            except ImportError:
                self._offer_dxcam_install_3btn()

    def _offer_dxcam_install_3btn(self):
        """dxcam 미설치 시 3버튼 모달로 설치 제안"""
        from core.dependency_checker import check_dxcam, DependencyState
        from ui.dependency_dialogs import (
            DependencyInstallDialog, ID_INSTALL, show_install_flow,
        )

        status = check_dxcam()
        if status.state == DependencyState.INSTALLED:
            return

        dlg = DependencyInstallDialog(
            self, status,
            tr('dep_dxcam_desc'),
            disable_label=tr('dep_use_gdi_instead'),
            show_dont_ask=True,
        )
        ret = dlg.ShowModal()
        dont_ask = dlg.dont_ask_again
        dlg.Destroy()

        if dont_ask and self.settings:
            if self._is_app_settings:
                self.settings.set('skip_dxcam_check', 'true')
            else:
                if not self.settings.has_section('General'):
                    self.settings.add_section('General')
                self.settings.set('General', 'skip_dxcam_check', 'true')

        if ret == ID_INSTALL.GetId():
            success = show_install_flow(self, "dxcam", status)
            if not success:
                self._revert_to_gdi()
        else:
            self._revert_to_gdi()

    def _revert_to_gdi(self):
        """백엔드를 GDI로 되돌리기"""
        for i, key in enumerate(CAPTURE_BACKEND_OPTIONS):
            if CAPTURE_BACKEND_OPTIONS_MAP.get(key) == "gdi":
                self.backend_combo.SetSelection(i)
                break

    def _cfg(self, key: str, fallback: str = "") -> str:
        """설정 값 읽기 — AppSettings / configparser 양쪽 호환."""
        if self._is_app_settings:
            return self.settings.get(key, fallback)
        # configparser 경로
        return self.settings.get("General", key, fallback=fallback)

    def _cfg_set(self, key: str, value: str) -> None:
        """설정 값 쓰기 — AppSettings / configparser 양쪽 호환."""
        if self._is_app_settings:
            self.settings.set(key, value)
        else:
            if not self.settings.has_section('General'):
                self.settings.add_section('General')
            self.settings.set('General', key, value)

    def load_settings(self):
        """설정 값 불러오기"""
        if not self.settings:
            return

        try:
            self.mic_audio_cb.SetValue(self._cfg("mic_audio", "false").lower() == "true")
            self.watermark_cb.SetValue(self._cfg("watermark", "false").lower() == "true")
            self.click_highlight_cb.SetValue(self._cfg("click_highlight", "false").lower() == "true")
            self.keyboard_display_cb.SetValue(self._cfg("keyboard_display", "false").lower() == "true")
            self.preview_cb.SetValue(self._cfg("preview_enabled", "false").lower() == "true")
            self.hdr_correction_cb.SetValue(self._cfg("hdr_correction", "false").lower() == "true")

            lang = self._cfg("language", "ko")
            self.lang_combo.SetSelection(0 if lang == 'ko' else 1)

            backend = self._cfg('capture_backend', 'gdi')
            backend_idx = self._find_combo_index(CAPTURE_BACKEND_OPTIONS_MAP, backend)
            if 0 <= backend_idx < self.backend_combo.GetCount():
                self.backend_combo.SetSelection(backend_idx)
            else:
                self.backend_combo.SetSelection(0)

            encoder = self._cfg('encoder', 'auto')
            encoder_idx = self._find_combo_index(ENCODER_OPTIONS_MAP, encoder)
            if 0 <= encoder_idx < self.encoder_combo.GetCount():
                self.encoder_combo.SetSelection(encoder_idx)
            else:
                self.encoder_combo.SetSelection(0)

            codec = self._cfg('codec', 'h264')
            codec_idx = self._find_combo_index(CODEC_OPTIONS_MAP, codec)
            if 0 <= codec_idx < self.codec_combo.GetCount():
                self.codec_combo.SetSelection(codec_idx)
            else:
                self.codec_combo.SetSelection(0)

            memory_limit = self._cfg('memory_limit_mb', '1024')
            memory_map = {"1024": 0, "2048": 1, "3072": 2, "4096": 3}
            self.memory_limit_combo.SetSelection(memory_map.get(memory_limit, 0))
        except Exception as e:
            logger.warning("설정 불러오기 오류: %s", e)

    def _find_combo_index(self, options_map: dict, value: str) -> int:
        if not options_map or not value:
            return 0
        try:
            for idx, (key, val) in enumerate(options_map.items()):
                if val == value:
                    return idx
        except (TypeError, ValueError):
            pass
        return 0

    def save_settings(self) -> bool:
        """설정 값 저장"""
        if not self.settings:
            return False

        try:
            self._cfg_set('mic_audio', "true" if self.mic_audio_cb.GetValue() else "false")
            self._cfg_set('watermark', "true" if self.watermark_cb.GetValue() else "false")
            self._cfg_set('click_highlight', "true" if self.click_highlight_cb.GetValue() else "false")
            self._cfg_set('keyboard_display', "true" if self.keyboard_display_cb.GetValue() else "false")
            self._cfg_set('preview_enabled', "true" if self.preview_cb.GetValue() else "false")
            self._cfg_set('hdr_correction', "true" if self.hdr_correction_cb.GetValue() else "false")

            try:
                backend_idx = self.backend_combo.GetSelection()
                if 0 <= backend_idx < len(CAPTURE_BACKEND_OPTIONS):
                    backend_key = CAPTURE_BACKEND_OPTIONS[backend_idx]
                    self._cfg_set('capture_backend', CAPTURE_BACKEND_OPTIONS_MAP.get(backend_key, "auto"))
                else:
                    self._cfg_set('capture_backend', "auto")
            except (AttributeError, IndexError, KeyError):
                self._cfg_set('capture_backend', "auto")

            try:
                encoder_idx = self.encoder_combo.GetSelection()
                if 0 <= encoder_idx < len(ENCODER_OPTIONS):
                    encoder_key = ENCODER_OPTIONS[encoder_idx]
                    self._cfg_set('encoder', ENCODER_OPTIONS_MAP.get(encoder_key, "auto"))
                else:
                    self._cfg_set('encoder', "auto")
            except (AttributeError, IndexError, KeyError):
                self._cfg_set('encoder', "auto")

            try:
                codec_idx = self.codec_combo.GetSelection()
                if 0 <= codec_idx < len(CODEC_OPTIONS):
                    codec_key = CODEC_OPTIONS[codec_idx]
                    self._cfg_set('codec', CODEC_OPTIONS_MAP.get(codec_key, "h264"))
                else:
                    self._cfg_set('codec', "h264")
            except (AttributeError, IndexError, KeyError):
                self._cfg_set('codec', "h264")

            memory_limit_map = {0: "1024", 1: "2048", 2: "3072", 3: "4096"}
            self._cfg_set('memory_limit_mb', memory_limit_map.get(self.memory_limit_combo.GetSelection(), "1024"))

            lang_idx = self.lang_combo.GetSelection()
            lang_data = 'ko' if lang_idx == 0 else 'en'
            self._cfg_set('language', lang_data)
            self.trans.set_language(lang_data)

            # 저장
            if self._is_app_settings:
                self.settings.save()
            else:
                import os
                from core.utils import APP_SETTINGS_NAME
                appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
                config_dir = os.path.join(appdata, APP_SETTINGS_NAME)
                os.makedirs(config_dir, exist_ok=True)
                config_path = os.path.join(config_dir, 'config.ini')
                with open(config_path, 'w', encoding='utf-8') as f:
                    self.settings.write(f)
            return True
        except Exception as e:
            logger.warning("설정 저장 오류: %s", e)
            return False

    def _on_reset(self, event):
        """설정을 기본값으로 복원"""
        dlg = wx.MessageDialog(
            self,
            tr('reset_confirm_msg'),
            tr('reset_confirm_title'),
            wx.YES_NO | wx.ICON_QUESTION | wx.NO_DEFAULT
        )
        if dlg.ShowModal() == wx.ID_YES:
            self.mic_audio_cb.SetValue(self.DEFAULT_SETTINGS["mic_audio"] == "true")
            self.watermark_cb.SetValue(self.DEFAULT_SETTINGS["watermark"] == "true")
            self.click_highlight_cb.SetValue(self.DEFAULT_SETTINGS["click_highlight"] == "true")
            self.keyboard_display_cb.SetValue(self.DEFAULT_SETTINGS["keyboard_display"] == "true")
            self.preview_cb.SetValue(self.DEFAULT_SETTINGS["preview_enabled"] == "true")
            self.hdr_correction_cb.SetValue(self.DEFAULT_SETTINGS["hdr_correction"] == "true")

            lang_default = self.DEFAULT_SETTINGS["language"]
            lang_idx = 0 if lang_default == 'ko' else 1
            self.lang_combo.SetSelection(lang_idx)

            backend_idx = self._find_combo_index(CAPTURE_BACKEND_OPTIONS_MAP, self.DEFAULT_SETTINGS["capture_backend"])
            self.backend_combo.SetSelection(backend_idx)

            encoder_idx = self._find_combo_index(ENCODER_OPTIONS_MAP, self.DEFAULT_SETTINGS["encoder"])
            self.encoder_combo.SetSelection(encoder_idx)

            codec_idx = self._find_combo_index(CODEC_OPTIONS_MAP, self.DEFAULT_SETTINGS["codec"])
            self.codec_combo.SetSelection(codec_idx)

            memory_limit = self.DEFAULT_SETTINGS["memory_limit_mb"]
            memory_map = {"1024": 0, "2048": 1, "3072": 2, "4096": 3}
            self.memory_limit_combo.SetSelection(memory_map.get(memory_limit, 0))

            self._show_status(tr('settings_reset'), success=True)
        dlg.Destroy()

    def _on_reset_dep_flags(self, event):
        """의존성 확인 skip 플래그 초기화"""
        if self.settings:
            self._cfg_set('skip_ffmpeg_check', 'false')
            self._cfg_set('skip_cupy_check', 'false')
            self._cfg_set('skip_dxcam_check', 'false')
            self._cfg_set('startup_dep_checked', 'false')
        self._show_status(tr('dep_skip_flags_reset'), success=True)

    def _show_status(self, message: str, success: bool = True, duration_ms: int = 2000):
        """상태 메시지 표시"""
        if self.status_label:
            self.status_label.SetLabel(message)
            self.status_label.Show()

            if success:
                self.status_label.SetBackgroundColour(Colors.STATUS_SUCCESS_ALT)
            else:
                self.status_label.SetBackgroundColour(Colors.STATUS_ERROR)

            self.status_label.SetForegroundColour(Colors.TEXT_PRIMARY)
            self.Layout()

            def hide_label():
                try:
                    if self.status_label and self.status_label.IsShown():
                        self.status_label.Hide()
                        self.Layout()
                except (RuntimeError, AttributeError):
                    pass
            wx.CallLater(duration_ms, hide_label)

    def _on_ok(self, event):
        """확인 버튼 클릭"""
        if self.save_settings():
            self._show_status(tr('settings_saved'), success=True)

            def do_close():
                try:
                    self.EndModal(wx.ID_OK)
                except (RuntimeError, AttributeError):
                    pass
            wx.CallLater(300, do_close)
        else:
            self._show_status(tr('save_failed'), success=False)
            wx.MessageBox(tr('save_failed'), tr('warning'), wx.OK | wx.ICON_WARNING)

    def _on_cancel(self, event):
        """취소 버튼 클릭"""
        self.EndModal(wx.ID_CANCEL)

    def _on_close(self, event):
        """다이얼로그 닫힐 때 번역 콜백 해제"""
        try:
            self.trans.unregister_callback(self.retranslateUi)
        except Exception:
            pass
        event.Skip()

    def retranslateUi(self, lang=None):
        """언어 변경 시 UI 업데이트"""
        self.SetTitle(tr('settings'))

        if hasattr(self, 'lang_box'):
            self.lang_box.SetLabel(tr('language'))
        if hasattr(self, 'audio_box'):
            self.audio_box.SetLabel(tr('audio'))
        if hasattr(self, 'overlay_box'):
            self.overlay_box.SetLabel(tr('overlay'))
        if hasattr(self, 'interaction_box'):
            self.interaction_box.SetLabel(tr('interaction'))
        if hasattr(self, 'preview_box'):
            self.preview_box.SetLabel(tr('preview'))
        if hasattr(self, 'memory_box'):
            self.memory_box.SetLabel(tr('memory_management'))
        if hasattr(self, 'gpu_box'):
            self.gpu_box.SetLabel(tr('gpu_encoder'))

        if hasattr(self, 'lang_label'):
            self.lang_label.SetLabel(tr('language') + ":")
        if hasattr(self, 'mic_audio_cb'):
            self.mic_audio_cb.SetLabel(tr('mic_recording'))
        if hasattr(self, 'watermark_cb'):
            self.watermark_cb.SetLabel(tr('watermark'))
        if hasattr(self, 'click_highlight_cb'):
            self.click_highlight_cb.SetLabel(tr('click_highlight'))
        if hasattr(self, 'keyboard_display_cb'):
            self.keyboard_display_cb.SetLabel(tr('keyboard_display'))
        if hasattr(self, 'preview_cb'):
            self.preview_cb.SetLabel(tr('realtime_preview'))
        if hasattr(self, 'memory_label'):
            self.memory_label.SetLabel(tr('max_memory'))
        if hasattr(self, 'backend_label'):
            self.backend_label.SetLabel(tr('capture_backend'))
        if hasattr(self, 'encoder_label'):
            self.encoder_label.SetLabel(tr('encoder'))
        if hasattr(self, 'codec_label'):
            self.codec_label.SetLabel(tr('codec'))
        if hasattr(self, 'reset_btn'):
            self.reset_btn.SetLabel(tr('reset_defaults'))
        if hasattr(self, 'reset_dep_btn'):
            self.reset_dep_btn.SetLabel(tr('dep_reset_skip_flags'))
            self.reset_dep_btn.SetToolTip(tr('dep_reset_skip_flags_tooltip'))

        if hasattr(self, 'lang_combo'):
            self.lang_combo.SetToolTip(tr('language_tooltip'))
        if hasattr(self, 'mic_audio_cb'):
            self.mic_audio_cb.SetToolTip(tr('mic_recording_tooltip'))
        if hasattr(self, 'watermark_cb'):
            self.watermark_cb.SetToolTip(tr('watermark_tooltip'))
        if hasattr(self, 'click_highlight_cb'):
            self.click_highlight_cb.SetToolTip(tr('click_highlight_tooltip'))
        if hasattr(self, 'keyboard_display_cb'):
            self.keyboard_display_cb.SetToolTip(tr('keyboard_display_tooltip'))
        if hasattr(self, 'preview_cb'):
            self.preview_cb.SetToolTip(tr('realtime_preview_tooltip'))
        if hasattr(self, 'memory_limit_combo'):
            self.memory_limit_combo.SetToolTip(tr('max_memory_tooltip'))
        if hasattr(self, 'backend_combo'):
            self.backend_combo.SetToolTip(tr('capture_backend_tooltip'))
        if hasattr(self, 'encoder_combo'):
            self.encoder_combo.SetToolTip(tr('encoder_tooltip'))
        if hasattr(self, 'codec_combo'):
            self.codec_combo.SetToolTip(tr('codec_tooltip'))
        if hasattr(self, 'reset_btn'):
            self.reset_btn.SetToolTip(tr('reset_tooltip'))

        if hasattr(self, 'memory_limit_combo'):
            curr_mem_idx = self.memory_limit_combo.GetSelection()
            self.memory_limit_combo.Clear()
            self.memory_limit_combo.AppendItems(["1 GB (" + tr('auto') + ")", "2 GB", "3 GB", "4 GB"])
            if curr_mem_idx >= 0:
                self.memory_limit_combo.SetSelection(curr_mem_idx)

        if hasattr(self, 'lang_combo'):
            curr_lang_idx = self.lang_combo.GetSelection()
            self.lang_combo.Clear()
            self.lang_combo.Append(tr('language_ko'))
            self.lang_combo.Append(tr('language_en'))
            if curr_lang_idx >= 0:
                self.lang_combo.SetSelection(curr_lang_idx)
