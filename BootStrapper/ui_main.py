"""
ui_main.py - XGif Bootstrapper 메인 UI
startup_check_dialog.py 디자인 기반 – 독립 실행형 부트스트래퍼

다크 테마 · ListCtrl 상태 테이블 · 접이식 로그 · FlatButton
"""
import wx
import wx.lib.newevent
import subprocess
import threading
import os
from typing import Optional

# ── 커스텀 이벤트 ──────────────────────────────────────────
LogEvent, EVT_LOG = wx.lib.newevent.NewEvent()
ProgressEvent, EVT_PROGRESS = wx.lib.newevent.NewEvent()
TaskCompleteEvent, EVT_TASK_COMPLETE = wx.lib.newevent.NewEvent()
UpdateRowEvent, EVT_UPDATE_ROW = wx.lib.newevent.NewEvent()

# ── 상태 상수 ──────────────────────────────────────────────
ST_UNCHECKED = "미검사"
ST_CHECKING = "검사 중…"
ST_PASS = "설치됨"
ST_MISSING = "미설치"
ST_INSTALLING = "설치 중…"
ST_INSTALL_OK = "설치 완료"
ST_FAIL = "실패"
ST_SKIP = "건너뜀"

# ── 색상 (ui/theme.py Colors 독립 복제) ───────────────────
_BG_PANEL = wx.Colour(40, 40, 40)
_BG_TERTIARY = wx.Colour(55, 55, 55)
_BG_HOVER = wx.Colour(70, 70, 70)
_BG_PRESSED = wx.Colour(45, 45, 45)
_TEXT_PRIMARY = wx.Colour(255, 255, 255)
_TEXT_SECONDARY = wx.Colour(180, 180, 180)
_ACCENT = wx.Colour(0, 120, 212)
_ACCENT_HOVER = wx.Colour(26, 145, 235)
_ACCENT_PRESSED = wx.Colour(0, 95, 170)
_BTN_DISABLED_FG = wx.Colour(100, 100, 100)
_BTN_DISABLED_BG = wx.Colour(50, 50, 50)

_GREEN = wx.Colour(129, 199, 132)
_RED = wx.Colour(255, 107, 107)
_YELLOW = wx.Colour(255, 213, 79)
_BLUE = wx.Colour(79, 195, 247)
_DIM = wx.Colour(180, 180, 180)

_STATUS_COLORS = {
    ST_UNCHECKED: _DIM,
    ST_CHECKING: _BLUE,
    ST_PASS: _GREEN,
    ST_MISSING: _RED,
    ST_INSTALLING: _BLUE,
    ST_INSTALL_OK: _GREEN,
    ST_FAIL: _RED,
    ST_SKIP: _YELLOW,
}

# ── 폰트 유틸 ─────────────────────────────────────────────
_FONT_FACE = "Segoe UI Variable"
_FONT_FB = "Segoe UI"


def _font(size=10, bold=False):
    w = wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL
    f = wx.Font(size, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, w,
                faceName=_FONT_FACE)
    if not f.IsOk() or f.GetFaceName() != _FONT_FACE:
        f = wx.Font(size, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, w,
                    faceName=_FONT_FB)
    return f


# ── FlatButton (capture_control_bar.py 독립 복제) ─────────
class FlatButton(wx.Control):
    """Windows 11 스타일 플랫 버튼 (owner-draw)"""

    def __init__(self, parent, label="", size=wx.DefaultSize,
                 bg_color=None, fg_color=None,
                 hover_color=None, pressed_color=None,
                 corner_radius=4, id=wx.ID_ANY):
        super().__init__(parent, id, pos=wx.DefaultPosition,
                         size=size, style=wx.BORDER_NONE)
        self._label = label
        self._corner_radius = corner_radius
        self._enabled = True

        self._bg = wx.Colour(*(bg_color or _BG_TERTIARY.Get()[:3]))
        self._fg = wx.Colour(*(fg_color or _TEXT_PRIMARY.Get()[:3]))
        self._hover_c = wx.Colour(*(hover_color or _BG_HOVER.Get()[:3]))
        self._press_c = wx.Colour(*(pressed_color or _BG_PRESSED.Get()[:3]))

        self._hovered = False
        self._pressed = False
        self._cache = None
        self._cache_key = None

        self.SetMinSize(size)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.SetFont(_font(10))

        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda e: None)
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_left_up)

    # --- 공개 API ---

    def SetLabel(self, label):
        self._label = label
        self._cache = None
        self.Refresh()

    def GetLabel(self):
        return self._label

    def Enable(self, enable=True):
        self._enabled = enable
        super().Enable(enable)
        self.SetCursor(
            wx.Cursor(wx.CURSOR_HAND if enable else wx.CURSOR_ARROW))
        self._cache = None
        self.Refresh()

    def Disable(self):
        self.Enable(False)

    # --- 내부 이벤트 ---

    def _on_enter(self, event):
        if self._enabled:
            self._hovered = True
            self.Refresh()

    def _on_leave(self, event):
        self._hovered = False
        self._pressed = False
        self.Refresh()

    def _on_left_down(self, event):
        if self._enabled:
            self._pressed = True
            self.CaptureMouse()
            self.Refresh()

    def _on_left_up(self, event):
        had_capture = self.HasCapture()
        if had_capture:
            self.ReleaseMouse()
        was_pressed = self._pressed
        self._pressed = False
        self.Refresh()
        if was_pressed and self._enabled and self._hovered:
            evt = wx.CommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED,
                                 self.GetId())
            evt.SetEventObject(self)
            self.GetEventHandler().ProcessEvent(evt)

    def _on_paint(self, event):
        dc = wx.PaintDC(self)
        w, h = self.GetSize()
        if w <= 0 or h <= 0:
            return

        key = (w, h, self._hovered, self._pressed, self._enabled, self._label)
        if self._cache is not None and self._cache_key == key:
            dc.DrawBitmap(self._cache, 0, 0, False)
            return

        bmp = wx.Bitmap(w, h)
        mdc = wx.MemoryDC(bmp)
        parent = self.GetParent()
        mdc.SetBackground(
            wx.Brush(parent.GetBackgroundColour() if parent else _BG_PANEL))
        mdc.Clear()

        gc = wx.GraphicsContext.Create(mdc)
        if gc:
            if not self._enabled:
                bg = _BTN_DISABLED_BG
            elif self._pressed:
                bg = self._press_c
            elif self._hovered:
                bg = self._hover_c
            else:
                bg = self._bg

            gc.SetBrush(wx.Brush(bg))
            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.DrawRoundedRectangle(0, 0, w, h, self._corner_radius)

            fg = _BTN_DISABLED_FG if not self._enabled else self._fg
            gc.SetFont(self.GetFont(), fg)
            tw, th = gc.GetTextExtent(self._label)[:2]
            gc.DrawText(self._label, (w - tw) / 2, (h - th) / 2)

        mdc.SelectObject(wx.NullBitmap)
        self._cache = bmp
        self._cache_key = key
        dc.DrawBitmap(bmp, 0, 0, False)


# ────────────────────────────────────────────────────────────
# 메인 프레임
# ────────────────────────────────────────────────────────────
class BootstrapperFrame(wx.Frame):
    """XGif 부트스트래퍼 — startup_check_dialog 디자인"""

    def __init__(self, logger, paths_module):
        # 버전 정보 가져오기
        try:
            import importlib, sys, os
            # core/version.py를 직접 로드 (부트스트래퍼는 core 패키지 밖에 있음)
            _target = paths_module.get_target_dir()
            _ver_path = os.path.join(str(_target), "core", "version.py")
            if os.path.isfile(_ver_path):
                spec = importlib.util.spec_from_file_location("_ver", _ver_path)
                _mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(_mod)
                _app_ver = getattr(_mod, "APP_VERSION", "")
            else:
                _app_ver = ""
        except Exception:
            _app_ver = ""
        _title = f"XGif Bootstrapper v{_app_ver}" if _app_ver else "XGif Bootstrapper"

        super().__init__(
            parent=None, title=_title,
            size=(740, 560),
            style=wx.DEFAULT_FRAME_STYLE | wx.RESIZE_BORDER,
        )
        self.SetBackgroundColour(_BG_PANEL)
        self.SetMinSize((640, 440))

        self.logger = logger
        self.paths = paths_module
        self._worker: Optional[threading.Thread] = None
        self._is_running = False
        self._log_visible = False
        self._all_required_ok = False
        self._auto_close_timer: Optional[wx.Timer] = None
        self._auto_close_remaining = 0

        # deps 로드
        import deps_specs
        self._deps = deps_specs.DEPS

        self._build_ui()
        self.Centre()

        # 로깅 콜백
        from logging_setup import set_ui_callback
        set_ui_callback(self._on_log_cb)

        # 이벤트
        self.Bind(EVT_LOG, self._on_log_evt)
        self.Bind(EVT_PROGRESS, self._on_progress_evt)
        self.Bind(EVT_TASK_COMPLETE, self._on_complete_evt)
        self.Bind(EVT_UPDATE_ROW, self._on_row_evt)
        self.Bind(wx.EVT_CLOSE, self._on_window_close)

        self.logger.info("UI 초기화 완료")

        # 열자마자 자동 검사 시작
        wx.CallAfter(self._start_check_only)

    # ──────────────────────────────────────────────
    # UI 구성
    # ──────────────────────────────────────────────

    def _build_ui(self):
        # Windows에서 Frame 직접 사용 시 배경 렌더링 문제 → Panel 필수
        panel = wx.Panel(self)
        panel.SetBackgroundColour(_BG_PANEL)
        self._panel = panel

        root = wx.BoxSizer(wx.VERTICAL)

        # ── 제목 ──
        # 좌측 여백에 StaticText를 배치하면 첫 글자가 잘릴 수 있으므로
        # 텍스트 앞에 공백 패딩을 포함한 수평 sizer 사용
        title = wx.StaticText(panel, label="  XGif 의존성 설치 도우미")
        title.SetForegroundColour(_TEXT_PRIMARY)
        title.SetFont(_font(16, bold=True))
        root.Add(title, 0, wx.LEFT | wx.TOP | wx.RIGHT, 20)
        root.AddSpacer(4)

        # ── 설명 ──
        desc = wx.StaticText(
            panel,
            label="  필수 구성 요소를 자동으로 검사하고 설치합니다."
                  " 인터넷 연결이 필요합니다.\n"
                  "  이 설치 과정은 인터넷 환경에 따라 1분에서 10분이 걸릴 수 있습니다."
                  " GPU가 있는 분은 전부 다 설치해야 작동합니다!",
        )
        desc.SetForegroundColour(_TEXT_SECONDARY)
        desc.SetFont(_font(10))
        desc.Wrap(660)
        root.Add(desc, 0, wx.LEFT | wx.RIGHT, 20)
        root.AddSpacer(12)

        # ── ListCtrl (4컬럼) ──
        self._list = wx.ListCtrl(
            panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_NONE,
        )
        self._list.SetBackgroundColour(wx.Colour(40, 40, 40))
        self._list.SetForegroundColour(_TEXT_PRIMARY)
        self._list.SetFont(_font(10))

        self._list.InsertColumn(0, "구성 요소", width=180)
        self._list.InsertColumn(1, "필수", width=80)
        self._list.InsertColumn(2, "상태", width=140)
        self._list.InsertColumn(3, "상세", width=300)

        for i, dep in enumerate(self._deps):
            idx = self._list.InsertItem(i, dep["label"])
            self._list.SetItem(idx, 1, "필수" if dep["required"] else "선택")
            self._list.SetItem(idx, 2, ST_UNCHECKED)
            self._list.SetItem(idx, 3, "")
            self._list.SetItemTextColour(idx, _DIM)

        root.Add(self._list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        root.AddSpacer(8)

        # ── 프로그레스 바 ──
        self._gauge = wx.Gauge(
            panel, range=max(len(self._deps), 1),
            style=wx.GA_HORIZONTAL | wx.GA_SMOOTH,
        )
        root.Add(self._gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        root.AddSpacer(6)

        # ── 로그 토글 ──
        self._log_toggle = wx.StaticText(panel, label="\u25B6 로그 보기")
        self._log_toggle.SetForegroundColour(_TEXT_SECONDARY)
        self._log_toggle.SetFont(_font(9))
        self._log_toggle.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self._log_toggle.Bind(wx.EVT_LEFT_DOWN, self._on_toggle_log)
        root.Add(self._log_toggle, 0, wx.LEFT, 20)
        root.AddSpacer(2)

        # ── 로그 텍스트 (기본 숨김) ──
        self._log_text = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.BORDER_NONE,
        )
        self._log_text.SetBackgroundColour(wx.Colour(24, 24, 24))
        self._log_text.SetForegroundColour(_DIM)
        self._log_text.SetFont(wx.Font(
            9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_NORMAL, faceName="Consolas",
        ))
        self._log_text.SetMinSize((-1, 120))
        self._log_text.Hide()
        root.Add(self._log_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        root.AddSpacer(12)

        # ── 버튼 바 ──
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._btn_install = FlatButton(
            panel, label="설치 시작", size=(130, 32),
            bg_color=_ACCENT.Get()[:3],
            fg_color=_TEXT_PRIMARY.Get()[:3],
            hover_color=_ACCENT_HOVER.Get()[:3],
            pressed_color=_ACCENT_PRESSED.Get()[:3],
        )
        self._btn_install.Bind(wx.EVT_BUTTON, self._on_install)
        btn_sizer.Add(self._btn_install, 0, wx.RIGHT, 6)

        self._btn_recheck = FlatButton(
            panel, label="다시 검사", size=(100, 32),
            bg_color=_BG_TERTIARY.Get()[:3],
            fg_color=_TEXT_PRIMARY.Get()[:3],
            hover_color=_BG_HOVER.Get()[:3],
        )
        self._btn_recheck.Bind(wx.EVT_BUTTON, self._on_recheck)
        btn_sizer.Add(self._btn_recheck, 0, wx.RIGHT, 6)

        self._btn_log_folder = FlatButton(
            panel, label="로그 폴더", size=(100, 32),
            bg_color=_BG_TERTIARY.Get()[:3],
            fg_color=_TEXT_PRIMARY.Get()[:3],
            hover_color=_BG_HOVER.Get()[:3],
        )
        self._btn_log_folder.Bind(wx.EVT_BUTTON, self._on_open_log_folder)
        btn_sizer.Add(self._btn_log_folder, 0)

        btn_sizer.AddStretchSpacer()

        self._btn_close = FlatButton(
            panel, label="닫기", size=(80, 32),
            bg_color=_BG_TERTIARY.Get()[:3],
            fg_color=_TEXT_PRIMARY.Get()[:3],
            hover_color=_BG_HOVER.Get()[:3],
        )
        self._btn_close.Bind(wx.EVT_BUTTON, self._on_close)
        btn_sizer.Add(self._btn_close, 0)

        root.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)
        panel.SetSizer(root)

    # ──────────────────────────────────────────────
    # 이벤트 핸들러
    # ──────────────────────────────────────────────

    def _on_log_cb(self, msg: str):
        try:
            if self and not self.IsBeingDeleted():
                wx.PostEvent(self, LogEvent(message=msg))
        except RuntimeError:
            pass  # window already destroyed

    def _on_log_evt(self, event):
        self._log_text.AppendText(event.message + "\n")
        self._log_text.ShowPosition(self._log_text.GetLastPosition())

    def _on_toggle_log(self, event):
        self._log_visible = not self._log_visible
        if self._log_visible:
            self._log_text.Show()
            self._log_toggle.SetLabel("\u25BC 로그 숨기기")
        else:
            self._log_text.Hide()
            self._log_toggle.SetLabel("\u25B6 로그 보기")
        self._panel.Layout()

    def _on_progress_evt(self, event):
        self._gauge.SetValue(event.value)

    def _on_row_evt(self, event):
        color = _STATUS_COLORS.get(event.status, _TEXT_PRIMARY)
        self._list.SetItem(event.row, 2, event.status)
        self._list.SetItem(event.row, 3, event.detail)
        self._list.SetItemTextColour(event.row, color)

    def _on_complete_evt(self, event):
        self._is_running = False
        self._btn_recheck.Enable(True)
        self._btn_close.Enable(True)

        # 자동 닫기 타이머 초기화
        if hasattr(self, "_auto_close_timer") and self._auto_close_timer:
            self._auto_close_timer.Stop()
            self._auto_close_timer = None

        if event.success:
            # 필수 항목 중 미설치가 있는지 확인
            has_missing = False
            for i, dep in enumerate(self._deps):
                st = self._list.GetItemText(i, 2)
                if dep["required"] and st not in (ST_PASS, ST_INSTALL_OK):
                    has_missing = True
                    break

            self._all_required_ok = not has_missing

            if has_missing:
                self._btn_install.SetLabel("설치 시작")
                self._btn_install.Enable(True)
            else:
                self._btn_install.SetLabel("모두 충족")
                self._btn_install.Enable(False)
                # 자동 닫기 카운트다운 시작 (#12)
                self._start_auto_close_countdown()
        else:
            self._all_required_ok = False
            self._btn_install.SetLabel("설치 시작")
            self._btn_install.Enable(True)

            # 실패 메시지를 UI에 표시 (#13)
            if event.error:
                self.logger.error(f"설치 실패: {event.error}")
                wx.MessageBox(
                    event.error,
                    "설치 실패",
                    wx.OK | wx.ICON_ERROR,
                )

    # ──────────────────────────────────────────────
    # 자동 닫기 (#12)
    # ──────────────────────────────────────────────

    def _start_auto_close_countdown(self, seconds: int = 5):
        """모든 필수 항목이 충족되면 카운트다운 후 자동 종료"""
        self._auto_close_remaining = seconds
        self._auto_close_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_auto_close_tick, self._auto_close_timer)
        self._auto_close_timer.Start(1000)
        self._btn_close.SetLabel(f"닫기 ({seconds}s)")

    def _on_auto_close_tick(self, event):
        self._auto_close_remaining -= 1
        if self._auto_close_remaining <= 0:
            self._auto_close_timer.Stop()
            self._auto_close_timer = None
            self.Close()
        else:
            self._btn_close.SetLabel(f"닫기 ({self._auto_close_remaining}s)")

    def _cancel_auto_close(self):
        """자동 닫기 취소 (사용자가 버튼 클릭 시)"""
        if self._auto_close_timer:
            self._auto_close_timer.Stop()
            self._auto_close_timer = None
            self._btn_close.SetLabel("닫기")

    # ──────────────────────────────────────────────
    # 버튼 액션
    # ──────────────────────────────────────────────

    def _set_busy(self, label="진행 중…"):
        self._is_running = True
        self._btn_install.Enable(False)
        self._btn_install.SetLabel(label)
        self._btn_recheck.Enable(False)

    def _on_install(self, event):
        """누락 항목 검사 + 설치"""
        self._cancel_auto_close()
        if self._is_running:
            return
        self._reset_rows()
        self._set_busy("설치 중…")
        self._gauge.SetRange(len(self._deps))
        self._gauge.SetValue(0)
        self.logger.info("설치 프로세스 시작")
        self._worker = threading.Thread(
            target=self._run_install_task, daemon=True)
        self._worker.start()

    def _on_recheck(self, event):
        """검사만 다시 실행"""
        self._cancel_auto_close()
        if self._is_running:
            return
        self._start_check_only()

    def _start_check_only(self):
        """검사만 실행 (UI 리셋 포함)"""
        self._reset_rows()
        self._set_busy("검사 중…")
        self._gauge.SetRange(len(self._deps))
        self._gauge.SetValue(0)
        self._worker = threading.Thread(
            target=self._run_check_only, daemon=True)
        self._worker.start()

    def _reset_rows(self):
        """ListCtrl 행 초기화"""
        for i in range(len(self._deps)):
            self._list.SetItem(i, 2, ST_UNCHECKED)
            self._list.SetItem(i, 3, "")
            self._list.SetItemTextColour(i, _DIM)

    def _on_open_log_folder(self, event):
        log_dir = self.paths.get_log_dir()
        self.logger.info(f"로그 폴더 열기: {log_dir}")
        try:
            os.startfile(str(log_dir))
        except Exception as e:
            self.logger.error(f"폴더 열기 실패: {e}")

    def _on_close(self, event):
        self.Close()

    def _on_window_close(self, event):
        self._cancel_auto_close()
        if self._is_running:
            if wx.MessageBox(
                "작업이 진행 중입니다. 종료하시겠습니까?",
                "확인", wx.YES_NO | wx.ICON_WARNING,
            ) != wx.YES:
                event.Veto()
                return
        # Store result on app for exit code
        app = wx.GetApp()
        if app:
            app._setup_success = self._all_required_ok
        self.logger.info("부트스트래퍼 종료 (setup_success=%s)", self._all_required_ok)
        self.Destroy()

    # ──────────────────────────────────────────────
    # 워커 유틸
    # ──────────────────────────────────────────────

    def _post_row(self, row, status, detail=""):
        wx.PostEvent(self, UpdateRowEvent(row=row, status=status, detail=detail))

    def _make_progress_cb(self, row_idx: int):
        """install 함수에 전달할 progress_cb 생성 (다운로드/압축 진행률 → UI 로그)"""
        _last_pct = [-1]

        def _cb(downloaded, total):
            if total and total > 0:
                pct = int(downloaded * 100 / total)
                # 5% 단위로만 업데이트하여 이벤트 폭주 방지
                if pct >= _last_pct[0] + 5 or pct >= 100:
                    _last_pct[0] = pct
                    mb = downloaded / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    self._post_row(
                        row_idx, ST_INSTALLING,
                        f"{mb:.1f} / {total_mb:.1f} MB ({pct}%)",
                    )
        return _cb

    # ──────────────────────────────────────────────
    # 워커: 검사만
    # ──────────────────────────────────────────────

    def _run_check_only(self):
        try:
            import deps_checker

            for idx, dep in enumerate(self._deps):
                self._post_row(idx, ST_CHECKING)

                check_fn = getattr(deps_checker, dep["check_func"], None)
                if check_fn is None:
                    self._post_row(idx, ST_FAIL, "check 함수 없음")
                    wx.PostEvent(self, ProgressEvent(value=idx + 1))
                    continue

                passed, detail = check_fn()
                self._post_row(
                    idx, ST_PASS if passed else ST_MISSING, detail)
                wx.PostEvent(self, ProgressEvent(value=idx + 1))

            wx.PostEvent(self, TaskCompleteEvent(success=True, error=None))

        except Exception as e:
            self.logger.error(f"검사 중 오류: {e}", exc_info=True)
            wx.PostEvent(self, TaskCompleteEvent(success=False, error=str(e)))

    # ──────────────────────────────────────────────
    # 워커: 검사 + 설치
    # ──────────────────────────────────────────────

    def _run_install_task(self):
        try:
            import deps_checker
            import deps_installer
            from download_utils import check_connectivity

            # 인터넷 연결 확인 (#6)
            self.logger.info("인터넷 연결 확인 중…")
            if not check_connectivity():
                self.logger.warning("인터넷 연결 없음")
                wx.PostEvent(self, TaskCompleteEvent(
                    success=False,
                    error="인터넷에 연결되어 있지 않습니다. 네트워크를 확인한 후 다시 시도하세요.",
                ))
                return

            failed_items = []

            for idx, dep in enumerate(self._deps):
                label = dep["label"]
                required = dep["required"]

                # ── 검사 ──
                self._post_row(idx, ST_CHECKING)

                check_fn = getattr(deps_checker, dep["check_func"], None)
                if check_fn is None:
                    self._post_row(idx, ST_FAIL, "check 함수 없음")
                    wx.PostEvent(self, ProgressEvent(value=idx + 1))
                    continue

                passed, detail = check_fn()
                if passed:
                    self._post_row(idx, ST_PASS, detail)
                    self.logger.info(f"[OK] {label}: {detail}")
                    wx.PostEvent(self, ProgressEvent(value=idx + 1))
                    continue

                # ── 설치 불가 (수동) ──
                if dep["install_func"] is None:
                    status = ST_SKIP if not required else ST_MISSING
                    self._post_row(idx, status,
                                   f"수동 설치 필요 ({detail})")
                    if required:
                        failed_items.append(label)
                    wx.PostEvent(self, ProgressEvent(value=idx + 1))
                    continue

                install_fn = getattr(deps_installer, dep["install_func"], None)
                if install_fn is None:
                    self._post_row(idx, ST_FAIL, "install 함수 없음")
                    if required:
                        failed_items.append(label)
                    wx.PostEvent(self, ProgressEvent(value=idx + 1))
                    continue

                # ── 설치 실행 (progress_cb 전달) ──
                self._post_row(idx, ST_INSTALLING)
                progress_cb = self._make_progress_cb(idx)
                success = install_fn(progress_cb=progress_cb)

                if not success:
                    self._post_row(idx, ST_FAIL, "설치 실패")
                    if required:
                        failed_items.append(label)
                        self.logger.error(f"[FAIL] {label}")
                    else:
                        self.logger.warning(
                            f"[SKIP] {label} 설치 실패 (선택)")
                    wx.PostEvent(self, ProgressEvent(value=idx + 1))
                    continue

                # ── 설치 후 재검증 ──
                self._post_row(idx, ST_CHECKING, "재검증…")
                passed2, detail2 = check_fn()
                if passed2:
                    self._post_row(idx, ST_INSTALL_OK, detail2)
                    self.logger.info(f"[OK] {label}: {detail2}")
                else:
                    self._post_row(idx, ST_FAIL,
                                   f"검증 실패: {detail2}")
                    if required:
                        failed_items.append(label)
                        self.logger.error(
                            f"[FAIL] {label} 검증 실패: {detail2}")

                wx.PostEvent(self, ProgressEvent(value=idx + 1))

            # ── 완료 ──
            if not failed_items:
                evt = TaskCompleteEvent(success=True, error=None)
            else:
                evt = TaskCompleteEvent(
                    success=False,
                    error=f"실패: {', '.join(failed_items)}",
                )
            wx.PostEvent(self, evt)
            self.logger.info("설치 작업 완료")

        except Exception as e:
            self.logger.error(f"설치 중 오류: {e}", exc_info=True)
            wx.PostEvent(self,
                         TaskCompleteEvent(success=False, error=str(e)))


def create_app(logger, paths_module) -> wx.App:
    """wx.App 인스턴스 생성"""
    app = wx.App(False)
    frame = BootstrapperFrame(logger, paths_module)
    frame.Show()
    return app
