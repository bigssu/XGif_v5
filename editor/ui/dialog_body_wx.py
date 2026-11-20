"""An editor dialog viewport with always-visible actions."""
import wx


class DialogBody(wx.ScrolledWindow):
    def __init__(self, dialog):
        super().__init__(dialog, style=wx.HSCROLL | wx.VSCROLL | wx.TAB_TRAVERSAL)
        self.SetScrollRate(*self.FromDIP((12, 12)))

    def install(self, content, actions):
        dialog = self.GetParent()
        self.SetSizer(content)
        width, height = content.CalcMin()
        self.SetMinSize((1, 1))
        for item in actions.GetChildren():
            button = item.GetWindow()
            if button is None:
                continue
            label = button.GetTextExtent(button.GetLabel())
            minimum = button.GetEffectiveMinSize()
            button.SetMinSize((max(minimum.width, label.width + dialog.FromDIP(20)),
                               max(minimum.height, label.height + dialog.FromDIP(8))))
        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(self, 1, wx.EXPAND)
        root.Add(actions, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, dialog.FromDIP(8))
        dialog.SetSizer(root)
        action_size = root.CalcMin()
        dialog.SetClientSize((max(width, action_size.width), height + action_size.height))
        self.FitInside()
