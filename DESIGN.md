# XGif Design System

This project uses a Figma-inspired desktop editor language adapted from:
https://github.com/VoltAgent/awesome-design-md/tree/main/design-md/figma

## Intent

XGif is a practical media capture and frame-editing tool. The UI should feel like
a focused creative workspace: bright canvas, black ink, quiet chrome, and a small
set of expressive color blocks for edit actions.

## Color Roles

- Canvas: `#f7f7f5` for the application background.
- Surface: `#ffffff` for bars, panels, dialogs, and edit controls.
- Soft Surface: `#f1f1f1` for inputs and secondary controls.
- Ink: `#111111` for primary text.
- Muted Ink: `#464646` and `#727272` for metadata.
- Hairline: `#e6e6e6` for separators and control borders.
- Primary Action: `#c5b0f4` for selected/edit-apply states.
- Attention Accent: `#ff3d8b` for version, active tool outline, and high-signal highlights.
- Success: `#1ea64a`; warning: `#b17600`; danger: `#d32f2f`.

## Component Rules

- Keep editor chrome light and low contrast; the media preview should be the focal point.
- Use hairline borders on tool buttons and panels instead of heavy shadows.
- Tool buttons may be rounded icon surfaces; text buttons stay compact.
- Reserve magenta for active/high-signal states, not large backgrounds.
- Keep frame list, canvas, toolbar, and property controls on the same shared token system.

## Do Not

- Do not reintroduce one-off hard-coded UI colors when a semantic token exists.
- Do not mix a separate dark toolbar palette into the editor without updating the shared theme.
- Do not add decorative gradients or large marketing-style blocks to the desktop workspace.
