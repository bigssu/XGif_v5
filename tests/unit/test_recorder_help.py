import wx

from ui.help_dialog import BUG_REPORT_EMAIL, GITHUB_URL, HelpDialog
from ui.i18n import get_trans_manager


def test_recorder_help_live_language_and_narrow_layout():
    app = wx.GetApp() or wx.App(False)
    manager = get_trans_manager()
    previous = manager.current_lang
    manager.set_language("en")
    dialog = HelpDialog()
    try:
        dialog.SetSize(dialog.GetMinSize())
        dialog.Show()
        app.Yield()
        for lang, title, features, report, close, focus_word in (
                ("en", "Help", "Features", "Report a bug", "Close", "keyboard focus"),
                ("ko", "도움말", "주요 기능", "버그 신고", "닫기", "포커스")):
            manager.set_language(lang)
            assert dialog.GetTitle() == title
            assert dialog.notebook.GetPageText(1) == features
            assert dialog.report.GetLabel() == report
            assert dialog.close_button.GetLabel() == close
            assert focus_word in dialog.pages[2].GetValue()
            assert GITHUB_URL in dialog.pages[0].GetValue()
            assert BUG_REPORT_EMAIL in dialog.pages[0].GetValue()
            assert all(key in dialog.pages[2].GetValue() for key in ("F9", "F10", "F11", "Ctrl+D"))
            for index, page in enumerate(dialog.pages):
                dialog.notebook.SetSelection(index)
                app.Yield()
                assert page.GetSize().width > 100
                assert page.GetWindowStyle() & wx.TE_MULTILINE
                assert not page.GetWindowStyle() & wx.HSCROLL
                page.ShowPosition(page.GetLastPosition())
                if index == 1:
                    assert page.GetScrollPos(wx.VERTICAL) > 0
            buttons = [child for child in dialog.GetChildren() if isinstance(child, wx.Button)]
            rects = sorted((button.GetRect() for button in buttons), key=lambda rect: rect.x)
            assert len(rects) == 3
            assert all(left.GetRight() < right.GetLeft() for left, right in zip(rects, rects[1:]))
            assert rects[-1].GetRight() < dialog.GetClientSize().width
    finally:
        dialog.Close()
        app.ProcessPendingEvents()
        app.Yield()
        manager.set_language(previous)
    assert dialog._translate not in manager._callbacks
