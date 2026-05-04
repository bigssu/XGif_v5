# XGif UI Review Remediation

## Score

Code-based UI audit score after this pass: **20/24**.

| Pillar | Before | After | Evidence |
| --- | ---: | ---: | --- |
| Copywriting | 2 | 3 | RotateToolbar labels now use `resources/i18n/en.json` and `resources/i18n/ko.json` instead of hardcoded Korean strings. |
| Visuals | 2 | 3 | Instant RotateToolbar no longer shows unrelated Apply/Cancel actions. Shared action buttons are created through one helper. |
| Color | 2 | 4 | Action, save, language-toggle, and icon active/disabled colors now route through semantic `Colors` tokens. |
| Typography | 3 | 3 | Language toggle uses `Fonts.get_font(...)`; broader dialog typography remains for a later pass. |
| Spacing | 2 | 3 | Shared action button sizing is centralized; large fixed desktop layouts remain. |
| Experience Design | 2 | 4 | Speed cancel restores preview state, and Rotate selection is now an immediate apply-and-close action without a fake cancel contract. |

## Changes Locked By Tests

- `tests/unit/editor/test_ui_review_contracts.py` locks the immediate RotateToolbar contract.
- `tests/unit/editor/test_ui_review_contracts.py` locks semantic token usage for action buttons, save button, language toggle, and icon active state.
- `tests/unit/editor/test_speed_toolbar.py` still locks SpeedToolbar cancel restoration.

## Remaining UI Gaps

- Empty canvas copy and several menu/dialog strings still need broader i18n cleanup.
- `SaveDialog` still uses a fixed `900x550` layout.
- Icon-only toolbar discoverability still depends heavily on tooltips.
