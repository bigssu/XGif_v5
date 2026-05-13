"""
PropertyBar - 도구별 속성 바 컨테이너 (wxPython)

한 번에 하나의 인라인 툴바만 표시하는 스택형 컨테이너.
도구 미선택 시 PropertyBar 자체가 숨겨져 캔버스가 전체 공간을 차지합니다.
"""
import wx
from .style_constants_wx import Colors


class PropertyBar(wx.Panel):
    """도구별 속성 바 컨테이너"""

    def __init__(self, parent):
        super().__init__(parent, style=wx.BORDER_NONE)
        self.SetBackgroundColour(Colors.BG_PRIMARY)

        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)

        self._toolbars = {}  # name -> toolbar
        self._active_name = None

        self.Bind(wx.EVT_SIZE, self._on_size)

        self.Hide()

    def register_toolbar(self, name, toolbar):
        """툴바 등록 (Reparent → self, 숨김)"""
        toolbar.Reparent(self)
        toolbar.Hide()
        self._sizer.Add(toolbar, 0, wx.EXPAND)
        self._toolbars[name] = toolbar

    def show_toolbar(self, name):
        """지정 툴바만 표시, 나머지 숨김, PropertyBar 자체 Show"""
        if name not in self._toolbars:
            return

        for n, tb in self._toolbars.items():
            if n == name:
                tb.Show()
            else:
                tb.Hide()

        self._active_name = name
        self.Show()
        self.sync_active_toolbar_height()
        self.GetParent().Layout()

    def hide_all(self):
        """모든 툴바 숨김, PropertyBar 자체 Hide"""
        for tb in self._toolbars.values():
            tb.Hide()
        self._active_name = None
        self.SetMinSize((-1, 0))
        self.Hide()
        self.GetParent().Layout()

    def _on_size(self, event):
        self.sync_active_toolbar_height()
        event.Skip()

    def sync_active_toolbar_height(self):
        """Resize the property bar to the active toolbar's wrapped height."""
        toolbar = self._toolbars.get(self._active_name)
        if not toolbar or not toolbar.IsShown():
            return

        height = toolbar.sync_layout_height(notify_parent=False)
        if self.GetMinSize().GetHeight() != height:
            self.SetMinSize((-1, height))

        self.Layout()
        parent = self.GetParent()
        if parent:
            parent.Layout()

    @property
    def active_toolbar_name(self):
        """현재 활성 툴바 이름 반환"""
        return self._active_name
