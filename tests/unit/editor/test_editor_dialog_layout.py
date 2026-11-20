"""Native, hidden-window checks for editor dialogs on constrained work areas."""
import importlib
import pytest
import wx
from editor.core import FrameCollection
from editor.ui.dialog_body_wx import DialogBody
from editor.ui.icon_toolbar_wx import IconToolbar
from editor.ui.save_dialog_wx import SaveDialog
from ui.i18n import EditorTranslations, get_trans_manager


@pytest.fixture(scope="module")
def editor_parent():
    app = wx.GetApp() or wx.App(False)
    parent = wx.Frame(None)
    parent.frames = parent._frames = FrameCollection()
    parent._translations = EditorTranslations()
    yield parent
    parent.Destroy()
    app.ProcessPendingEvents()


@pytest.mark.parametrize('language', ['ko', 'en'])
@pytest.mark.parametrize('tool', ['crop', 'resize', 'pencil', 'speed', 'effects', 'sticker', 'text', 'target_frame_hint', 'save'])
def test_editor_actions_stay_visible_with_scrollable_settings(editor_parent, language, tool):
    manager = get_trans_manager()
    previous = manager.get_language()
    original_font = editor_parent.GetFont()
    large_font = wx.Font(original_font)
    large_font.SetPointSize(round(original_font.GetPointSize() * 1.5))
    editor_parent.SetFont(large_font)
    manager.set_language(language)
    dialog = None
    try:
        if tool == 'save':
            dialog = SaveDialog(editor_parent)
        else:
            module = importlib.import_module(f'editor.ui.dialogs.{tool}_dialog_wx')
            dialog_class = getattr(module, ''.join(w.capitalize() for w in tool.split('_'))+'Dialog')
            dialog = dialog_class(editor_parent)
        dialog.fit_to_content()
        dialog.SetMinSize((1, 1))
        dialog.SetClientSize((600, 380))
        dialog.Layout()
        body = next(child for child in dialog.GetChildren() if isinstance(child, DialogBody))
        body.Layout()
        body.FitInside()
        controls = dialog.GetSizer().GetItem(1).GetSizer()
        for item in controls.GetChildren():
            button = item.GetWindow()
            if button is None:
                continue
            rect = button.GetRect()
            assert rect.y >= body.GetRect().GetBottom()
            assert rect.height > 12 and rect.width >= button.GetTextExtent(button.GetLabel())[0]
            assert dialog.GetClientRect().Contains(rect)
        natural = body.GetSizer().CalcMin()
        assert body.GetVirtualSize().width >= natural.width
        assert body.GetVirtualSize().height >= natural.height
    finally:
        if dialog is not None:
            dialog.Destroy()
        manager.set_language(previous)
        editor_parent.SetFont(original_font)


def test_editor_toolbar_exposes_last_tool_on_narrow_window(editor_parent):
    toolbar = IconToolbar(editor_parent, editor_parent)
    try:
        toolbar.SetSize((510, 86))
        toolbar.Layout()
        viewport = toolbar._scroll_panel
        viewport.FitInside()
        assert viewport.HasScrollbar(wx.HORIZONTAL)
        viewport.Scroll(viewport.GetScrollRange(wx.HORIZONTAL), 0)
        x, y = viewport.ScreenToClient(toolbar._all_buttons[-1].ClientToScreen((0, 0)))
        assert 0 <= x < x + toolbar._all_buttons[-1].GetSize().width <= viewport.GetClientSize().width
    finally:
        toolbar.Destroy()
