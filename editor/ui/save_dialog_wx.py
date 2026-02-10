"""
SaveDialog (wxPython) - 양자화 설정 및 실시간 프리뷰가 있는 저장 다이얼로그

이 모듈은 GIF 저장 시 양자화 설정을 조정하고 실시간 프리뷰를 제공하는
다이얼로그를 구현합니다.
"""
import wx
from PIL import Image
from typing import Optional, Dict, List
from pathlib import Path

from .style_constants_wx import Colors, ThemedDialog
from ..core.editor_gif_encoder import GifEncoder, EncoderSettings, QuantizationMethod


class SaveDialog(ThemedDialog):
    """
    양자화 설정 및 프리뷰 다이얼로그 (wxPython 버전)

    GIF 저장 시 양자화 알고리즘, 색상 수, 디더링 등의 설정을 조정하고
    실시간으로 결과를 미리볼 수 있는 다이얼로그입니다.

    Attributes:
        PREVIEW_WIDTH: 프리뷰 영역 너비
        PREVIEW_HEIGHT: 프리뷰 영역 높이
        MAX_PREVIEW_DIM: 프리뷰 이미지 최대 크기 (크래시 방지)
        DEBOUNCE_PREVIEW_MS: 프리뷰 업데이트 디바운스 시간
        DEBOUNCE_SIZE_MS: 파일 크기 추정 디바운스 시간
        ZOOM_LEVELS: 지원하는 줌 레벨 목록
    """

    # === 클래스 상수 ===
    # 색상 상수
    COLOR_DARK_BG = Colors.BG_PRIMARY
    COLOR_PREVIEW_BG = Colors.BG_SECONDARY
    COLOR_WHITE = Colors.TEXT_PRIMARY
    COLOR_LABEL = Colors.TEXT_SECONDARY
    COLOR_BUTTON_BG = Colors.BG_HOVER
    COLOR_BUTTON_SAVE = wx.Colour(211, 47, 47)
    COLOR_SIZE_TEXT = Colors.INFO
    COLOR_SUBTEXT = Colors.TEXT_MUTED

    # 수치 상수
    BYTES_PER_MB = 1024 * 1024
    PREVIEW_WIDTH: int = 440
    PREVIEW_HEIGHT: int = 320
    MAX_PREVIEW_DIM: int = 1024
    DEBOUNCE_PREVIEW_MS: int = 100
    DEBOUNCE_SIZE_MS: int = 500
    INITIAL_PREVIEW_DELAY_MS: int = 50
    QUANTIZED_PREVIEW_DELAY_MS: int = 300
    ZOOM_LEVELS: List[float] = [0.5, 1.0, 2.0, 4.0]

    # 양자화 알고리즘 설명
    QUANT_DESCRIPTIONS: Dict[QuantizationMethod, str] = {
        QuantizationMethod.ADAPTIVE: "PIL 기본 양자화 - 빠르고 안정적",
        QuantizationMethod.MEDIANCUT: "Median Cut - 색상 분포 균일화",
        QuantizationMethod.MAXCOVERAGE: "Max Coverage - 넓은 색상 범위",
        QuantizationMethod.FASTOCTREE: "Fast Octree - 빠른 처리 속도",
        QuantizationMethod.LIBIMAGEQUANT: "LIQ - 고품질 양자화 (pngquant 사용)",
    }

    QUANT_NAMES: Dict[QuantizationMethod, str] = {
        QuantizationMethod.ADAPTIVE: "ADAPTIVE",
        QuantizationMethod.MEDIANCUT: "MEDIAN CUT",
        QuantizationMethod.MAXCOVERAGE: "MAX COVERAGE",
        QuantizationMethod.FASTOCTREE: "FAST OCTREE",
        QuantizationMethod.LIBIMAGEQUANT: "LIQ",
    }

    def __init__(self, main_window, parent=None):
        """
        SaveDialog 초기화

        Args:
            main_window: 메인 윈도우 참조
            parent: 부모 위젯 (기본값: main_window)
        """
        super().__init__(parent or main_window, title="GIF 저장 설정", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._main_window = main_window

        # 타이머 초기화
        self._preview_timer = wx.Timer(self)
        self._size_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_preview_timer, self._preview_timer)
        self.Bind(wx.EVT_TIMER, self._on_size_timer, self._size_timer)

        # 상태 변수 초기화
        self._settings = EncoderSettings()
        self._file_path: Optional[str] = None
        self._preview_zoom: float = 1.0
        self._original_preview_bitmap: Optional[wx.Bitmap] = None
        self._preview_offset_x: int = 0
        self._preview_offset_y: int = 0
        self._preview_dragging: bool = False
        self._preview_drag_start_x: float = 0.0
        self._preview_drag_start_y: float = 0.0
        self._preview_frame_index: int = 0
        self._show_quantized_preview: bool = False

        # 줌 버튼 딕셔너리
        self._zoom_buttons: Dict[float, wx.ToggleButton] = {}

        # UI 설정
        self._setup_ui()
        self._connect_events()
        self._init_preview_slider()

        # 초기 프리뷰 로딩 (지연 실행)
        wx.CallLater(self.INITIAL_PREVIEW_DELAY_MS, self._update_preview_fast)
        wx.CallLater(self.QUANTIZED_PREVIEW_DELAY_MS, self._enable_quantized_preview)

        # 다이얼로그 크기 설정
        self.SetSize((900, 550))
        self.SetMinSize((900, 550))
        self.CenterOnParent()

    def _get_translation(self, key: str, default: str = "") -> str:
        """번역 문자열 가져오기 헬퍼"""
        translations = getattr(self._main_window, '_translations', None)
        if translations:
            return translations.tr(key)
        return default

    def _setup_ui(self):
        """UI 초기화 - 레이아웃 및 위젯 구성"""
        # 다크 테마 색상 설정
        self.SetBackgroundColour(self.COLOR_DARK_BG)
        self.SetForegroundColour(self.COLOR_WHITE)

        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # === 왼쪽: 프리뷰 영역 ===
        preview_box = wx.StaticBox(self, label=self._get_translation("save_dialog_preview", "미리보기"))
        preview_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        preview_sizer = wx.StaticBoxSizer(preview_box, wx.VERTICAL)

        # 프리뷰 이미지 패널
        self._preview_panel = wx.Panel(self, size=(self.PREVIEW_WIDTH, self.PREVIEW_HEIGHT))
        self._preview_panel.SetBackgroundColour(self.COLOR_PREVIEW_BG)
        self._preview_panel.SetMinSize((self.PREVIEW_WIDTH, self.PREVIEW_HEIGHT))
        self._preview_panel.SetMaxSize((self.PREVIEW_WIDTH, self.PREVIEW_HEIGHT))

        # 프리뷰 비트맵 (StaticBitmap 대신 Panel에 직접 그리기)
        self._preview_panel.Bind(wx.EVT_PAINT, self._on_preview_paint)
        self._preview_panel.Bind(wx.EVT_LEFT_DOWN, self._on_preview_mouse_press)
        self._preview_panel.Bind(wx.EVT_MOTION, self._on_preview_mouse_move)
        self._preview_panel.Bind(wx.EVT_LEFT_UP, self._on_preview_mouse_release)

        preview_sizer.Add(self._preview_panel, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        # Zoom 버튼 영역
        zoom_sizer = wx.BoxSizer(wx.HORIZONTAL)
        zoom_label = wx.StaticText(self, label=self._get_translation("save_dialog_zoom", "Zoom:"))
        zoom_label.SetForegroundColour(self.COLOR_LABEL)
        zoom_sizer.Add(zoom_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        # Zoom 버튼들
        for zoom in self.ZOOM_LEVELS:
            btn = wx.ToggleButton(self, label=f"{zoom}x", size=(72, 36))
            btn.SetBackgroundColour(self.COLOR_BUTTON_BG)
            btn.SetForegroundColour(self.COLOR_WHITE)
            if zoom == 1.0:
                btn.SetValue(True)
            btn.Bind(wx.EVT_TOGGLEBUTTON, lambda e, z=zoom: self._set_zoom(z))
            zoom_sizer.Add(btn, 0, wx.RIGHT, 3)
            self._zoom_buttons[zoom] = btn

        zoom_sizer.AddStretchSpacer()
        preview_sizer.Add(zoom_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # 프리뷰 프레임 슬라이더
        frame_sizer = wx.BoxSizer(wx.HORIZONTAL)
        frame_label = wx.StaticText(self, label=self._get_translation("save_dialog_frame", "프레임:"))
        frame_label.SetForegroundColour(self.COLOR_LABEL)
        frame_sizer.Add(frame_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self._preview_frame_slider = wx.Slider(self, minValue=0, maxValue=100, value=0, style=wx.SL_HORIZONTAL)
        self._preview_frame_slider.Bind(wx.EVT_SLIDER, self._on_preview_frame_changed)
        frame_sizer.Add(self._preview_frame_slider, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self._preview_frame_label = wx.StaticText(self, label="0/0")
        self._preview_frame_label.SetMinSize((60, -1))
        self._preview_frame_label.SetForegroundColour(self.COLOR_LABEL)
        frame_sizer.Add(self._preview_frame_label, 0, wx.ALIGN_CENTER_VERTICAL)

        preview_sizer.Add(frame_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # 프리뷰 정보
        self._preview_info = wx.StaticText(self, label=self._get_translation("save_dialog_preview_info", "원본 vs 압축 미리보기"))
        self._preview_info.SetForegroundColour(self.COLOR_LABEL)
        preview_sizer.Add(self._preview_info, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        main_sizer.Add(preview_sizer, 0, wx.ALL, 10)

        # === 오른쪽: 설정 영역 ===
        settings_sizer = wx.BoxSizer(wx.VERTICAL)

        # 양자화 방법 선택
        quant_box = wx.StaticBox(self, label=self._get_translation("save_dialog_quantization", "양자화 알고리즘"))
        quant_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        quant_sizer = wx.StaticBoxSizer(quant_box, wx.VERTICAL)

        self._quant_combo = wx.ComboBox(self, style=wx.CB_READONLY, size=(200, -1))
        self._populate_quant_combo()
        self._quant_combo.SetBackgroundColour(Colors.BG_TERTIARY)
        self._quant_combo.SetForegroundColour(Colors.TEXT_PRIMARY)
        quant_sizer.Add(self._quant_combo, 0, wx.ALL, 5)

        # 알고리즘 설명
        self._quant_desc = wx.StaticText(self, label=self._get_translation("save_dialog_quant_desc", "PIL 기본 양자화 알고리즘"))
        self._quant_desc.SetForegroundColour(self.COLOR_SUBTEXT)
        self._quant_desc.Wrap(300)
        quant_sizer.Add(self._quant_desc, 0, wx.ALL, 5)

        settings_sizer.Add(quant_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # 품질 설정
        quality_box = wx.StaticBox(self, label=self._get_translation("save_dialog_quality", "품질 설정"))
        quality_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        quality_sizer = wx.StaticBoxSizer(quality_box, wx.VERTICAL)

        # 색상 수
        colors_sizer = wx.BoxSizer(wx.HORIZONTAL)
        colors_label = wx.StaticText(self, label="색상:")
        colors_label.SetForegroundColour(self.COLOR_LABEL)
        colors_sizer.Add(colors_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self._colors_slider = wx.Slider(self, minValue=2, maxValue=256, value=256, style=wx.SL_HORIZONTAL)
        colors_sizer.Add(self._colors_slider, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self._colors_label = wx.StaticText(self, label="256")
        self._colors_label.SetMinSize((40, -1))
        self._colors_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        colors_sizer.Add(self._colors_label, 0, wx.ALIGN_CENTER_VERTICAL)

        quality_sizer.Add(colors_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # 디더링
        self._dither_check = wx.CheckBox(self, label=self._get_translation("save_dialog_dither", "디더링 사용"))
        self._dither_check.SetValue(True)
        self._dither_check.SetForegroundColour(Colors.TEXT_SECONDARY)
        quality_sizer.Add(self._dither_check, 0, wx.ALL, 5)

        # 최적화
        self._optimize_check = wx.CheckBox(self, label=self._get_translation("save_dialog_optimize", "파일 크기 최적화"))
        self._optimize_check.SetValue(True)
        self._optimize_check.SetForegroundColour(Colors.TEXT_SECONDARY)
        quality_sizer.Add(self._optimize_check, 0, wx.ALL, 5)

        settings_sizer.Add(quality_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # 파일 크기 예상
        size_box = wx.StaticBox(self, label=self._get_translation("save_dialog_result", "예상 결과"))
        size_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        size_sizer = wx.StaticBoxSizer(size_box, wx.VERTICAL)

        size_text = self._get_translation("save_dialog_size", "예상 크기:")
        self._size_label = wx.StaticText(self, label=f"{size_text} 계산 중...")
        self._size_label.SetForegroundColour(self.COLOR_SIZE_TEXT)
        size_sizer.Add(self._size_label, 0, wx.ALL, 5)

        self._comparison_label = wx.StaticText(self, label="")
        self._comparison_label.SetForegroundColour(self.COLOR_SUBTEXT)
        self._comparison_label.Wrap(300)
        size_sizer.Add(self._comparison_label, 0, wx.ALL, 5)

        settings_sizer.Add(size_sizer, 0, wx.ALL | wx.EXPAND, 5)

        settings_sizer.AddStretchSpacer()

        # 버튼
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._save_btn = wx.Button(self, label=self._get_translation("save_dialog_save", "저장"), size=(-1, 40))
        self._save_btn.SetBackgroundColour(self.COLOR_BUTTON_SAVE)
        self._save_btn.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._save_btn.Bind(wx.EVT_BUTTON, self._on_save)
        button_sizer.Add(self._save_btn, 1, wx.ALL, 5)

        self._cancel_btn = wx.Button(self, label=self._get_translation("save_dialog_cancel", "취소"), size=(-1, 40))
        self._cancel_btn.SetBackgroundColour(self.COLOR_BUTTON_BG)
        self._cancel_btn.SetForegroundColour(self.COLOR_WHITE)
        self._cancel_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
        button_sizer.Add(self._cancel_btn, 1, wx.ALL, 5)

        settings_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 5)

        main_sizer.Add(settings_sizer, 1, wx.ALL | wx.EXPAND, 10)

        self.SetSizer(main_sizer)

    def _populate_quant_combo(self):
        """양자화 콤보박스 항목 채우기"""
        quant_items = [
            ("save_dialog_quant_adaptive", "ADAPTIVE (기본)", QuantizationMethod.ADAPTIVE),
            ("save_dialog_quant_median", "MEDIAN CUT", QuantizationMethod.MEDIANCUT),
            ("save_dialog_quant_max", "MAX COVERAGE", QuantizationMethod.MAXCOVERAGE),
            ("save_dialog_quant_octree", "FAST OCTREE", QuantizationMethod.FASTOCTREE),
            ("save_dialog_quant_liq", "LIBIMAGEQUANT (LIQ)", QuantizationMethod.LIBIMAGEQUANT),
        ]
        for key, default, method in quant_items:
            self._quant_combo.Append(self._get_translation(key, default), method)
        self._quant_combo.SetSelection(0)

    def _connect_events(self):
        """이벤트 연결 (중복 제거됨)"""
        # 각 이벤트당 하나의 핸들러만 바인딩 (성능 최적화)
        self._quant_combo.Bind(wx.EVT_COMBOBOX, self._on_quant_changed)
        self._colors_slider.Bind(wx.EVT_SLIDER, self._on_colors_changed)
        self._dither_check.Bind(wx.EVT_CHECKBOX, self._on_checkbox_changed)
        self._optimize_check.Bind(wx.EVT_CHECKBOX, self._on_checkbox_changed)

    def _on_quant_changed(self, event):
        """양자화 방법 변경 (통합 핸들러)"""
        self._on_setting_changed()
        self._on_size_setting_changed()

    def _on_checkbox_changed(self, event):
        """체크박스 변경 (통합 핸들러)"""
        self._on_setting_changed()
        self._on_size_setting_changed()

    def _enable_quantized_preview(self):
        """양자화된 프리뷰 활성화 및 업데이트"""
        self._show_quantized_preview = True
        self._update_preview()

    def _on_colors_changed(self, event):
        """색상 수 변경 (통합 핸들러)"""
        value = self._colors_slider.GetValue()
        self._colors_label.SetLabel(str(value))
        self._on_setting_changed()
        self._on_size_setting_changed()

    def _on_setting_changed(self):
        """설정 변경 시 프리뷰 업데이트 예약 (디바운싱 적용)"""
        self._update_settings()
        self._show_quantized_preview = True
        self._preview_timer.StartOnce(self.DEBOUNCE_PREVIEW_MS)

    def _on_size_setting_changed(self):
        """설정 변경 시 파일 크기 예상 업데이트 (디바운싱 적용)"""
        self._update_settings()
        self._size_timer.StartOnce(self.DEBOUNCE_SIZE_MS)

    def _on_preview_timer(self, event):
        """프리뷰 타이머 이벤트"""
        self._update_preview()

    def _on_size_timer(self, event):
        """파일 크기 타이머 이벤트"""
        self._update_size_estimate()

    def _set_zoom(self, zoom: float):
        """프리뷰 줌 설정"""
        self._preview_zoom = zoom

        # 줌이 1.0이면 오프셋 초기화
        if zoom == 1.0:
            self._preview_offset_x = 0
            self._preview_offset_y = 0

        # 모든 줌 버튼 체크 해제
        for z, btn in self._zoom_buttons.items():
            btn.SetValue(z == zoom)

        # 프리뷰 업데이트
        self._update_preview_display()

    def _update_preview_display(self):
        """프리뷰 표시 업데이트 (줌 적용 및 오프셋 고려)"""
        self._preview_panel.Refresh()

    def _on_preview_paint(self, event):
        """프리뷰 패널 페인팅"""
        if self._original_preview_bitmap is None or not self._original_preview_bitmap.IsOk():
            return

        try:
            dc = wx.PaintDC(self._preview_panel)
            dc.SetBackground(wx.Brush(Colors.BG_SECONDARY))
            dc.Clear()

            # 줌 적용
            bmp_width = self._original_preview_bitmap.GetWidth()
            bmp_height = self._original_preview_bitmap.GetHeight()

            scaled_width = max(1, int(bmp_width * self._preview_zoom))
            scaled_height = max(1, int(bmp_height * self._preview_zoom))

            # 비트맵 스케일링
            img = self._original_preview_bitmap.ConvertToImage()
            img = img.Scale(scaled_width, scaled_height, wx.IMAGE_QUALITY_HIGH)
            scaled_bitmap = wx.Bitmap(img)

            # 패널 크기
            panel_width, panel_height = self._preview_panel.GetSize()

            # 줌인이 되어 있을 때만 오프셋 적용
            if self._preview_zoom > 1.0:
                # 오프셋 범위 제한
                max_offset_x = max(0, (scaled_width - panel_width) // 2)
                max_offset_y = max(0, (scaled_height - panel_height) // 2)

                if max_offset_x > 0:
                    self._preview_offset_x = max(-max_offset_x, min(max_offset_x, self._preview_offset_x))
                else:
                    self._preview_offset_x = 0

                if max_offset_y > 0:
                    self._preview_offset_y = max(-max_offset_y, min(max_offset_y, self._preview_offset_y))
                else:
                    self._preview_offset_y = 0

                # 이미지 그리기 (오프셋 적용)
                img_x = (panel_width - scaled_width) // 2 + self._preview_offset_x
                img_y = (panel_height - scaled_height) // 2 + self._preview_offset_y
            else:
                # 줌이 1.0 이하일 때는 중앙 정렬
                img_x = (panel_width - scaled_width) // 2
                img_y = (panel_height - scaled_height) // 2

            dc.DrawBitmap(scaled_bitmap, img_x, img_y, True)
        except Exception:
            pass

    def _init_preview_slider(self):
        """프리뷰 슬라이더 초기화"""
        frames = self._main_window.frames
        if frames is None or frames.is_empty:
            self._preview_frame_slider.SetMax(1)  # 최소 1로 설정 (0은 assertion 에러)
            self._preview_frame_slider.SetValue(0)
            self._preview_frame_slider.Enable(False)
            self._preview_frame_label.SetLabel("0/0")
            return

        frame_count = frames.frame_count
        if frame_count <= 0:
            self._preview_frame_slider.SetMax(1)  # 최소 1로 설정
            self._preview_frame_slider.SetValue(0)
            self._preview_frame_slider.Enable(False)
            self._preview_frame_label.SetLabel("0/0")
            return

        self._preview_frame_slider.Enable(True)
        self._preview_frame_slider.SetMax(max(1, frame_count - 1))  # 최소 1로 설정
        self._preview_frame_index = max(0, min(self._preview_frame_index, frame_count - 1))
        self._preview_frame_slider.SetValue(self._preview_frame_index)
        self._preview_frame_label.SetLabel(f"{self._preview_frame_index + 1}/{frame_count}")

    def _update_size_estimate(self):
        """파일 크기 예상 업데이트"""
        try:
            frames = self._main_window.frames
            if frames is None or frames.is_empty:
                return

            if frames.frame_count <= 0 or frames.width <= 0 or frames.height <= 0:
                return

            # 설정 먼저 업데이트
            self._update_settings()

            # 파일 크기 추정
            estimated_size = GifEncoder.estimate_gif_size(frames, self._settings)
            estimated_size_mb = estimated_size / self.BYTES_PER_MB
            size_text = self._get_translation("save_dialog_size", "예상 크기:")
            self._size_label.SetLabel(f"{size_text} {estimated_size_mb:.2f} MB")

            # 원본 대비 압축률 계산
            original_size = frames.width * frames.height * 4 * frames.frame_count
            if original_size > 0:
                ratio = (estimated_size / original_size) * 100
                compression_ratio = 100 - ratio
                self._comparison_label.SetLabel(
                    f"원본 대비 약 {ratio:.1f}% (압축률: {compression_ratio:.1f}%)\n"
                    f"양자화: {self._quant_combo.GetStringSelection()} | "
                    f"색상 수: {self._settings.colors} | "
                    f"디더링: {'ON' if self._settings.dithering else 'OFF'}"
                )
                self._comparison_label.Wrap(300)
        except Exception as e:
            error_text = self._get_translation("msg_error", "오류")
            self._size_label.SetLabel(f"{error_text}: {str(e)}")

    def _update_settings(self):
        """현재 UI에서 설정 가져오기"""
        sel = self._quant_combo.GetSelection()
        if sel != wx.NOT_FOUND:
            self._settings.quantization = self._quant_combo.GetClientData(sel)

        self._settings.colors = self._colors_slider.GetValue()
        self._settings.dithering = self._dither_check.GetValue()
        self._settings.optimize = self._optimize_check.GetValue()

        # 알고리즘 설명 업데이트
        self._quant_desc.SetLabel(self.QUANT_DESCRIPTIONS.get(self._settings.quantization, ""))
        self._quant_desc.Wrap(300)

    def _on_preview_frame_changed(self, event):
        """프리뷰 프레임 슬라이더 변경"""
        frames = self._main_window.frames
        if frames is None or frames.is_empty:
            return

        frame_count = frames.frame_count
        if frame_count <= 0:
            return

        value = self._preview_frame_slider.GetValue()
        value = max(0, min(value, frame_count - 1))
        self._preview_frame_index = value

        self._preview_frame_label.SetLabel(f"{value + 1}/{frame_count}")
        # 프레임 변경 시 오프셋 초기화
        self._preview_offset_x = 0
        self._preview_offset_y = 0
        # 프리뷰 즉시 업데이트
        if self._show_quantized_preview:
            self._update_preview()
        else:
            self._update_preview_fast()

    def _update_preview_fast(self):
        """빠른 프리뷰 업데이트 (원본만 표시, 양자화 없음)"""
        try:
            frames = self._main_window.frames
            if frames is None or frames.is_empty:
                return

            frame_count = frames.frame_count
            if frame_count <= 0:
                return

            # 프리뷰 슬라이더 초기화
            if self._preview_frame_slider.GetMax() != max(1, frame_count - 1):
                self._init_preview_slider()

            frame_index = max(0, min(self._preview_frame_index, frame_count - 1))
            preview_frame = frames.get_frame(frame_index)
            if not preview_frame or not hasattr(preview_frame, 'image') or preview_frame.image is None:
                return

            # 원본 프레임만 빠르게 표시
            original_img = preview_frame.image.copy()
            if original_img.mode != 'RGBA':
                original_img = original_img.convert('RGBA')

            # PIL Image를 wx.Bitmap으로 변환
            preview_bitmap = self._pil_to_bitmap(original_img)

            if preview_bitmap is None or not preview_bitmap.IsOk():
                return

            # 원본 프리뷰 저장
            self._original_preview_bitmap = preview_bitmap

            # 줌 적용하여 표시
            self._update_preview_display()

            # 프리뷰 정보 업데이트
            preview_info_text = self._get_translation("save_dialog_preview_info", "원본 vs 압축 미리보기")
            self._preview_info.SetLabel(f"{preview_info_text} (원본)")

        except Exception:
            pass

    def _update_preview(self):
        """프리뷰 업데이트 (양자화 적용)"""
        try:
            frames = self._main_window.frames
            if frames is None or frames.is_empty:
                return

            frame_count = frames.frame_count
            if frame_count <= 0:
                return

            # 프리뷰 슬라이더 초기화
            if self._preview_frame_slider.GetMax() != max(1, frame_count - 1):
                self._init_preview_slider()

            frame_index = max(0, min(self._preview_frame_index, frame_count - 1))
            preview_frame = frames.get_frame(frame_index)
            if not preview_frame or not hasattr(preview_frame, 'image') or preview_frame.image is None:
                return

            # 설정 업데이트
            self._update_settings()

            # 양자화된 프리뷰 생성
            preview_img = GifEncoder.create_preview(preview_frame, self._settings)

            if preview_img is None:
                preview_img = preview_frame.image.copy()
                if preview_img.mode != 'RGBA':
                    preview_img = preview_img.convert('RGBA')

            # PIL Image를 wx.Bitmap으로 변환
            preview_bitmap = self._pil_to_bitmap(preview_img)

            if preview_bitmap is None or not preview_bitmap.IsOk():
                # 원본 프레임 이미지 사용
                original_img = preview_frame.image.copy()
                if original_img.mode != 'RGBA':
                    original_img = original_img.convert('RGBA')
                preview_bitmap = self._pil_to_bitmap(original_img)

            if preview_bitmap is None or not preview_bitmap.IsOk():
                self._preview_info.SetLabel("프리뷰 이미지 생성 실패")
                return

            # 원본 프리뷰 저장
            self._original_preview_bitmap = preview_bitmap

            # 줌 적용하여 표시
            self._update_preview_display()

            # 파일 크기 예상은 타이머로 지연 처리
            self._size_timer.StartOnce(500)

            # 프리뷰 정보 업데이트
            quant_name = self.QUANT_NAMES.get(self._settings.quantization, "ADAPTIVE")
            self._preview_info.SetLabel(f"프레임 {frame_index + 1}/{frames.frame_count} - {quant_name} - {self._settings.colors}색")

        except Exception as e:
            self._preview_info.SetLabel(f"프리뷰 오류: {str(e)}")
            # 에러 발생 시 원본 프레임 이미지 표시 시도
            try:
                original_img = preview_frame.image.copy()
                if original_img.mode != 'RGBA':
                    original_img = original_img.convert('RGBA')
                preview_bitmap = self._pil_to_bitmap(original_img)
                if preview_bitmap and preview_bitmap.IsOk():
                    self._original_preview_bitmap = preview_bitmap
                    self._update_preview_display()
            except Exception:
                pass

    def _pil_to_bitmap(self, pil_image: Image.Image) -> Optional[wx.Bitmap]:
        """
        PIL Image를 wx.Bitmap으로 변환 (최적화됨)

        Args:
            pil_image: 변환할 PIL Image

        Returns:
            변환된 wx.Bitmap 또는 실패 시 None
        """
        if pil_image is None:
            return None

        try:
            # RGBA로 한 번만 변환
            if pil_image.mode != 'RGBA':
                pil_image = pil_image.convert('RGBA')

            # 이미지 크기 확인
            if pil_image.width <= 0 or pil_image.height <= 0:
                return None

            # 매우 큰 이미지는 프리뷰용으로 축소
            if pil_image.width > self.MAX_PREVIEW_DIM or pil_image.height > self.MAX_PREVIEW_DIM:
                pil_image.thumbnail((self.MAX_PREVIEW_DIM, self.MAX_PREVIEW_DIM), Image.Resampling.LANCZOS)

            # PIL Image → wx.Bitmap (최적화: 불필요한 변환 제거)
            width, height = pil_image.size

            # RGB 데이터와 Alpha 데이터를 한 번에 추출
            rgb_data = pil_image.tobytes('raw', 'RGB')
            alpha_data = pil_image.tobytes('raw', 'A')

            # wx.Image 생성 및 데이터 설정
            wx_image = wx.Image(width, height)
            wx_image.SetData(rgb_data)
            wx_image.SetAlpha(alpha_data)

            # wx.Bitmap 생성
            bitmap = wx.Bitmap(wx_image)
            return bitmap if bitmap.IsOk() else None

        except Exception:
            return None

    def _on_save(self, event):
        """저장 버튼 클릭"""
        # 파일 경로 선택
        start_dir = ""
        if self._main_window and hasattr(self._main_window, '_last_directory') and self._main_window._last_directory:
            start_dir = self._main_window._last_directory

        wildcard = (
            "GIF 파일 (*.gif)|*.gif|"
            "WebP 파일 (*.webp)|*.webp|"
            "APNG 파일 (*.apng;*.png)|*.apng;*.png|"
            "모든 파일 (*.*)|*.*"
        )

        dlg = wx.FileDialog(
            self,
            "애니메이션 저장",
            defaultDir=start_dir,
            wildcard=wildcard,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )

        if dlg.ShowModal() == wx.ID_OK:
            file_path = dlg.GetPath()

            # 확장자가 없으면 필터에 맞게 추가
            path = Path(file_path)
            if not path.suffix:
                filter_index = dlg.GetFilterIndex()
                if filter_index == 1:
                    file_path += ".webp"
                elif filter_index == 2:
                    file_path += ".png"
                else:
                    file_path += ".gif"

            self._file_path = file_path
            # 경로 저장
            self._main_window._last_directory = str(Path(file_path).parent)
            if hasattr(self._main_window, '_settings'):
                try:
                    self._main_window._settings.Write("last_directory", self._main_window._last_directory)
                except AttributeError:
                    pass  # wx.Config API가 다를 수 있음

            self.EndModal(wx.ID_OK)

        dlg.Destroy()

    def get_settings(self) -> EncoderSettings:
        """현재 설정 반환"""
        return self._settings

    def get_file_path(self) -> Optional[str]:
        """선택된 파일 경로 반환"""
        return self._file_path

    def _on_preview_mouse_press(self, event):
        """프리뷰 마우스 누름 이벤트"""
        if event.LeftDown() and self._preview_zoom > 1.0:
            self._preview_dragging = True
            self._preview_drag_start_x = event.GetX()
            self._preview_drag_start_y = event.GetY()
            self._preview_panel.SetCursor(wx.Cursor(wx.CURSOR_HAND))

    def _on_preview_mouse_move(self, event):
        """프리뷰 마우스 이동 이벤트"""
        if self._preview_dragging and self._preview_zoom > 1.0:
            # 드래그 거리 계산
            dx = event.GetX() - self._preview_drag_start_x
            dy = event.GetY() - self._preview_drag_start_y

            # 오프셋 업데이트
            self._preview_offset_x += int(dx)
            self._preview_offset_y += int(dy)

            # 드래그 시작 위치 업데이트
            self._preview_drag_start_x = event.GetX()
            self._preview_drag_start_y = event.GetY()

            # 프리뷰 업데이트
            self._update_preview_display()
        elif self._preview_zoom > 1.0:
            # 드래그 중이 아니지만 줌인이 되어 있으면 손 커서 표시
            self._preview_panel.SetCursor(wx.Cursor(wx.CURSOR_HAND))

    def _on_preview_mouse_release(self, event):
        """프리뷰 마우스 놓기 이벤트"""
        if event.LeftUp():
            self._preview_dragging = False
            if self._preview_zoom > 1.0:
                self._preview_panel.SetCursor(wx.Cursor(wx.CURSOR_HAND))
            else:
                self._preview_panel.SetCursor(wx.Cursor(wx.CURSOR_ARROW))

    def Destroy(self):
        """다이얼로그 닫힐 때 리소스 정리"""
        self._preview_timer.Stop()
        self._size_timer.Stop()
        # 프리뷰 리소스 해제
        self._original_preview_bitmap = None
        super().Destroy()
