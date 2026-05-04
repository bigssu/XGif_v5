"""
RotateToolbar - 회전 인라인 툴바 (wxPython 버전)
"""
import wx
from typing import TYPE_CHECKING
from .base_toolbar_wx import InlineToolbarBase

if TYPE_CHECKING:
    from ..main_window import MainWindow


class RotateToolbar(InlineToolbarBase):
    """회전 인라인 툴바 (wxPython)

    프레임 회전 옵션을 제공합니다.
    """

    _has_clear_button = False
    _has_action_buttons = False

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(main_window, parent)
        self._setup_controls()

    def _setup_controls(self):
        """컨트롤 설정"""
        translations = getattr(self._main_window, '_translations', None)

        # 회전 아이콘
        rotate_tooltip = translations.tr("rotate_tooltip") if translations else "회전"
        self.add_icon_label("rotate", 20, rotate_tooltip)

        # 회전 드롭다운 메뉴
        self._rotate_combo = wx.ComboBox(self._controls_widget, style=wx.CB_READONLY,
                                        choices=["0°", "90°", "180°", "270°"])
        self._rotate_combo.SetSelection(0)  # 기본값: 0°
        self._rotate_combo.SetMinSize((80, -1))
        angle_tooltip = translations.tr("rotate_angle") if translations else "회전 각도"
        self._rotate_combo.SetToolTip(angle_tooltip)
        self._rotate_combo.Bind(wx.EVT_COMBOBOX, self._on_rotate_changed)
        self.add_control(self._rotate_combo)

    def _on_rotate_changed(self, event):
        """회전 드롭다운 변경"""
        angles = [0, 90, 180, 270]
        index = self._rotate_combo.GetSelection()
        if 0 <= index < len(angles):
            angle = angles[index]
            if angle == 0:
                # 0도는 아무것도 하지 않음
                return
            self._apply_rotate(angle)

    def _apply_rotate(self, angle: int):
        """회전 적용 (선택 즉시 적용 후 툴바 닫기)"""
        if self.frames and not getattr(self.frames, 'is_empty', False) and hasattr(self._main_window, '_rotate_frames'):
            self._main_window._rotate_frames(angle)
            self._finish_apply()

    def _on_activated(self):
        """툴바 활성화"""
        self._rotate_combo.SetSelection(0)

    def _on_deactivated(self):
        """툴바 비활성화"""
        pass

    def reset_to_default(self):
        """기본값으로 초기화"""
        pass
