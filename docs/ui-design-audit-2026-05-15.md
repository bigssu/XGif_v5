# XGif UI Design Audit and Improvement Plan

Date: 2026-05-15

## Scope

This audit is based on repository inspection, not a live wxPython screenshot review. The target is the full desktop UI surface:

- Recorder shell: `ui/main_window.py`, `ui/capture_control_bar.py`, settings/help/dependency dialogs.
- Editor shell: `editor/ui/editor_main_window_wx.py`, canvas, toolbar, frame list, property bars, save dialog, inline toolbars.
- Existing review context: `docs/xgif-setup/11-UI-REVIEW.md`.

The `design-taste-frontend` rules are applied as desktop UI principles. React, Next.js, Tailwind, and browser-specific package rules are not applicable to this wxPython app.

## Executive Verdict

XGif already has a stronger foundation than a generic desktop utility: there is a dark theme token layer, owner-drawn controls, semantic status colors, and a professional editor cockpit structure. The weak point is not lack of styling. The weak point is that the UI system is split across mature custom components, older native wx form patterns, fixed-size layouts, and ad hoc copy/state handling.

Current design quality estimate: 68/100.

The fastest quality gain is to consolidate the design system and refactor the highest-visibility surfaces first:

1. Recorder control bar and status area.
2. Save/settings/dependency dialogs.
3. Editor toolbar discoverability and responsive layout.
4. Empty/loading/error state system.
5. i18n and user-facing copy cleanup.

## Strengths

### Dark Design Foundation Exists

`ui/theme.py` defines a coherent dark palette, semantic status colors, font sizes, spacing, and dialog helpers. `ThemedDialog` centralizes dark-theme application and content fitting. This is the right foundation to extend rather than replace.

Evidence:

- `ui/theme.py`: `Colors`, `Fonts`, `Spacing`, `Sizes`, `ThemedDialog`.
- `editor/ui/style_constants_wx.py` re-exports the shared theme layer for editor code.

### Editor Uses Custom Tool Components

The editor toolbar uses owner-drawn icon buttons with hover, pressed, active, disabled, and tooltip states. Inline property toolbars use wrapped layouts and dynamic height synchronization.

Evidence:

- `editor/ui/icon_toolbar_wx.py`: `FlatIconButton`, `IconToolbar`.
- `editor/ui/inline_toolbars/base_toolbar_wx.py`: wrapping, active height calculation, cached sizing.
- `editor/ui/property_bar_wx.py`: active-tool toolbar switching.

### Visual Density Matches a Utility App

The app is not trying to behave like a marketing site. The recorder is compact and the editor is dense, which fits a capture/editing utility. This should be preserved.

## Priority Findings

### P0: Design System Is Split Across Surfaces

The core theme exists, but multiple UI areas still define local sizing, local colors, local fixed dimensions, and native control styling. This produces visible drift between the recorder, editor, and dialogs.

Evidence:

- `ui/theme.py`: shared palette and sizing exist.
- `ui/capture_control_bar.py`: custom `FlatButton` owns separate button behavior and fixed dimensions.
- `editor/ui/icon_toolbar_wx.py`: separate icon button system.
- `editor/ui/save_dialog_wx.py`: local preview/layout constants and fixed dialog dimensions.
- `ui/dependency_dialogs.py`: native `wx.ProgressDialog` breaks dark visual continuity.

Impact:

- Controls look related but not fully systematic.
- Dialogs feel older than the main editor surface.
- Future UI changes require per-screen patching.

Recommended fix:

Create a small desktop design-system layer on top of `ui/theme.py`:

- `CommandButton`: text, icon, and icon+text variants.
- `IconButton`: shared owner-drawn implementation for recorder and editor.
- `StatusPill`: recording, paused, encoding, ready, warning, error.
- `InlineBanner`: non-modal success/warning/error/info messages.
- `FormSection` and `FormRow`: replace repeated `StaticBoxSizer` forms.
- `ThemedProgressDialog`: replace native dependency install progress.

Keep this wx-native. Do not introduce a web UI framework.

### P0: Recorder Control Bar Uses Text Glyphs As Icons

The recorder bar uses symbolic text labels for core tools: cursor, region, record, pause, settings, help, stop, and play. This makes icon weight, alignment, localization, and accessibility inconsistent.

Evidence:

- `ui/capture_control_bar.py`: labels such as cursor/region glyphs, `REC`, pause bars, settings glyph, help mark, stop/play labels.
- Editor already has an `IconFactory` pattern and owner-drawn icon buttons.

Impact:

- The main first-run surface looks less polished than the editor.
- Text glyph rendering varies by OS/font.
- Button width depends on label content, which works against stable command sizing.

Recommended fix:

Refactor recorder controls to use shared owner-drawn icon buttons:

- Draw record, stop, pause, cursor, region, settings, and help icons with `IconFactory` or a shared vector drawing helper.
- Keep visible text only for the primary record/stop button, using a drawn icon plus short label.
- Use tooltips for secondary clarification, not as the only source of meaning for primary actions.
- Preserve stable hit targets: minimum 32 px for compact secondary controls, 40 px for primary controls.

### P0: Fixed-Size Layouts Limit Responsiveness

Several important screens set hard minimum sizes or fixed preview/control dimensions. This will fail on smaller laptops, high DPI scaling, translated strings, and accessibility font scaling.

Evidence:

- `ui/constants.py`: main window minimum 900 x 160.
- `editor/ui/editor_main_window_wx.py`: editor initialized around 1008 x 840 minimum after a larger default size.
- `editor/ui/save_dialog_wx.py`: fixed 900 x 550 minimum and fixed 440 x 320 preview.
- `ui/settings_dialog.py`: fixed 520 x 580 starting size with fixed label widths.
- `ui/dependency_dialogs.py`: fixed dialog sizes and hardcoded text wrap widths.

Impact:

- Text clipping risk increases with Korean/English switching.
- Save dialog cannot adapt to narrow screens.
- UI cannot offer compact and comfortable density modes cleanly.

Recommended fix:

- Convert dialogs to `wx.FlexGridSizer`, `wx.WrapSizer`, or splitter-based layouts where appropriate.
- Replace fixed preview sizes with aspect-ratio bounded flexible panels.
- Keep minimums only where interaction would break below that size.
- Add layout smoke tests that instantiate dialogs and assert `GetBestSize()` stays within target bounds.

### P1: Toolbar Discoverability Depends Too Much On Tooltips

The editor toolbar is visually clean but heavily tooltip-dependent. This is acceptable for expert repeat use, but weak for first-use discoverability and feature learning.

Evidence:

- `editor/ui/icon_toolbar_wx.py`: icon-only buttons with tooltips.
- `docs/xgif-setup/11-UI-REVIEW.md`: already notes icon-only toolbar discoverability as a remaining gap.

Impact:

- New users need hover exploration to understand editor commands.
- Touchpad/tablet users and keyboard users get less immediate guidance.
- Advanced tools look hidden despite being available.

Recommended fix:

Add adaptive toolbar labeling:

- Compact mode: icon-only, current behavior.
- Comfortable mode: show short group labels or text under primary tools.
- Overflow mode: visible overflow affordance instead of hidden scrollbar behavior.
- Persist toolbar density in settings.

### P1: Dialogs Still Use Older Form-Sheet Visual Hierarchy

Settings, save, and tool dialogs often rely on `StaticBoxSizer`, fixed label widths, native buttons, and dense rows. This is functional but not visually aligned with the premium custom editor surface.

Evidence:

- `ui/settings_dialog.py`: repeated static-box groups and fixed row label widths.
- `editor/ui/save_dialog_wx.py`: fixed two-column form layout and native buttons.
- `editor/ui/dialogs/*`: many fixed-size wx dialogs and Korean literals.

Impact:

- Dialogs feel less modern than the main editor.
- Related controls are grouped, but hierarchy depends on boxes rather than spacing, headings, and component language.
- Validation and disabled states are harder to scan.

Recommended fix:

Refactor dialogs around section components:

- Section title, optional short description, rows, and inline validation.
- Consistent bottom action bar: primary, secondary, cancel.
- Avoid nested card-like panels; use full-width sections and spacing.
- Move destructive or risky actions into clearly styled secondary rows.

### P1: User Feedback Is Too Modal And Inconsistent

The app still uses many `wx.MessageBox` calls and native progress dialogs. Some modal errors are appropriate, but routine validation, missing dependency states, and recoverable warnings should be inline.

Evidence:

- `ui/main_window.py`: validation and encoding warnings use message boxes in several flows.
- `editor/ui/editor_main_window_wx.py`: many hardcoded `wx.MessageBox` calls.
- `ui/dependency_dialogs.py`: native progress dialogs for install flows.
- `editor/ui/canvas_widget_wx.py`: custom empty canvas state exists, but copy and i18n are incomplete.

Impact:

- Errors interrupt workflows.
- Warnings look different depending on where they appear.
- Users cannot always see what changed after dismissing a modal.

Recommended fix:

Introduce a shared feedback system:

- Inline banners for recoverable warnings and validation.
- Status pills for long-running states.
- Themed progress dialog for install or export operations.
- Toast-like transient notices only for low-risk confirmations.
- Modal dialogs only for destructive confirmation, unrecoverable failure, or permission/security boundaries.

### P1: i18n And Copy Are Still Fragmented

Several screens still contain direct Korean strings and hardcoded tooltips. Existing translation utilities are not consistently applied.

Evidence:

- `docs/xgif-setup/11-UI-REVIEW.md`: remaining i18n cleanup is already listed.
- `ui/main_window.py`: remaining Korean validation/error message strings.
- `editor/ui/editor_main_window_wx.py`: many Korean `wx.MessageBox` strings and labels.
- `editor/ui/save_dialog_wx.py`: Korean title, labels, preview failure message.
- `editor/ui/dialogs/*`: multiple direct Korean labels.

Impact:

- English/Korean mode can produce mixed-language UI.
- Layout cannot be verified for translated string expansion.
- Copy tone is inconsistent across app areas.

Recommended fix:

- Route all visible strings through the existing translation surface.
- Add a lint-style check for direct Korean literals in UI files, with an allowlist for tests and translation dictionaries.
- Define copy patterns for validation, dependency, capture, editor, and export states.
- Re-test layout under Korean and English.

### P2: Motion And Micro-Feedback Should Be Intentional, Not Decorative

The app has hover and active states, which are appropriate. It does not need decorative animation. It does need clearer progress, loading, and state transitions.

Recommended fix:

- Add subtle timer-driven feedback only for active operations: dependency install, GIF encoding, preview generation, capture preparation.
- Keep animations short and cancelable.
- Avoid decorative background effects, gradient blobs, and non-functional motion.

### P2: Accessibility Needs A Concrete Pass

The app has many compact controls, icon-only buttons, and fixed text regions. Keyboard focus, tab order, tool names, and high-DPI text behavior should be verified.

Recommended fix:

- Ensure all command buttons have accessible names via labels or tooltips.
- Add visible focus indicators to custom buttons.
- Audit tab order in recorder, settings, save, and editor shells.
- Validate at 125 percent and 150 percent Windows scaling.

## Improvement Roadmap

### Phase 1: Consolidate Desktop Design System

Target result: one shared component language across recorder, editor, and dialogs.

Work:

- Extend `ui/theme.py` with semantic layout tokens: density, control sizes, section spacing, focus ring, dialog widths.
- Create shared command controls for text, icon, and icon+text buttons.
- Create `FormSection`, `FormRow`, `StatusPill`, `InlineBanner`, and `ThemedProgressDialog`.
- Migrate duplicated owner-drawn button logic into shared primitives.

Acceptance criteria:

- Recorder and editor use the same icon button primitives.
- Native wx buttons are limited to system-native cases or wrapped by themed helpers.
- Dialog section spacing and action bars are consistent.

### Phase 2: Upgrade Recorder First Screen

Target result: the main capture surface looks as polished as the editor while staying compact.

Work:

- Replace text glyph command buttons in `ui/capture_control_bar.py`.
- Redesign the command rail into stable zones: capture mode, output settings, primary action, utility actions.
- Convert status/progress in `ui/main_window.py` into a compact status pill plus progress region.
- Add inline validation banners for invalid capture area, missing audio device, and missing encoder.

Acceptance criteria:

- No symbolic glyph labels are used as icons in recorder controls.
- Primary record/stop action remains obvious at first glance.
- Status, progress, and preview do not resize the control bar unexpectedly.

### Phase 3: Modernize Settings, Save, And Dependency Dialogs

Target result: dialogs feel like part of the same product, not separate wx defaults.

Work:

- Refactor `ui/settings_dialog.py` into responsive form sections.
- Refactor `editor/ui/save_dialog_wx.py` so preview and settings panes resize proportionally.
- Replace fixed wrap widths in dependency dialogs with layout-driven wrapping.
- Replace native install progress with themed progress UI.

Acceptance criteria:

- Save dialog works below the current 900 px minimum where practical.
- Dialogs pass Korean and English text expansion checks.
- Long-running dependency operations use dark themed progress.

### Phase 4: Improve Editor Discoverability

Target result: expert speed remains, but first-use discoverability improves.

Work:

- Add toolbar density modes: compact and comfortable.
- In comfortable mode, show short labels for primary tools or group labels.
- Add visible overflow affordance when toolbar content exceeds width.
- Normalize bottom action buttons to shared command components.

Acceptance criteria:

- Toolbar remains compact for expert users.
- New users can identify primary edit tools without hovering every icon.
- Overflow is visually discoverable.

### Phase 5: Centralize Feedback, Copy, And i18n

Target result: consistent user-facing language and state feedback.

Work:

- Replace routine `wx.MessageBox` flows with inline banners where recoverable.
- Keep modal dialogs for destructive or unrecoverable actions.
- Move all visible strings to translation dictionaries.
- Add a repository check for direct Korean literals in UI implementation files.

Acceptance criteria:

- English/Korean modes do not mix languages on audited screens.
- Recoverable validation appears inline.
- Hardcoded user-facing strings are blocked by test or lint.

### Phase 6: Verification System

Target result: UI quality does not regress silently.

Work:

- Add lightweight instantiation tests for major dialogs and shells.
- Add static checks for fixed-size dialog anti-patterns with explicit allowlists.
- Add static checks for symbolic text icons in command labels.
- Add manual visual QA checklist for Windows scaling: 100, 125, 150 percent.

Acceptance criteria:

- New UI changes have automated guardrails.
- Manual QA checklist is short, repeatable, and tied to known risk surfaces.

## Suggested Implementation Order

1. Build shared command/button/status/form primitives.
2. Migrate recorder control bar and status area.
3. Refactor save dialog and dependency progress.
4. Refactor settings dialog.
5. Add editor toolbar density/overflow improvements.
6. Centralize message/copy/i18n cleanup.
7. Add static UI regression checks.

## Stop Condition

The UI improvement effort should be considered complete when:

- Recorder, editor, and dialogs share the same command/control primitives.
- Fixed-size dialog constraints are removed or explicitly justified.
- Icon-only surfaces have either labels, group labels, or clear overflow/discoverability affordances.
- Recoverable feedback is inline and themed.
- Korean and English UI strings are consistently routed through translation utilities.
- Targeted UI static checks and dialog instantiation tests pass.

