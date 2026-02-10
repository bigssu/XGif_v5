"""
Giffy 메인 윈도우
wxPython 기반 UI: 녹화 제어 버튼
프로그램 시작 시 자동으로 캡처 영역 표시
"""

import os
import sys
import logging
import wx
import threading
import configparser
import numpy as np

# 로깅 설정
logger = logging.getLogger(__name__)

# 메모리 모니터링 (선택적)
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# GPU 유틸리티
from core.gpu_utils import detect_gpu, is_gpu_available, get_gpu_info_string

# Capability Manager (자동 최적화)
from core.capability_manager import get_capability_manager, CapabilityManager

# HDR 모니터 표시
from core.hdr_utils import is_hdr_active

# 오디오 녹음
from core.audio_recorder import AudioRecorder, is_audio_available

# 상수 정의
from ui.constants import (
    MAIN_WINDOW_MIN_WIDTH, MAIN_WINDOW_MIN_HEIGHT,
    APP_NAME, VERSION, MEMORY_WARNING_RATIO, SYSTEM_MEMORY_CRITICAL_MB,
    CAPTURE_PROCESS_TIMEOUT_SEC, CAPTURE_THREAD_TIMEOUT_SEC,
    ENCODING_THREAD_TIMEOUT_SEC, ENCODING_STATUS_CLEAR_DELAY_MS,
)
from ui.theme import Colors, Fonts
from ui.i18n import tr, get_trans_manager


class EncodingThread(threading.Thread):
    """GIF/MP4 인코딩을 위한 별도 스레드"""
    
    def __init__(self, encoder, frames, fps, output_path, output_format='gif', audio_path=None,
                 progress_callback=None, finished_callback=None, error_callback=None):
        threading.Thread.__init__(self, daemon=True)
        self.encoder = encoder
        self.frames = frames
        self.fps = fps
        self.output_path = output_path
        self.output_format = output_format.lower()  # 'gif' or 'mp4'
        self.audio_path = audio_path  # MP4용 오디오 파일 경로
        
        # 콜백 함수들
        self._progress_callback = progress_callback
        self._finished_callback = finished_callback
        self._error_callback = error_callback
        
        # 인코더 콜백 설정
        if self.encoder:
            self.encoder.set_progress_callback(self._on_progress)
            self.encoder.set_finished_callback(self._on_finished)
            self.encoder.set_error_callback(self._on_error)
    
    def _on_progress(self, current, total):
        if self._progress_callback:
            wx.CallAfter(self._progress_callback, current, total)
    
    def _on_finished(self, path):
        if self._finished_callback:
            wx.CallAfter(self._finished_callback, path)
    
    def _on_error(self, msg):
        if self._error_callback:
            wx.CallAfter(self._error_callback, msg)
    
    def run(self):
        try:
            if self.output_format == 'mp4':
                self.encoder.encode_mp4(self.frames, self.fps, self.output_path, self.audio_path)
            else:
                self.encoder.encode(self.frames, self.fps, self.output_path)
        except Exception as e:
            if self._error_callback:
                wx.CallAfter(self._error_callback, str(e))


class MainWindow(wx.Frame):
    """Giffy 메인 윈도우"""
    
    # 녹화 상태
    STATE_READY = 0
    STATE_RECORDING = 1
    STATE_PAUSED = 2
    
    def __init__(self, parent=None):
        wx.Frame.__init__(self, parent, title=f"{APP_NAME} v{VERSION}",
                         size=(MAIN_WINDOW_MIN_WIDTH, MAIN_WINDOW_MIN_HEIGHT),
                         style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
        self.capture_overlay = None
        self._last_pos = None  # 메인 윈도우 이전 위치 (오버레이 델타 이동용)
        self.recorder = None
        self.encoder = None
        self.record_state = self.STATE_READY
        self.frames = []
        self._editor_mode = False  # 편집 모드 플래그 (오버레이 재생성 방지)
        
        # 실시간 미리보기
        self.preview_enabled = False
        self.preview_timer = None
        self.preview_widget = None
        self.preview_label = None
        
        # 녹화 관련 변수 초기화
        self.record_timer = None
        self.record_elapsed = 0
        self._cached_frame_size = None
        self._memory_warned = False
        self._system_memory_warned = False
        
        # 인코딩 스레드
        self.encoding_thread = None
        
        # FFmpeg 다운로더
        self.ffmpeg_downloader = None
        self.ffmpeg_progress = None
        
        # 오디오 관련
        self.audio_file_path = None
        
        # 설정 저장/불러오기
        from core.utils import APP_SETTINGS_ORG, APP_SETTINGS_NAME
        import os
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        config_dir = os.path.join(appdata, APP_SETTINGS_NAME)
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, 'config.ini')
        self.settings = configparser.ConfigParser()
        if os.path.exists(config_path):
            self.settings.read(config_path, encoding='utf-8')
        if not self.settings.has_section('General'):
            self.settings.add_section('General')
        
        # 언어 관리자 초기화
        self.trans = get_trans_manager()
        language = self.settings.get('General', 'language', fallback='ko')
        self.trans.set_language(str(language))
        self.trans.register_callback(self.retranslateUi)
        
        # Capability Manager 초기화 (비동기로 시스템 능력 감지)
        self._capability_manager = get_capability_manager()
        
        # 윈도우 아이콘 설정
        from core.utils import get_resource_path
        icon_path = get_resource_path(os.path.join('resources', 'xgif_icon.ico'))
        if not os.path.exists(icon_path):
            icon_path = get_resource_path(os.path.join('resources', 'Xgif_icon.png'))
        if os.path.exists(icon_path):
            icon = wx.Icon(icon_path, wx.BITMAP_TYPE_ICO if icon_path.endswith('.ico') else wx.BITMAP_TYPE_PNG)
            self.SetIcon(icon)
        
        # GPU 초기화 플래그 (버튼 클릭 시 지연 초기화)
        self._gpu_initialized = False

        self._init_ui()
        self._init_recorder()
        self._setup_shortcuts()
        
        # 프로그램 시작 시 자동으로 캡처 영역 표시
        wx.CallLater(100, self._show_capture_overlay)
        
        # 시스템 능력 감지 (백그라운드에서 실행)
        wx.CallLater(500, self._detect_system_capabilities)
        
        # HDR 레이블 갱신 (설정에서 수동 켠 경우 표시)
        wx.CallLater(100, self._update_hdr_label)
        
        # 미리보기 시작 (설정에서 활성화된 경우)
        saved_preview = self.settings.get('General', 'preview_enabled', fallback='false')
        if saved_preview == "true":
            self.preview_enabled = True
            self._start_preview()
        
        # 이벤트 바인딩
        self.Bind(wx.EVT_MOVE, self.OnMove)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
    
    def _init_ui(self):
        """UI 초기화"""
        self.SetTitle(f"{APP_NAME} v{VERSION}")
        self.SetMinSize((MAIN_WINDOW_MIN_WIDTH, MAIN_WINDOW_MIN_HEIGHT))

        # 전역 Segoe UI 폰트 설정
        self.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))

        # 메인 패널 (툴바·프로그레스 영역·미리보기 영역 포함) - Windows 11 Dark Theme
        main_panel = wx.Panel(self)
        main_panel.SetBackgroundColour(Colors.BG_PRIMARY)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_panel.SetSizer(main_sizer)
        main_sizer.Add((0, 4))  # 상단 4px
        # Windows 11 Dark Theme 컨트롤 바
        from ui.capture_control_bar import CaptureControlBar
        self.capture_control_bar = CaptureControlBar(main_panel)
        self._connect_capture_control_bar()
        main_sizer.Add(self.capture_control_bar, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # 임시 버튼 참조 (호환성을 위해 capture_control_bar의 버튼 사용)
        self.start_btn = self.capture_control_bar.rec_button
        
        # 프로그레스 바 영역 (툴바 하단 중앙)
        self._create_progress_area(main_sizer, main_panel)
        
        # 실시간 미리보기 영역 (선택적)
        self._create_preview_area(main_sizer)
        main_sizer.SetSizeHints(main_panel)
        
        # 커스텀 상태바 (Windows 11 Dark Theme)
        status_panel = wx.Panel(self)
        status_panel.SetBackgroundColour(Colors.BG_SECONDARY)
        status_panel.SetMinSize((-1, 26))
        status_sizer = wx.BoxSizer(wx.HORIZONTAL)
        status_panel.SetSizer(status_sizer)
        font_sb = Fonts.get_font(Fonts.SIZE_DEFAULT)
        fg_sb = Colors.TEXT_PRIMARY
        # 필드 0: 메인 메시지 (준비 / 녹화 중 / 저장됨 등) - 긴 텍스트 말줄임
        ellipsize_style = getattr(wx, 'ST_ELLIPSIZE_END', 0)
        self.status_msg_label = wx.StaticText(status_panel, label=tr('ready'), style=ellipsize_style)
        self.status_msg_label.SetForegroundColour(fg_sb)
        self.status_msg_label.SetFont(font_sb)
        status_sizer.Add(self.status_msg_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 12)
        # 필드 1: 녹화 정보 (00:00 | 0f | 0.0MB) — 최소 너비 확보로 잘림 방지
        self.info_label = wx.StaticText(status_panel, label="")
        self.info_label.SetForegroundColour(Colors.STATUS_SUCCESS)
        info_font = Fonts.get_font(Fonts.SIZE_DEFAULT, bold=True)
        self.info_label.SetFont(info_font)
        self.info_label.SetToolTip(tr('fps_tooltip'))
        info_min_w = self.info_label.GetTextExtent("00:00 | 0f | 0.0MB")[0] + 10
        self.info_label.SetMinSize((info_min_w, -1))
        status_sizer.Add(self.info_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        # 필드 2: HDR
        self.hdr_label = wx.StaticText(status_panel, label="")
        self.hdr_label.SetForegroundColour(Colors.STATUS_WARNING)
        self.hdr_label.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT, bold=True))
        self.hdr_label.SetToolTip(tr('hdr_label_tooltip'))
        hdr_min_w = self.hdr_label.GetTextExtent("HDR")[0] + 10
        self.hdr_label.SetMinSize((hdr_min_w, -1))
        status_sizer.Add(self.hdr_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        self._update_hdr_label()
        
        # HDR 상태 주기적 갱신 (2초)
        self._hdr_check_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self._update_hdr_label(), self._hdr_check_timer)
        self._hdr_check_timer.Start(2000)
        
        # 초기 상태 동기화
        self._sync_capture_control_bar_state()
        
        # 메인 패널 + 커스텀 상태바를 프레임에 설정 (상태바가 프로그레스 패널을 덮지 않도록 맨 아래에 추가)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(main_panel, 1, wx.EXPAND)
        sizer.Add(status_panel, 0, wx.EXPAND)
        self.SetSizer(sizer)

        # 자식 위젯 크기에 맞게 창 크기 자동 계산
        sizer.Fit(self)
        # Fit 결과가 최소 크기보다 작으면 최소 크기 적용
        fit_size = self.GetSize()
        self.SetSize(max(fit_size.width, MAIN_WINDOW_MIN_WIDTH),
                     max(fit_size.height, MAIN_WINDOW_MIN_HEIGHT))

        # 리사이즈 시 컨트롤 바 강제 갱신 (흔적 제거)
        self.Bind(wx.EVT_SIZE, self._on_main_size)
    
    def _on_main_size(self, event):
        """메인 창 리사이즈 시 컨트롤 바(및 자식) 강제 다시 그리기"""
        event.Skip()
        if getattr(self, 'capture_control_bar', None):
            self.capture_control_bar.Refresh(True)
    
    def retranslateUi(self, lang=None):
        """언어 변경 시 UI 업데이트"""
        self.SetTitle(f"{APP_NAME} v{VERSION}")
        if self.record_state == self.STATE_READY:
            self.status_msg_label.SetLabel(tr('ready'))
        elif self.record_state == self.STATE_RECORDING:
            self.status_msg_label.SetLabel(tr('recording'))
        elif self.record_state == self.STATE_PAUSED:
            self.status_msg_label.SetLabel(tr('paused'))
            
        self.info_label.SetToolTip(tr('fps_tooltip'))
        self.hdr_label.SetToolTip(tr('hdr_label_tooltip'))
    
    def _connect_capture_control_bar(self):
        """CaptureControlBar 이벤트 연결 (wxPython 콜백 방식)"""
        # 녹화 제어
        self.capture_control_bar.set_recording_requested_callback(self._on_rec_clicked)
        self.capture_control_bar.set_pause_clicked_callback(self._on_pause_clicked)
        self.capture_control_bar.set_stop_clicked_callback(self._on_stop_clicked)
        self.capture_control_bar.set_settings_requested_callback(self._open_settings)
        
        # 토글 설정
        self.capture_control_bar.set_cursor_toggled_callback(self._on_cursor_toggled)
        self.capture_control_bar.set_region_toggled_callback(self._on_region_toggled)
        
        # 녹화 설정
        self.capture_control_bar.set_format_changed_callback(self._on_format_changed)
        self.capture_control_bar.set_fps_changed_callback(self._on_fps_changed)
        self.capture_control_bar.set_resolution_changed_callback(self._on_resolution_preset_changed)
        self.capture_control_bar.set_quality_changed_callback(self._on_quality_changed)
    
    def _on_cursor_toggled(self, enabled: bool):
        """커서 토글 변경 처리"""
        # recorder에 즉시 반영 (녹화 중이 아닐 때)
        if self.recorder and self.record_state == self.STATE_READY:
            self.recorder.include_cursor = enabled
    
    def _on_region_toggled(self, visible: bool):
        """영역 표시 토글 변경 처리"""
        # 설정에 저장
        if not self.settings.has_section('General'):
            self.settings.add_section('General')
        self.settings.set("General", "click_highlight", "true" if visible else "false")
        
        # recorder에 즉시 반영 (녹화 중이 아닐 때)
        if self.recorder and self.record_state == self.STATE_READY:
            self.recorder.show_click_highlight = visible
    
    def _sync_capture_control_bar_state(self):
        """CaptureControlBar 상태를 기존 설정과 동기화"""
        if not hasattr(self, 'capture_control_bar') or not self.capture_control_bar:
            return
        
        # 커서 포함 상태 (기본값 True)
        cursor_enabled = True
        self.capture_control_bar.set_cursor_enabled(cursor_enabled)
        
        # 영역 표시 상태 (클릭 하이라이트)
        region_visible = self.settings.get("General", "click_highlight", fallback="false") == "true"
        self.capture_control_bar.set_region_visible(region_visible)
        
        # 저장된 설정에서 FPS, 해상도 불러오기
        saved_fps = self.settings.get("General", "fps", fallback="15")
        try:
            fps_val = int(saved_fps)
            self.capture_control_bar.set_fps(fps_val)
        except ValueError:
            self.capture_control_bar.set_fps(15)
        
        saved_resolution = self.settings.get("General", "resolution_preset", fallback="320 × 240")
        self.capture_control_bar.set_resolution(saved_resolution)
        
        # GPU 버튼 클릭 콜백 등록
        self.capture_control_bar.set_gpu_click_callback(self._on_gpu_button_click)

        # 녹화 상태
        is_recording = self.record_state == self.STATE_RECORDING
        is_paused = self.record_state == self.STATE_PAUSED
        self.capture_control_bar.set_recording_state(is_recording, is_paused)
    
    def _apply_global_style(self):
        """전역 스타일 적용 (wxPython, 밝기 0.5 테마)"""
        self.SetBackgroundColour(Colors.BG_PRIMARY)
        self.SetForegroundColour(Colors.TEXT_PRIMARY)
    
    def _create_progress_area(self, parent_layout, parent_window):
        """프로그레스 바 영역 생성 (툴바 하단 중앙). v1과 동일: 높이 20, 내부 마진 (10,2,10,0), 간격 10."""
        progress_panel = wx.Panel(parent_window)
        progress_panel.SetMinSize((-1, 20))
        progress_panel.SetSize((-1, 20))
        progress_panel.SetBackgroundColour(Colors.BG_PRIMARY)
        self._progress_panel = progress_panel
        # v1: setContentsMargins(10,2,10,0), setSpacing(10) → 상단 2px + 가로 10
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add((0, 2))  # 상단 2px
        progress_sizer = wx.BoxSizer(wx.HORIZONTAL)
        outer.Add(progress_sizer, 1, wx.EXPAND)
        progress_panel.SetSizer(outer)
        progress_sizer.AddStretchSpacer()
        progress_sizer.Add((10, 0))  # 좌측 10px
        # 프로그레스 바 (0-100, 가로형, 기본 숨김)
        self.encoding_progress_bar = wx.Gauge(
            progress_panel, range=100,
            style=wx.GA_HORIZONTAL | getattr(wx, 'GA_SMOOTH', 0)
        )
        self.encoding_progress_bar.SetMinSize((280, 16))
        self.encoding_progress_bar.SetValue(0)
        self.encoding_progress_bar.Hide()
        progress_sizer.Add(self.encoding_progress_bar, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        progress_sizer.Add((10, 0))  # 간격 10
        # 상태 레이블 (인코딩 중/완료/실패 메시지) - Windows 11 Dark Theme
        self.encoding_status_label = wx.StaticText(progress_panel, label="")
        self.encoding_status_label.SetMinSize((280, -1))
        self.encoding_status_label.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.encoding_status_label.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT, bold=True))
        progress_sizer.Add(self.encoding_status_label, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        progress_sizer.Add((10, 0))  # 우측 10px
        progress_sizer.AddStretchSpacer()
        outer.SetSizeHints(progress_panel)
        parent_layout.Add(progress_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
    
    def _create_preview_area(self, parent_layout):
        """실시간 미리보기 영역 생성 (미구현 — 스텁)"""
        self.preview_label = None
        self.preview_widget = None
    
    def _start_preview(self):
        """실시간 미리보기 시작"""
        if not self.preview_enabled:
            return
        
        if not hasattr(self, 'preview_widget') or not self.preview_widget:
            return
        
        # 기존 타이머 정리 (레이스 컨디션 방지)
        if self.preview_timer is not None:
            try:
                self.preview_timer.Stop()  # wxPython은 대문자
            except (TypeError, RuntimeError, AttributeError):
                pass
            self.preview_timer = None
        
        self.preview_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self._update_preview(), self.preview_timer)
        self.preview_timer.Start(100)  # 10 FPS 미리보기
        
        self.preview_widget.Show()
    
    def _stop_preview(self):
        """실시간 미리보기 중지"""
        from core.utils import safe_delete_timer
        if self.preview_timer:
            safe_delete_timer(self.preview_timer)
            self.preview_timer = None
        
        if hasattr(self, 'preview_widget') and self.preview_widget:
            self.preview_widget.Hide()
            if hasattr(self, 'preview_label') and self.preview_label:
                self.preview_label.SetLabel(tr('preview'))
    
    def _update_preview(self):
        """미리보기 업데이트"""
        try:
            # 안전 검증
            if not self or self.recorder is None or not self.preview_enabled:
                return
            
            if not hasattr(self, 'preview_label') or self.preview_label is None:
                return
            
            frame = self.recorder.capture_single_frame()
            
            # 프레임 유효성 검증
            if frame is None:
                return
            
            if not isinstance(frame, np.ndarray):
                logger.warning(f"Invalid frame type: {type(frame)}")
                return
            
            if len(frame.shape) < 2 or frame.size == 0:
                return
            
            # 연속적인 배열로 변환 (메모리 접근 오류 방지)
            frame = np.ascontiguousarray(frame, dtype=np.uint8)
            h, w = frame.shape[:2]
            
            # 유효한 크기 및 채널 확인
            if h <= 0 or w <= 0:
                return
            
            if len(frame.shape) < 3 or frame.shape[2] < 3:
                logger.warning(f"Invalid frame channels: {frame.shape}")
                return
            
            if h > 0 and w > 0:
                    # 미리보기 비활성화 상태
                    pass
        except (AttributeError, ValueError, TypeError, RuntimeError, wx.PyDeadObjectError) as e:
            # 예외 발생 시 로그 (미리보기 실패는 치명적이지 않음)
            logger.debug(f"미리보기 업데이트 실패: {e}")
    
    def _init_recorder(self):
        """녹화기 초기화"""
        from core import ScreenRecorder, GifEncoder
        from core.hdr_utils import is_hdr_active
        
        self.recorder = ScreenRecorder()
        self.encoder = GifEncoder()
        
        # 설정에서 캡처 백엔드 로드 및 적용
        capture_backend = self.settings.get("General", "capture_backend", fallback="gdi")  # 기본값 gdi
        
        # Auto인 경우 HDR 상태에 따라 백엔드 선택
        if capture_backend == "auto":
            hdr_active = is_hdr_active()
            # HDR 환경: GDI (색상 정확, FastGDI로 빠름)
            # SDR 환경: DXCam (고성능)
            actual_backend = "gdi" if hdr_active else "dxcam"
            logger.info(f"Auto mode: HDR {'ON' if hdr_active else 'OFF'} → {actual_backend} (FastGDI)")
            if self.recorder:
                self.recorder.set_capture_backend(actual_backend)
        else:
            # 명시적 설정 사용
            if self.recorder:
                self.recorder.set_capture_backend(capture_backend)
                logger.info(f"Capture backend set to: {capture_backend}")
        
        # 백그라운드에서 캡처 백엔드 워밍업 (앱 시작 시 자동)
        logger.info("Screen recorder initialized with pre-warming")
        
        # 오디오 녹음기 초기화 (MP4용)
        self.audio_recorder = AudioRecorder()
        self.audio_file_path = None  # 녹음된 오디오 파일 경로
        
        # 콜백 연결 (수집/캡처 스레드에서 호출되므로 wx.CallAfter로 메인 스레드에서 실행)
        self.recorder.set_frame_captured_callback(lambda n: wx.CallAfter(self._on_frame_captured, n))
        self.recorder.set_recording_stopped_callback(lambda: wx.CallAfter(self._on_recording_stopped))
        self.recorder.set_error_occurred_callback(lambda msg: wx.CallAfter(self._on_recording_error, msg))
        
        # HDR 보정 설정: 사용자 설정값만 사용 (기본 OFF)
        hdr_on = self.settings.get('General', 'hdr_correction', fallback='false') == "true"
        self.recorder.set_hdr_correction(hdr_on)
    
    # ── 의존성 관리 ──

    def _run_startup_dependency_check(self):
        """시작 시 의존성 진단 (백그라운드 감지 후 다이얼로그 표시)"""
        # 이미 진단 완료된 경우 스킵
        if self.settings.get('General', 'startup_dep_checked', fallback='false') == 'true':
            return
        from core.dependency_checker import check_all_async
        check_all_async(self._on_startup_dep_results)

    def _on_startup_dep_results(self, results):
        """시작 진단 결과 콜백"""
        from core.dependency_checker import DependencyState
        # 모두 설치됨이면 다이얼로그 표시하지 않음
        missing = [r for r in results if r.state != DependencyState.INSTALLED]
        if not missing:
            return
        from ui.startup_check_dialog import StartupCheckDialog
        dlg = StartupCheckDialog(self, results)
        dlg.ShowModal()
        dlg.Destroy()
        # 진단 완료 플래그 저장
        if not self.settings.has_section('General'):
            self.settings.add_section('General')
        self.settings.set('General', 'startup_dep_checked', 'true')
        self._save_settings_to_disk()
        # FFmpeg 설치 후 인코더 경로 갱신
        if self.encoder:
            self.encoder.refresh_ffmpeg_path()
        # CuPy가 여전히 미설치이면 CPU 모드 안내
        cupy_missing = any(r.name == "CuPy" and r.state != DependencyState.INSTALLED for r in results)
        if cupy_missing:
            self.status_msg_label.SetLabel(tr('cupy_cpu_mode_notice').split('\n')[0])

    def _check_dep_for_feature(self, dep_name, skip_flag_key, feature_desc, disable_label=None):
        """기능 선택 시 의존성 확인 통합 헬퍼

        Returns:
            True=사용 가능 (설치됨 또는 설치 성공), False=사용 불가
        """
        # skip 플래그 확인
        if self.settings.get('General', skip_flag_key, fallback='false') == 'true':
            return False  # 이전에 "다시 묻지 않기" 선택 → 대안 사용

        # 동기 감지 (각 <100ms)
        from core.dependency_checker import check_ffmpeg, check_cupy, check_dxcam, DependencyState
        checkers = {"FFmpeg": check_ffmpeg, "CuPy": check_cupy, "dxcam": check_dxcam}
        check_fn = checkers.get(dep_name)
        if not check_fn:
            return True
        status = check_fn()
        if status.state == DependencyState.INSTALLED:
            return True

        # 3버튼 모달 표시
        from ui.dependency_dialogs import (
            DependencyInstallDialog, ID_INSTALL, ID_DISABLE, ID_CANCEL_DEP,
            show_install_flow,
        )
        dlg = DependencyInstallDialog(self, status, feature_desc, disable_label)
        ret = dlg.ShowModal()
        dont_ask = dlg.dont_ask_again
        dlg.Destroy()

        if dont_ask:
            if not self.settings.has_section('General'):
                self.settings.add_section('General')
            self.settings.set('General', skip_flag_key, 'true')
            self._save_settings_to_disk()

        if ret == ID_INSTALL.GetId():
            success = show_install_flow(self, dep_name, status, self.settings)
            if success and self.encoder:
                self.encoder.refresh_ffmpeg_path()
            return success
        # ID_DISABLE 또는 ID_CANCEL_DEP
        return False

    def _save_settings_to_disk(self):
        """config.ini에 설정 저장"""
        try:
            from core.utils import APP_SETTINGS_NAME
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            config_dir = os.path.join(appdata, APP_SETTINGS_NAME)
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, 'config.ini')
            with open(config_path, 'w', encoding='utf-8') as f:
                self.settings.write(f)
        except Exception as e:
            logger.warning("설정 저장 실패: %s", e)
    
    def _show_capture_overlay(self):
        """캡처 오버레이 표시"""
        from ui.capture_overlay import CaptureOverlay

        # MainWindow C++ 객체가 이미 삭제되었으면 무시
        try:
            if not self or not self.GetHandle():
                return
        except RuntimeError:
            return

        if self.capture_overlay is None:
            self.capture_overlay = CaptureOverlay(self)
            
            # 영역 변경 콜백 연결
            self.capture_overlay.set_region_changed_callback(self._on_region_changed)
            # 닫힘 콜백 연결
            self.capture_overlay.set_closed_callback(self._on_overlay_closed)
            
            # 저장된 해상도 적용 (없으면 기본 320x240)
            saved_resolution = self.settings.get("General", "resolution_preset", fallback="320 × 240")
            try:
                clean_text = saved_resolution.replace("×", "x").replace(" ", "").lower()
                if "x" in clean_text:
                    parts = clean_text.split("x")
                    w, h = int(parts[0]), int(parts[1])
                    self.capture_overlay.set_capture_size(w, h)
                else:
                    self.capture_overlay.set_capture_size(320, 240)
            except (ValueError, IndexError):
                self.capture_overlay.set_capture_size(320, 240)
        
        # 메인 윈도우 하단에 위치
        self._position_overlay_below_window()
        self.capture_overlay.Show()
        self.capture_overlay.Raise()  # 항상 최상위로
    
    def _position_overlay_below_window(self):
        """캡처 오버레이를 메인 윈도우 하단에 위치"""
        if self.capture_overlay:
            main_rect = self.GetRect()
            overlay_rect = self.capture_overlay.GetRect()
            
            # 메인 윈도우 바로 아래, 왼쪽 정렬
            new_x = main_rect.x
            new_y = main_rect.y + main_rect.height + 5
            
            self.capture_overlay.SetPosition((new_x, new_y))
    
    def OnMove(self, event):
        """메인 윈도우 이동 시 오버레이도 같은 방향으로 이동 (델타 기반)"""
        event.Skip()
        current_pos = self.GetPosition()
        if self._last_pos is None:
            self._last_pos = current_pos
            return
        if self.capture_overlay and self.capture_overlay.IsShown():
            if self.record_state == self.STATE_READY:
                dx = current_pos.x - self._last_pos.x
                dy = current_pos.y - self._last_pos.y
                if dx != 0 or dy != 0:
                    overlay_pos = self.capture_overlay.GetPosition()
                    self.capture_overlay.SetPosition((overlay_pos.x + dx, overlay_pos.y + dy))
        self._last_pos = current_pos

    def _on_region_changed(self, x, y, w, h):
        """캡처 영역 변경됨"""
        if self.recorder is not None:
            self.recorder.set_region(x, y, w, h)

        # 순환 호출 방지
        if getattr(self, '_updating_resolution', False):
            return
        self._updating_resolution = True
        try:
            # 논리적 크기를 사용해서 표시 (DPI 스케일링 전)
            if self.capture_overlay:
                logical_w, logical_h = self.capture_overlay.get_capture_size()
                size_text = f"{logical_w} × {logical_h}"
            else:
                size_text = f"{w} × {h}"

            if hasattr(self, 'capture_control_bar'):
                self.capture_control_bar.set_resolution(size_text)
        finally:
            self._updating_resolution = False
        
        # 마지막 크기 저장
        if not self.settings.has_section('General'):
            self.settings.add_section('General')
        self.settings.set("General", "resolution_preset", size_text)
    
    def _on_fps_changed(self, text):
        """FPS 값 변경됨"""
        if text:
            if not self.settings.has_section('General'):
                self.settings.add_section('General')
            self.settings.set("General", "fps", text)
    
    def _on_format_changed(self, format_text):
        """출력 포맷 변경 시 FPS 자동 조정 + FFmpeg 인터셉트"""
        if hasattr(self, 'capture_control_bar') and self.capture_control_bar:
            if format_text == "GIF":
                self.capture_control_bar.set_fps(15)
            elif format_text == "MP4":
                # FFmpeg 확인
                from core.ffmpeg_installer import FFmpegManager
                if not FFmpegManager.is_available():
                    available = self._check_dep_for_feature(
                        "FFmpeg", "skip_ffmpeg_check",
                        tr('dep_ffmpeg_required_for_record'),
                        disable_label=tr('dep_use_gif_instead'),
                    )
                    if not available:
                        # GIF로 되돌리기
                        wx.CallAfter(self.capture_control_bar.set_format, "GIF")
                        return
                self.capture_control_bar.set_fps(30)
    
    def _on_resolution_preset_changed(self, text):
        """해상도 프리셋 변경됨"""
        if getattr(self, '_updating_resolution', False):
            return

        if not self.settings.has_section('General'):
            self.settings.add_section('General')
        self.settings.set("General", "resolution_preset", text)

        # 해상도 파싱 후 CallAfter로 비동기 적용
        # (콤보박스 이벤트 처리 중 오버레이 크기 변경 시 크래시 방지)
        try:
            clean_text = text.replace("×", "x").replace(" ", "").lower()
            if "x" in clean_text:
                parts = clean_text.split("x")
                w, h = int(parts[0]), int(parts[1])
                if w > 0 and h > 0:
                    wx.CallAfter(self._apply_resolution, w, h)
        except Exception as e:
            logger.error(f"Resolution preset change error: {e}", exc_info=True)

    def _apply_resolution(self, w, h):
        """해상도를 오버레이에 비동기 적용"""
        try:
            if self.capture_overlay is None:
                self._show_capture_overlay()
            if self.capture_overlay:
                self._updating_resolution = True
                try:
                    self.capture_overlay.set_capture_size(w, h)
                finally:
                    self._updating_resolution = False
        except Exception as e:
            logger.error(f"Apply resolution error: {e}", exc_info=True)
    
    def _on_quality_changed(self, index: int):
        """품질 변경됨"""
        # 품질 설정은 저장하지 않음 (기본값 사용)
        pass
    
    def _on_overlay_closed(self):
        """오버레이 창 닫힘"""
        # 참조 제거
        self.capture_overlay = None
        
        # 편집 모드에서는 오버레이 재생성 안함
        if self._editor_mode:
            return
        # 오버레이가 닫히면 다시 표시
        if self.record_state == self.STATE_READY:
            wx.CallLater(100, self._show_capture_overlay)
    
    def _open_settings(self):
        """설정 다이얼로그 열기"""
        from .settings_dialog import SettingsDialog
        
        dialog = SettingsDialog(self, self.settings)
        try:
            if dialog.ShowModal() == wx.ID_OK:
                # 설정 변경사항 반영
                self._apply_settings()
        finally:
            dialog.Destroy()
    
    def _apply_settings(self):
        """설정 변경사항을 recorder에 반영"""
        try:
            
            # 워터마크
            if self.recorder and self.recorder.watermark:
                watermark_enabled = self.settings.get("General", "watermark", fallback="false") == "true"
                self.recorder.watermark.set_enabled(watermark_enabled)
            
            # 키보드 입력 표시
            if self.recorder and self.recorder.keyboard_display:
                keyboard_enabled = self.settings.get("General", "keyboard_display", fallback="false") == "true"
                if keyboard_enabled:
                    if not self.recorder.keyboard_display.is_available():
                        wx.MessageBox(tr('keyboard_unavailable'), tr('warning'), wx.OK | wx.ICON_WARNING)
                        if not self.settings.has_section('General'):
                            self.settings.add_section('General')
                        self.settings.set("General", "keyboard_display", "false")
                        return
                self.recorder.keyboard_display.set_enabled(keyboard_enabled)
            
            # 실시간 미리보기
            preview_enabled = self.settings.get("General", "preview_enabled", fallback="false") == "true"
            if preview_enabled != self.preview_enabled:
                self.preview_enabled = preview_enabled
                if preview_enabled:
                    self._start_preview()
                else:
                    self._stop_preview()
            
            # HDR 보정 설정 반영
            hdr_on = self.settings.get("General", "hdr_correction", fallback="false") == "true"
            if self.recorder:
                self.recorder.set_hdr_correction(hdr_on)
            self._update_hdr_label()
        except Exception as e:
            logger.warning("설정 적용 오류: %s", e)
    
    def _on_start_btn_clicked(self, event):
        """녹화 시작 버튼 클릭 (wxPython 이벤트)"""
        self._on_rec_clicked()
    
    def _on_stop_btn_clicked(self, event):
        """녹화 중지 버튼 클릭 (wxPython 이벤트)"""
        self._on_stop_clicked()
    
    def _on_rec_clicked(self):
        """REC/STOP 토글 버튼 클릭"""
        try:
            if self.record_state == self.STATE_READY:
                self._start_recording()
            elif self.record_state == self.STATE_RECORDING:
                self._stop_recording()
            elif self.record_state == self.STATE_PAUSED:
                self._resume_recording()
        except Exception as e:
            wx.MessageBox(tr('start_failed').format(str(e)), tr('error'), wx.OK | wx.ICON_ERROR)
            logger.warning("REC 버튼 클릭 오류: %s", e)
    
    def _on_pause_clicked(self):
        """PAUSE 버튼 클릭"""
        if self.record_state == self.STATE_RECORDING:
            self._pause_recording()
    
    def _on_stop_clicked(self):
        """중지 버튼 클릭 처리"""
        if self.record_state != self.STATE_READY:
            self.status_msg_label.SetLabel(tr('recording'))  # Showing as finishing
            self._stop_recording()
    
    def _start_recording(self):
        """녹화 시작"""
        # 녹화 중이면 무시
        if self.record_state != self.STATE_READY:
            logger.warning("Cannot start recording: already recording")
            return

        # recorder 확인
        if self.recorder is None:
            logger.error("Recorder not initialized")
            wx.MessageBox(tr('recorder_not_init'), tr('warning'), wx.OK | wx.ICON_WARNING)
            return

        # MP4 포맷인데 FFmpeg 없으면 녹화 차단
        if hasattr(self, 'capture_control_bar') and self.capture_control_bar:
            fmt = self.capture_control_bar.get_format()
            if fmt == "MP4":
                from core.ffmpeg_installer import FFmpegManager
                if not FFmpegManager.is_available():
                    available = self._check_dep_for_feature(
                        "FFmpeg", "skip_ffmpeg_check",
                        tr('dep_ffmpeg_required_for_record'),
                        disable_label=tr('dep_use_gif_instead'),
                    )
                    if not available:
                        wx.CallAfter(self.capture_control_bar.set_format, "GIF")
                        return
                    elif self.encoder:
                        self.encoder.refresh_ffmpeg_path()

        # 녹화 영역 확인
        if self.capture_overlay is None:
            logger.error("Capture overlay not initialized")
            wx.MessageBox(tr('region_not_set'), tr('warning'), wx.OK | wx.ICON_WARNING)
            return
        
        # 녹화 시작 전 현재 오버레이 위치로 캡처 영역 업데이트
        x, y, w, h = self.capture_overlay.get_capture_region()
        self.recorder.set_region(x, y, w, h)
        logger.info(f"Capture region set to: ({x}, {y}, {w}x{h})")
        
        # 영역 유효성 검증
        try:
            region = self.recorder.region
            if not region or len(region) != 4:
                raise ValueError("Invalid region format")
            x, y, w, h = region
            if w <= 0 or h <= 0:
                raise ValueError(f"Invalid region size: {w}x{h}")
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid capture region: {e}")
            wx.MessageBox("캡처 영역이 유효하지 않습니다. 영역을 다시 설정해주세요.", tr('warning'), wx.OK | wx.ICON_WARNING)
            return
        
        # capture_control_bar에서 설정값 가져오기
        if hasattr(self, 'capture_control_bar') and self.capture_control_bar:
            fps = self.capture_control_bar.get_fps()
            include_cursor = self.capture_control_bar.cursor_toggle.IsChecked()
            show_click_highlight = self.capture_control_bar.region_toggle.IsChecked()
        else:
            fps = 15
            include_cursor = True
            show_click_highlight = False
        
        self.recorder.fps = fps
        self.recorder.include_cursor = include_cursor
        self.recorder.show_click_highlight = show_click_highlight
        
        # 메모리 경고 플래그 및 프레임 크기 캐시 초기화
        if hasattr(self, '_memory_warned'):
            del self._memory_warned
        if hasattr(self, '_system_memory_warned'):
            del self._system_memory_warned
        if hasattr(self, '_zero_frame_warned'):
            del self._zero_frame_warned
        self._cached_frame_size = None  # 프레임 크기 캐시 초기화
        
        # 프레임 버퍼 명시적 초기화 (이전 녹화 참조 제거)
        self.frames = []
        
        self.record_state = self.STATE_RECORDING
        self._update_button_states()
        
        # 녹화 중 UI 비활성화
        if hasattr(self, 'include_cursor_cb') and self.include_cursor_cb:
            self.include_cursor_cb.Enable(False)
        
        # 캡처 영역 오버레이 처리
        if self.capture_overlay:
            # 녹화 모드 활성화 (30% 투명도)
            self.capture_overlay.set_recording_mode(True)
            self.capture_overlay.set_movable(False)
        
        # 녹화 시작 (오버레이 처리 후)
        wx.CallLater(50, self._do_start_recording)
    
    def _do_start_recording(self):
        """실제 녹화 시작 (오버레이 숨김 후)"""
        
        # 백엔드 설정: 매 녹화 시작 시 설정값 적용
        user_backend = str(self.settings.get("General", "capture_backend", fallback="gdi"))
        if self.recorder:
            if user_backend == "auto":
                # Auto 모드: HDR 상태에 따라 백엔드 선택
                from core.hdr_utils import is_hdr_active
                hdr_active = is_hdr_active()
                backend = "gdi" if hdr_active else "dxcam"
                self.recorder.set_capture_backend(backend)
                logger.info(f"[Auto] HDR {'ON' if hdr_active else 'OFF'} → {backend}")
            elif user_backend in ["dxcam", "gdi"]:
                # 명시적 설정 적용
                self.recorder.set_capture_backend(user_backend)
                logger.info(f"[Manual] 백엔드 설정 적용: {user_backend}")
        
        # 워터마크, 키보드 표시 설정 적용 (녹화 시작 전)
        try:
            if self.recorder and self.recorder.watermark:
                watermark_enabled = self.settings.get("General", "watermark", fallback="false") == "true"
                self.recorder.watermark.set_enabled(watermark_enabled)
        except (AttributeError, RuntimeError) as e:
            logger.error(f"Watermark setup failed: {e}")
        
        try:
            if self.recorder and self.recorder.keyboard_display:
                keyboard_enabled = self.settings.get("General", "keyboard_display", fallback="false") == "true"
                if keyboard_enabled and not self.recorder.keyboard_display.is_available():
                    wx.MessageBox(tr('keyboard_unavailable'), tr('warning'), wx.OK | wx.ICON_WARNING)
                    if not self.settings.has_section('General'):
                        self.settings.add_section('General')
                    self.settings.set("General", "keyboard_display", "false")
                    keyboard_enabled = False
                self.recorder.keyboard_display.set_enabled(keyboard_enabled)
        except (AttributeError, RuntimeError) as e:
            logger.error(f"Keyboard display setup failed: {e}")
        
        # 녹화 시작 (에러 처리)
        try:
            self.recorder.start_recording()
            
            # 녹화가 실제로 시작되었는지 확인
            if not self.recorder.is_recording:
                raise RuntimeError("녹화 시작 실패: recorder.is_recording = False")
            
            # 백엔드가 이미 워밍업되었는지 확인
            backend_ready = getattr(self.recorder, '_backend_warmed_up', False)
            
            if backend_ready:
                # 백엔드가 이미 준비됨 - 즉시 활성화
                self.status_msg_label.SetLabel(tr('recording'))
                logger.info("Backend pre-warmed, recording ready immediately")
            else:
                # 백엔드 준비 안 됨 - 짧은 대기 (500ms)
                self.status_msg_label.SetLabel(tr('recording') + " - 초기화 중...")

                # 500ms 후 상태 메시지 업데이트
                def _on_backend_ready():
                    if self.record_state == self.STATE_RECORDING:
                        self.status_msg_label.SetLabel(tr('recording'))

                wx.CallLater(500, _on_backend_ready)
                logger.info("Backend not pre-warmed, using 500ms delay")
            
            # 기존 타이머 정리 (안전)
            from core.utils import safe_delete_timer
            if self.record_timer is not None:
                safe_delete_timer(self.record_timer)
            
            # 녹화 시간 타이머 생성
            self.record_timer = wx.Timer(self)
            self.record_elapsed = 0
            self.Bind(wx.EVT_TIMER, lambda e: self._update_record_time(), self.record_timer)
            self.record_timer.Start(1000)
        except Exception as e:
            # 녹화 시작 실패 시 상태 복원
            self.record_state = self.STATE_READY
            self._update_button_states()
            if hasattr(self, 'include_cursor_cb') and self.include_cursor_cb:
                self.include_cursor_cb.Enable(True)
            
            # 오디오 녹음 중지 및 정리
            if hasattr(self, 'audio_recorder') and self.audio_recorder and self.audio_recorder.is_recording():
                self.audio_recorder.stop()
                self.audio_recorder.cleanup()
            
            # 오버레이 복원
            if self.capture_overlay:
                self.capture_overlay.set_recording_mode(False)
                self.capture_overlay.set_movable(True)
            
            error_msg = tr("start_failed").format(str(e))
            wx.MessageBox(error_msg, tr("error"), wx.OK | wx.ICON_ERROR)
            self.status_msg_label.SetLabel(tr("save_failed"))
            logger.warning("녹화 시작 오류: %s", e)
    
    def _pause_recording(self):
        """녹화 일시정지"""
        if self.recorder is None:
            return
        self.recorder.pause_recording()
        self.record_state = self.STATE_PAUSED
        self._update_button_states()
        
        # 캡처 영역 오버레이 표시 (녹화 모드 해제, 이동만 가능)
        if self.capture_overlay:
            self.capture_overlay.set_recording_mode(False)
            self.capture_overlay.set_movable(True, allow_resize=False)
            self.capture_overlay.Show()
            self.capture_overlay.Raise()  # 항상 최상위로
        
        self.status_msg_label.SetLabel(tr('paused'))
    
    def _resume_recording(self):
        """녹화 재개"""
        self.record_state = self.STATE_RECORDING
        self._update_button_states()
        
        # 캡처 영역 오버레이 처리 (녹화 모드 활성화)
        if self.capture_overlay:
            self.capture_overlay.set_recording_mode(True)
            self.capture_overlay.set_movable(False)
        
        # 오버레이 처리 후 녹화 재개
        wx.CallLater(50, self._do_resume_recording)
    
    def _do_resume_recording(self):
        """실제 녹화 재개 (오버레이 숨김 후)"""
        if self.recorder is None:
            return
        self.recorder.resume_recording()
        self.status_msg_label.SetLabel(tr('recording'))
    
    def _stop_recording(self):
        """녹화 중지"""
        # 이미 녹화가 중지된 상태면 중복 실행 방지
        if self.record_state == self.STATE_READY:
            return

        # 녹화 타이머 안전하게 중지
        from core.utils import safe_delete_timer
        if self.record_timer is not None:
            safe_delete_timer(self.record_timer)
            self.record_timer = None

        self.record_state = self.STATE_READY
        self._update_button_states()
        
        # 오디오 녹음 중지 (MP4 모드) - 안전
        self.audio_file_path = None
        try:
            if self.audio_recorder and self.audio_recorder.is_recording():
                self.audio_file_path = self.audio_recorder.stop()
        except (AttributeError, RuntimeError) as e:
            logger.error(f"Audio recording stop failed: {e}")
        
        # 녹화 중지
        if self.recorder is not None:
            self.frames = self.recorder.stop_recording()
        else:
            self.frames = []
        
        # 캡처 영역 오버레이 다시 표시 (녹화 모드 해제)
        if self.capture_overlay:
            self.capture_overlay.set_recording_mode(False)
            self.capture_overlay.set_movable(True, allow_resize=True)
            self.capture_overlay.Show()
            self.capture_overlay.Raise()  # 항상 최상위로
        
        # 프레임 수 확인 및 로깅
        frame_count = len(self.frames) if self.frames else 0
        logger.info(f"Recording stopped with {frame_count} frames")
        
        # 성능 경고 체크 (실제 FPS가 목표의 70% 미만일 때)
        if frame_count > 0 and hasattr(self.recorder, 'actual_fps') and self.recorder.actual_fps:
            target_fps = self.recorder.fps
            actual_fps = self.recorder.actual_fps
            if actual_fps < target_fps * 0.7:
                wx.MessageBox(
                    tr('low_fps_warning_msg').format(actual_fps=actual_fps, target_fps=target_fps),
                    tr('low_fps_warning_title'),
                    wx.OK | wx.ICON_WARNING
                )
        
        if frame_count > 0:
            # 현재 출력 포맷 확인
            output_format = self.capture_control_bar.get_format() if hasattr(self, 'capture_control_bar') else "GIF"
            
            if output_format == "MP4":
                # MP4는 편집 불가 → 바로 저장으로 이동
                self._save_gif()
            else:
                # GIF는 저장/편집/삭제 선택 다이얼로그 표시
                self._show_save_edit_dialog(frame_count)
        else:
            # 프레임이 없는 이유 로깅
            logger.warning("No frames captured during recording")
            wx.MessageBox(
                tr('no_frames') + "\n\n" + 
                "녹화 시간이 너무 짧았거나 캡처 프로세스 초기화가 늦어졌을 수 있습니다.\n" +
                "최소 1초 이상 녹화를 유지해주세요.",
                tr("warning"),
                wx.OK | wx.ICON_WARNING
            )
            self._reset_ui()
    
    def _show_save_edit_dialog(self, frame_count: int):
        """녹화 완료 후 저장/편집/삭제 선택 다이얼로그 표시"""
        # 커스텀 다이얼로그 생성
        dlg = wx.MessageDialog(
            self,
            tr('recording_complete_msg').format(frame_count),
            tr('recording_complete'),
            wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION
        )
        dlg.SetYesNoCancelLabels(tr('save_now'), tr('edit_now'), tr('discard'))
        
        result = dlg.ShowModal()
        dlg.Destroy()
        
        if result == wx.ID_YES:
            # 저장 선택
            self._save_gif()
        elif result == wx.ID_NO:
            # 편집 선택 - GifEditor 열기
            self._open_editor_with_frames()
        else:
            # 삭제 선택
            self.frames = []
            if self.recorder:
                self.recorder.clear_frames()
            self._reset_ui()
    
    def _open_editor_with_frames(self):
        """녹화된 프레임으로 GifEditor 열기
        
        NOTE: editor 모듈은 wxPython 기반입니다.
        임시 GIF를 저장하고 별도 프로세스로 editor를 실행합니다.
        """
        from PIL import Image
        import tempfile
        
        try:
            self.status_msg_label.SetLabel(tr('opening_editor'))
            
            # FPS 가져오기
            try:
                if hasattr(self, 'capture_control_bar') and self.capture_control_bar:
                    fps = self.capture_control_bar.get_fps()
                else:
                    fps = 15
            except (ValueError, TypeError):
                fps = 15
            
            delay_ms = int(1000 / fps)
            frame_count = len(self.frames) if self.frames else 0
            
            if frame_count == 0:
                wx.MessageBox(tr('no_frames'), tr('warning'), wx.OK | wx.ICON_WARNING)
                self._reset_ui()
                return
            
            # PIL 이미지 리스트로 변환
            pil_frames = []
            logger.info(f"변환 시작: self.frames 개수 = {len(self.frames)}")
            for i, np_frame in enumerate(self.frames):
                if np_frame is None:
                    logger.warning(f"프레임 {i}: None")
                    continue
                if np_frame.size == 0:
                    logger.warning(f"프레임 {i}: size=0")
                    continue
                if np_frame is not None and np_frame.size > 0:
                    if len(np_frame.shape) == 3 and np_frame.shape[2] == 3:
                        np_frame_rgb = np_frame[:, :, ::-1]
                        pil_image = Image.fromarray(np_frame_rgb, 'RGB')
                    elif len(np_frame.shape) == 3 and np_frame.shape[2] == 4:
                        np_frame_rgba = np_frame[:, :, [2, 1, 0, 3]]
                        pil_image = Image.fromarray(np_frame_rgba, 'RGBA').convert('RGB')
                    else:
                        logger.warning(f"프레임 {i}: 잘못된 shape {np_frame.shape}")
                        continue
                    pil_frames.append(pil_image)

            logger.info(f"변환 완료: pil_frames 개수 = {len(pil_frames)}")

            if not pil_frames:
                wx.MessageBox(tr('no_frames'), tr('warning'), wx.OK | wx.ICON_WARNING)
                self._reset_ui()
                return
            
            # 임시 GIF 파일로 저장
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, 'xgif_temp_edit.gif')
            
            pil_frames[0].save(
                temp_path,
                save_all=True,
                append_images=pil_frames[1:],
                duration=delay_ms,
                loop=0
            )
            
            logger.info(f"Temp GIF saved to: {temp_path}")
            
            # 기존 프레임 메모리 해제
            self.frames = []
            if self.recorder:
                self.recorder.clear_frames()
            
            # 같은 프로세스 내에서 에디터 창 열기 (PyInstaller 빌드 호환)
            try:
                from editor.ui.editor_main_window_wx import MainWindow as EditorMainWindow
                editor_window = EditorMainWindow()
                editor_window.open_file(temp_path)
                editor_window.Show()
                logger.info(f"Editor launched with {frame_count} frames, closing recorder")
                # 에디터 열렸으면 레코더 종료
                self.Close()
                return
            except Exception as e:
                logger.error(f"Failed to launch editor: {e}")
                wx.MessageBox(
                    f"편집기 실행에 실패했습니다.\n\n임시 파일 위치:\n{temp_path}",
                    tr('warning'),
                    wx.OK | wx.ICON_WARNING
                )

            self._reset_ui()
            
        except Exception as e:
            logger.error(f"Failed to open editor: {e}")
            import traceback
            traceback.print_exc()
            wx.MessageBox(
                f"편집기를 여는 중 오류가 발생했습니다:\n{e}\n\n대신 저장하시겠습니까?",
                tr('error'),
                wx.OK | wx.ICON_ERROR
            )
            # 실패 시 저장으로 대체
            self._save_gif()

    def _update_button_states(self):
        """버튼 상태 업데이트"""
        # CaptureControlBar 상태 업데이트
        is_recording = self.record_state == self.STATE_RECORDING
        is_paused = self.record_state == self.STATE_PAUSED
        if hasattr(self, 'capture_control_bar') and self.capture_control_bar:
            self.capture_control_bar.set_recording_state(is_recording, is_paused)
    
    def _update_record_time(self):
        """녹화 시간 업데이트"""
        try:
            # 녹화 중이 아니면 무시
            if self.record_state != self.STATE_RECORDING:
                return
            
            # recorder가 None이면 무시
            if self.recorder is None:
                return
            
            # 위젯 삭제 체크
            if not self or not hasattr(self, 'info_label') or not self.info_label:
                return
            
            self.record_elapsed += 1
            minutes = self.record_elapsed // 60
            seconds = self.record_elapsed % 60
            frame_count = self.recorder.get_frame_count()
            
            # 메모리 사용량 계산 (프레임 데이터 크기) - 최적화: 캐시된 프레임 크기 사용
            memory_mb = 0.0
            try:
                if frame_count > 0:
                    # 캐시가 없으면 get_estimated_size_mb 사용
                    if self._cached_frame_size is None:
                        estimated_mb = self.recorder.get_estimated_size_mb()
                        if estimated_mb > 0 and frame_count > 0:
                            self._cached_frame_size = (estimated_mb * 1024 * 1024) / frame_count
                        else:
                            self._cached_frame_size = 0
                    
                    if self._cached_frame_size and self._cached_frame_size > 0:
                        memory_mb = (self._cached_frame_size * frame_count) / (1024 * 1024)
            except (ZeroDivisionError, ValueError, TypeError) as e:
                logger.warning(f"Memory calculation error: {e}")
                memory_mb = 0.0
            
            # 사용자 설정 메모리 제한 확인
            max_mem_mb = int(self.settings.get("General", "memory_limit_mb", fallback="1024"))
            
            # 메모리 임계값 도달 시 강제 중지
            if memory_mb >= max_mem_mb:
                wx.CallAfter(wx.MessageBox, tr('mem_limit_msg').format(max_mem_mb), tr('mem_limit_reached'), wx.OK | wx.ICON_WARNING)
                wx.CallAfter(self._stop_recording)
                return

            # 시스템 전체 메모리 확인 (psutil 사용 가능한 경우)
            if HAS_PSUTIL:
                try:
                    # 가용 메모리가 임계값 미만이면 강제 중지 (매우 위험한 수준)
                    available_mem_mb = psutil.virtual_memory().available / (1024 * 1024)
                    if available_mem_mb < SYSTEM_MEMORY_CRITICAL_MB:
                        if not hasattr(self, '_system_memory_warned') or not self._system_memory_warned:
                            self._system_memory_warned = True
                            wx.CallAfter(wx.MessageBox, tr('system_memory_low').format(available_mem_mb), tr('warning'), wx.OK | wx.ICON_WARNING)
                            wx.CallAfter(self._stop_recording)
                            return
                except Exception:
                    pass

            # 메모리 경고 (임계값 비율 초과 시)
            if memory_mb > max_mem_mb * MEMORY_WARNING_RATIO and not hasattr(self, '_memory_warned'):
                self._memory_warned = True
                if hasattr(self, 'status_msg_label') and self.status_msg_label:
                    self.status_msg_label.SetLabel(tr('mem_warning').format(memory_mb, max_mem_mb))
            
            # 오디오 버퍼 상한 도달 시 녹화 중지 (메모리 안전성)
            if hasattr(self, 'audio_recorder') and self.audio_recorder and self.audio_recorder.buffer_limit_reached:
                wx.CallAfter(wx.MessageBox, tr('audio_buffer_limit_reached'), tr('warning'), wx.OK | wx.ICON_WARNING)
                wx.CallAfter(self._stop_recording)
                return
            
            # 녹화 시작 후 3초 이상 프레임이 0개면 한 번만 경고 (캡처 백엔드 실패 가능성)
            if self.record_elapsed >= 3 and frame_count == 0 and not getattr(self, '_zero_frame_warned', False):
                self._zero_frame_warned = True
                if hasattr(self, 'status_msg_label') and self.status_msg_label:
                    self.status_msg_label.SetLabel(tr('capture_no_frames_warning'))
            
            rec_info = f"{minutes:02d}:{seconds:02d} | {frame_count}f | {memory_mb:.1f}MB"
            if hasattr(self, 'info_label') and self.info_label:
                self.info_label.SetLabel(rec_info)
        except (RuntimeError, AttributeError, wx.PyDeadObjectError) as e:
            # 위젯이 삭제된 경우 조용히 무시
            logger.debug(f"Timer callback error (widget deleted?): {e}")
    
    def _on_frame_captured(self, frame_num):
        """프레임 캡처됨"""
        pass
    
    def _on_recording_stopped(self):
        """녹화 중지됨 (비동기 - 레코더 자체에서 중지 시 호출)

        주의: UI의 Stop 버튼이 이미 _stop_recording을 직접 호출한 경우,
        recorder.stop_recording() 내부의 _emit_recording_stopped()로 이 콜백이
        다시 호출될 수 있음. record_state 체크로 중복 호출 방지.
        """
        if self.record_state != self.STATE_READY:
            wx.CallAfter(self._stop_recording)
    
    def _save_gif(self):
        """GIF 또는 MP4 저장"""
        # 인코딩 진행 중인지 확인
        if self.encoding_thread is not None and self.encoding_thread.is_alive():
            wx.MessageBox(tr('encoding') + "...", tr('warning'), wx.OK | wx.ICON_WARNING)
            return
        
        # 프레임 유효성 검증
        if not self.frames or len(self.frames) == 0:
            logger.error("No frames to encode")
            wx.MessageBox("인코딩할 프레임이 없습니다.", tr('warning'), wx.OK | wx.ICON_WARNING)
            self._reset_ui()
            return
        
        # 프레임 스냅샷 생성 (타이밍 이슈 방지)
        # 파일 다이얼로그가 모달로 표시되는 동안 _on_encoding_finished가
        # wx.CallAfter로 실행되어 self.frames를 비울 수 있으므로,
        # 현재 프레임 리스트의 복사본을 미리 생성
        frames_snapshot = list(self.frames)
        
        # encoder 확인
        if self.encoder is None:
            logger.error("Encoder not initialized")
            wx.MessageBox("인코더가 초기화되지 않았습니다.", tr('error'), wx.OK | wx.ICON_ERROR)
            self._reset_ui()
            return
        
        # 출력 포맷 확인
        if hasattr(self, 'capture_control_bar') and self.capture_control_bar:
            output_format = self.capture_control_bar.get_format().lower()
        else:
            output_format = 'gif'
        
        # 마지막 저장 경로 불러오기 (디렉토리만)
        last_dir = self.settings.get("General", "last_save_dir", fallback="")
        
        # 포맷에 따른 파일 다이얼로그
        if output_format == 'mp4':
            file_filter = "MP4 " + tr('file') + " (*.mp4)|*.mp4"
            file_ext = '.mp4'
            dialog_title = tr('save_mp4')
        else:
            file_filter = "GIF " + tr('file') + " (*.gif)|*.gif"
            file_ext = '.gif'
            dialog_title = tr('save_gif')
        
        with wx.FileDialog(self, dialog_title, last_dir, "", file_filter,
                          wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                self._reset_ui()
                return
            file_path = dlg.GetPath()
        
        if not file_path:
            self._reset_ui()
            return
        
        # 기존 확장자 제거 후 올바른 확장자 추가
        base_path = file_path
        for ext in ['.gif', '.mp4', '.GIF', '.MP4']:
            if file_path.endswith(ext):
                base_path = file_path[:-len(ext)]
                break
        file_path = base_path + file_ext
        
        # 저장 디렉토리 기억
        if not self.settings.has_section('General'):
            self.settings.add_section('General')
        self.settings.set("General", "last_save_dir", os.path.dirname(file_path))
        
        # 품질 설정
        if hasattr(self, 'capture_control_bar') and self.capture_control_bar:
            quality = self.capture_control_bar.get_quality()
        else:
            quality = 0
        quality_map = ['high', 'medium', 'low']
        self.encoder.set_quality(quality_map[quality])
        
        # 내장 프로그레스 바 표시
        format_name = output_format.upper()
        if self.encoding_progress_bar:
            self.encoding_progress_bar.SetValue(0)
            self.encoding_progress_bar.Show()
        if self.encoding_status_label:
            self.encoding_status_label.SetLabel(tr('encoding').format(format_name))
            self.encoding_status_label.SetForegroundColour(Colors.ENCODING_PROGRESS)
        self.status_msg_label.SetLabel(tr('encoding').format(format_name))
        if getattr(self, '_progress_panel', None):
            self._progress_panel.Layout()
            self._progress_panel.Refresh()
        
        # 인코딩 스레드 시작 (MP4인 경우 오디오 파일 경로 전달)
        # MP4의 경우 실제 캡처된 FPS 사용 (정확한 재생 속도)
        if output_format == 'mp4' and hasattr(self.recorder, 'actual_fps') and self.recorder.actual_fps:
            fps = round(self.recorder.actual_fps)
            logger.info(f"[MP4] Using actual captured FPS: {fps} (target was {self.recorder.fps})")
        else:
            # capture_control_bar에서 FPS 가져오기
            if hasattr(self, 'capture_control_bar') and self.capture_control_bar:
                fps = self.capture_control_bar.get_fps()
            else:
                fps = 15
        audio_path = self.audio_file_path if output_format == 'mp4' else None
        
        # 이전 인코딩 스레드 정리 (논블로킹)
        if self.encoding_thread is not None:
            if self.encoding_thread.is_alive():
                # 데몬 스레드이므로 블로킹 대기 대신 경고만 출력
                logger.warning("Previous encoding thread still running, it will finish in background")
            self.encoding_thread = None
        
        # 프레임 넘기기 (스냅샷 사용 - 타이밍 이슈 방지)
        frames_to_encode = frames_snapshot
        
        self.encoding_thread = EncodingThread(
            self.encoder, frames_to_encode, fps, file_path, output_format, audio_path,
            progress_callback=self._on_encoding_progress,
            finished_callback=self._on_encoding_finished,
            error_callback=self._on_encoding_error
        )
        self.encoding_thread.start()
    
    def _on_encoding_progress(self, current, total):
        """인코딩 진행률"""
        try:
            if total > 0:
                percent = min(100, max(0, int((current / total) * 100)))  # 0-100 범위 제한
            else:
                percent = 0
        except (ZeroDivisionError, ValueError, TypeError):
            percent = 0
        
        if percent >= 0:
            if self.encoding_progress_bar:
                self.encoding_progress_bar.SetValue(percent)
            if hasattr(self, 'capture_control_bar') and self.capture_control_bar:
                format_name = self.capture_control_bar.get_format()
            else:
                format_name = "GIF"
            if self.encoding_status_label:
                self.encoding_status_label.SetLabel(tr('encoding_percent').format(format_name, percent))
            self.status_msg_label.SetLabel(tr('encoding_percent').format(format_name, percent))
            if getattr(self, '_progress_panel', None):
                self._progress_panel.Refresh()
    
    def _on_encoding_finished(self, output_path):
        """인코딩 완료"""
        try:
            # 프레임 버퍼 즉시 해제 (메모리 최적화)
            self.frames = []
            if self.recorder:
                self.recorder.clear_frames()
            
            # 오디오 임시 파일 정리
            if hasattr(self, 'audio_recorder') and self.audio_recorder:
                self.audio_recorder.cleanup()
            self.audio_file_path = None
            
            # 파일 크기 계산
            file_size_str = ""
            try:
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    if file_size < 1024:
                        file_size_str = f" ({file_size} B)"
                    elif file_size < 1024 * 1024:
                        file_size_str = f" ({file_size / 1024:.1f} KB)"
                    else:
                        file_size_str = f" ({file_size / (1024 * 1024):.1f} MB)"
            except Exception:
                pass
            
            # 프로그레스 바 완료 후 숨김
            if self.encoding_progress_bar:
                self.encoding_progress_bar.SetValue(100)
                bar = self.encoding_progress_bar
                def _hide_bar():
                    try:
                        if bar:
                            bar.Hide()
                    except (RuntimeError, AttributeError):
                        pass
                wx.CallLater(300, _hide_bar)
            if self.encoding_status_label:
                self.encoding_status_label.SetLabel("✓ " + tr('save_complete') + file_size_str)
                self.encoding_status_label.SetForegroundColour(Colors.ENCODING_COMPLETE)
            if getattr(self, '_progress_panel', None):
                self._progress_panel.Layout()
                self._progress_panel.Refresh()
            
            # 상태바에 파일 경로 표시
            filename = os.path.basename(output_path)
            self.status_msg_label.SetLabel(tr('saved_to').format(filename) + file_size_str)
            
            # 일정 시간 후 메시지 제거
            wx.CallLater(ENCODING_STATUS_CLEAR_DELAY_MS, self._clear_encoding_status)
            
            # 저장된 폴더 열기 (Windows)
            try:
                folder = os.path.dirname(output_path)
                if folder and os.path.exists(folder) and os.path.isdir(folder):
                    try:
                        os.startfile(folder)
                    except (OSError, AttributeError) as e:
                        logger.warning(f"폴더 열기 실패: {e}")
                        # 폴더 열기 실패 시 사용자에게 경로 알림
                        wx.MessageBox(
                            tr('saved_to_path').format(output_path),
                            tr('save_complete'),
                            wx.OK | wx.ICON_INFORMATION
                        )
                else:
                    logger.warning(f"Output folder not accessible: {folder}")
            except (OSError, ValueError) as e:
                logger.error(f"Path processing error: {e}")
            
            self._reset_ui()
        except Exception as e:
            logger.warning("인코딩 완료 후처리 중 에러: %s", e)
            self._reset_ui()
    
    def _clear_encoding_status(self):
        """인코딩 상태 메시지 제거"""
        self.status_msg_label.SetLabel(tr('ready'))
        if self.encoding_status_label:
            self.encoding_status_label.SetLabel("")
    
    def _on_recording_error(self, error_msg):
        """녹화 에러 처리"""
        wx.MessageBox(tr('recording_error').format(error_msg), tr('error'), wx.OK | wx.ICON_ERROR)
        if self.record_state in [self.STATE_RECORDING, self.STATE_PAUSED]:
            self._stop_recording()
        self._reset_ui()
    
    def _on_encoding_error(self, error_msg):
        """인코딩 에러"""
        # 프레임 버퍼 즉시 해제 (메모리 최적화)
        self.frames = []
        if self.recorder:
            self.recorder.clear_frames()
        
        # 프로그레스 바 초기화 후 숨김
        if self.encoding_progress_bar:
            self.encoding_progress_bar.SetValue(0)
            self.encoding_progress_bar.Hide()
        if self.encoding_status_label:
            self.encoding_status_label.SetLabel("✗ " + tr('encoding_failed'))
            self.encoding_status_label.SetForegroundColour(Colors.ENCODING_ERROR)
        if getattr(self, '_progress_panel', None):
            self._progress_panel.Layout()
            self._progress_panel.Refresh()
        
        wx.MessageBox(tr('encoding_failed') + f":\n{error_msg}", tr('error'), wx.OK | wx.ICON_ERROR)
        
        # 일정 시간 후 메시지 제거
        wx.CallLater(ENCODING_STATUS_CLEAR_DELAY_MS, self._clear_encoding_status)
        self._reset_ui()
    
    def _reset_ui(self):
        """UI 초기화"""
        # capture_control_bar 컨트롤 활성화
        if hasattr(self, 'capture_control_bar') and self.capture_control_bar:
            self.capture_control_bar.fps_combo.Enable(True)
            self.capture_control_bar.quality_combo.Enable(True)
            self.capture_control_bar.format_combo.Enable(True)
            self.capture_control_bar.resolution_combo.Enable(True)
        self.frames = []
        self.info_label.SetLabel("")
        self.status_msg_label.SetLabel(tr('ready'))
    
    def _detect_system_capabilities(self):
        """시스템 능력 감지 및 최적 파이프라인 적용"""
        try:
            # Capability 감지 (캐시 사용)
            caps = self._capability_manager.detect_capabilities()
            
            # 최적 파이프라인 적용
            pipeline = caps.optimal_pipeline
            if pipeline:
                # 캡처 백엔드 설정
                user_backend = self.settings.get("General", "capture_backend", fallback="gdi")
                if self.recorder:
                    if user_backend == "auto":
                        # Auto 모드: HDR 감지하여 백엔드 선택
                        from core.hdr_utils import is_hdr_active
                        hdr_active = is_hdr_active()
                        actual_backend = "gdi" if hdr_active else "dxcam"
                        logger.info(f"[MainWindow] Auto: HDR {'ON' if hdr_active else 'OFF'} → {actual_backend}")
                        self.recorder.set_capture_backend(actual_backend)
                    elif user_backend in ["dxcam", "gdi"]:
                        # 명시적 설정 우선
                        logger.info(f"[MainWindow] 사용자 설정 백엔드 유지: {user_backend}")
                        self.recorder.set_capture_backend(user_backend)
                    else:
                        # 잘못된 설정 - 파이프라인 적용
                        self.recorder.set_capture_backend(pipeline.capture_backend)
                
                # 인코더 설정
                if self.encoder:
                    self.encoder.set_codec(pipeline.codec)
                    # 인코더 타입 추출 (nvenc, qsv, amf, cpu)
                    encoder_type = 'auto'
                    if 'nvenc' in pipeline.encoder:
                        encoder_type = 'nvenc'
                    elif 'qsv' in pipeline.encoder:
                        encoder_type = 'qsv'
                    elif 'amf' in pipeline.encoder:
                        encoder_type = 'amf'
                    elif 'lib' in pipeline.encoder:
                        encoder_type = 'cpu'
                    self.encoder.set_preferred_encoder(encoder_type)
                
                logger.info("[MainWindow] 최적 파이프라인 적용: %s", pipeline.name)

            # GPU 하드웨어 감지 시 백그라운드에서 CuPy까지 확인하여 자동 활성화
            if caps.has_nvidia_gpu:
                def _detect_cupy_bg():
                    try:
                        info = detect_gpu(skip_cupy=False)
                    except Exception:
                        from core.gpu_utils import GpuInfo
                        info = GpuInfo()
                    wx.CallAfter(self._on_auto_gpu_detect_done, info)
                threading.Thread(target=_detect_cupy_bg, daemon=True).start()

        except Exception as e:
            logger.warning("[MainWindow] 시스템 능력 감지 실패: %s", e)

    def _on_auto_gpu_detect_done(self, gpu_info):
        """자동 GPU 감지 완료 (메인 스레드) — CuPy 가능 시 GPU 자동 활성화"""
        self._gpu_initialized = True
        has_gpu = gpu_info.has_cupy
        self.capture_control_bar.set_gpu_status(has_gpu)
        if has_gpu:
            logger.info("[MainWindow] GPU 자동 활성화: CuPy 사용 가능")
        else:
            logger.info("[MainWindow] GPU 자동 감지 완료: CuPy 미사용")

    def _on_gpu_button_click(self):
        """GPU 버튼 클릭 — 비동기 GPU 감지 후 정보 표시"""
        if self._gpu_initialized:
            # 이미 초기화됨 → GPU 정보 메시지박스 표시
            self._show_gpu_info_dialog()
            return

        # 아직 초기화 안 됨 → 백그라운드에서 감지
        self.capture_control_bar.gpu_status_button.SetLabel(tr('gpu_initializing'))
        self.capture_control_bar.gpu_status_button.Enable(False)

        def _detect_in_bg():
            try:
                info = detect_gpu()  # CuPy 포함 전체 감지
            except Exception:
                from core.gpu_utils import GpuInfo
                info = GpuInfo()
            wx.CallAfter(self._on_gpu_detect_done, info)

        threading.Thread(target=_detect_in_bg, daemon=True).start()

    def _on_gpu_detect_done(self, gpu_info):
        """GPU 감지 완료 (메인 스레드)"""
        self._gpu_initialized = True
        self.capture_control_bar.gpu_status_button.Enable(True)
        self.capture_control_bar.set_gpu_status(gpu_info.has_cuda)
        self._show_gpu_info_dialog()

    def _show_gpu_info_dialog(self):
        """GPU 정보 메시지박스 표시"""
        try:
            gpu_info = detect_gpu(skip_cupy=True)
        except Exception:
            from core.gpu_utils import GpuInfo
            gpu_info = GpuInfo()

        if not gpu_info.has_cuda:
            wx.MessageBox(tr('gpu_not_found_msg'), tr('gpu_info_title'), wx.OK | wx.ICON_INFORMATION, self)
            return

        msg = tr('gpu_info_msg',
                 name=gpu_info.gpu_name or "Unknown",
                 memory=gpu_info.gpu_memory_mb,
                 cupy="O" if gpu_info.has_cupy else "X",
                 nvenc="O" if gpu_info.ffmpeg_nvenc else "X",
                 driver=gpu_info.driver_version or "N/A")
        wx.MessageBox(msg, tr('gpu_info_title'), wx.OK | wx.ICON_INFORMATION, self)
    
    def _update_hdr_label(self):
        """HDR 모드 레이블 업데이트 (상태바 필드 2 및 hdr_label)"""
        try:
            hdr_force = bool(self.recorder and getattr(self.recorder, 'hdr_correction_force', False))
            if is_hdr_active() or hdr_force:
                hdr_text = "HDR"
            else:
                hdr_text = ""
            if self and hasattr(self, 'hdr_label') and self.hdr_label is not None:
                self.hdr_label.SetLabel(hdr_text)
                if hdr_text:
                    self.hdr_label.Show()
                else:
                    self.hdr_label.Hide()
        except (RuntimeError, AttributeError, wx.PyDeadObjectError) as e:
            logger.debug("HDR label update failed: %s", e)
    
    def _setup_shortcuts(self):
        """키보드 단축키 설정 (글로벌 핫키는 capture_control_bar에서 처리)"""
        pass
    
    def _on_shortcut_rec(self):
        """F9 단축키: 녹화 시작/일시정지"""
        if self.record_state == self.STATE_READY:
            self._start_recording()
        elif self.record_state == self.STATE_PAUSED:
            self._resume_recording()
        elif self.record_state == self.STATE_RECORDING:
            self._pause_recording()
    
    def _on_shortcut_stop(self):
        """F10 단축키: 녹화 중지"""
        if self.record_state in [self.STATE_RECORDING, self.STATE_PAUSED]:
            self._stop_recording()
    
    def _on_shortcut_overlay(self):
        """F11 단축키: 캡처 영역 표시/숨김"""
        if self.capture_overlay:
            if self.capture_overlay.IsShown():
                self.capture_overlay.Hide()
            else:
                self.capture_overlay.Show()
                self.capture_overlay.Raise()  # 항상 최상위로
                self._position_overlay_below_window()
    
    def _cleanup_overlay_on_quit(self):
        """앱 종료 직전 캡처 오버레이 강제 정리 (aboutToQuit에서 호출)"""
        overlay = getattr(self, 'capture_overlay', None)
        self.capture_overlay = None
        if overlay is not None:
            try:
                overlay.Hide()
                overlay.Destroy()
            except (RuntimeError, AttributeError, TypeError):
                pass

    def OnClose(self, event):
        """윈도우 닫기 이벤트"""
        if self.record_state != self.STATE_READY:
            dlg = wx.MessageDialog(
                self,
                tr('quit_confirm_msg'),
                tr('confirm'),
                wx.YES_NO | wx.ICON_QUESTION | wx.NO_DEFAULT
            )
            reply = dlg.ShowModal()
            dlg.Destroy()
            if reply == wx.ID_NO:
                event.Veto()
                return
            
            if self.recorder is not None:
                self.recorder.stop_recording()
        
        # 설정을 디스크에 저장 (해상도, FPS 등 유지)
        self._save_settings_to_disk()

        # 캡처 오버레이 먼저 강제 종료 (로컬 참조 사용: Destroy 시 콜백에서 None이 됨 방지)
        overlay = self.capture_overlay
        self.capture_overlay = None
        if overlay is not None:
            try:
                overlay.Hide()
                overlay.Close()
                overlay.Destroy()
            except (RuntimeError, AttributeError):
                pass
        
        # 번역 콜백 등록 해제 (메모리 누수 및 PyDeadObjectError 방지)
        try:
            self.trans.unregister_callback(self.retranslateUi)
        except Exception:
            pass

        # 전체 리소스 정리
        self._cleanup_all_resources()
        
        event.Skip()  # wxPython에서는 Skip() 사용
    
    def _cleanup_all_resources(self):
        """모든 리소스 정리 - 메모리 누수 방지"""
        from core.utils import safe_delete_timer
        
        # 미리보기 중지
        self._stop_preview()
        
        # HDR 체크 타이머 정리
        if getattr(self, '_hdr_check_timer', None) is not None:
            safe_delete_timer(self._hdr_check_timer)
            self._hdr_check_timer = None
        
        # 녹화 타이머 정리
        if self.record_timer is not None:
            safe_delete_timer(self.record_timer)
            self.record_timer = None
        
        # 인코딩 스레드 정리 (threading.Thread 기반)
        if self.encoding_thread is not None:
            if self.encoding_thread.is_alive():
                # 데몬 스레드이므로 종료 대기만
                self.encoding_thread.join(timeout=2.0)
            self.encoding_thread = None
        
        # 오디오 레코더 정리
        if hasattr(self, 'audio_recorder') and self.audio_recorder:
            try:
                if self.audio_recorder.is_recording():
                    self.audio_recorder.stop()
                self.audio_recorder.cleanup()
            except (AttributeError, RuntimeError):
                pass
        
        # 캡처 오버레이 정리 (wxPython, 로컬 참조 사용)
        overlay = self.capture_overlay
        self.capture_overlay = None
        if overlay is not None:
            try:
                overlay.Close()
                overlay.Destroy()
            except (RuntimeError, AttributeError):
                pass
        
        # 프레임 버퍼 해제
        self.frames = []
        if self.recorder is not None:
            self.recorder.clear_frames()
        
        # DXCam 공유 카메라 정리 (메모리 누수 방지)
        try:
            from core.capture_backend import DXCamBackend
            DXCamBackend.cleanup_shared_camera()
        except Exception as e:
            logger.debug(f"DXCam cleanup error: {e}")
