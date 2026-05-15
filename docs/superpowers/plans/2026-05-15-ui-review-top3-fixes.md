# UI Review Top-3 Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the three top-priority findings from `docs/UI-REVIEW-2026-05-15.md`: (1) full editor-surface i18n, (2) unpin the editor window from a fixed 1008×840, (3) add `FormSection`/`FormRow` primitives and converge the owner-drawn button stacks.

**Architecture:** XGif is a Windows wxPython 4.2.5 desktop app. Translations route through the singleton-backed module function `tr(key, default=None, **kwargs)` in `ui/i18n.py`; strings live as flat dicts under `{"main": {...}, "editor": {...}}` in `resources/i18n/en.json` and `resources/i18n/ko.json` (both sections merged at load). `editor/` importing `ui/i18n.py` is explicitly permitted by `.claude/rules/architecture-boundaries.md` (국제화 row). Window-size responsiveness reuses the proven display-clamp pattern from `ThemedDialog.fit_to_content` in `ui/theme.py`. Shared UI primitives live in `ui/design_system.py`; static contracts are locked in `tests/unit/test_ui_design_system_contracts.py`.

**Tech Stack:** Python 3.11.9 (`.venv/Scripts/python.exe`), wxPython 4.2.5, pytest, ruff (line-length 120, py311). Run tests: `.venv/Scripts/python.exe -m pytest tests/ -v`. Lint: `.venv/Scripts/python.exe -m ruff check . --fix`.

---

## Scope & Independence

The three fixes are independent subsystems and may be executed in any order. They map to `docs/UI-REVIEW-2026-05-15.md` "Top 3 Priority Fixes" #1/#2/#3. **Recommended execution order: Part B → Part C → Part A** (smallest/lowest-risk first, biggest last), but the user requested all three; numbering below follows the audit's Top-3 order. Each Part produces working, committable software on its own.

**Grade (per `.claude/rules/workflow-orchestrator.md`):** L-grade. Touches `editor/ui/` (CRITICAL_DIR), `ui/design_system.py`, `ui/settings_dialog.py`. After implementation, STEP 3 `/test-automation` and STEP 4 `/code-reviewer` are expected per the harness; that routing is out of this plan's scope (this plan is STEP 2 Implement) but is flagged in the Execution Handoff.

**Explicit non-goals (do NOT do these — scope guards):**
- No live language re-translation (`retranslateUi`) for persistent editor chrome. Editor language is fixed at startup via `EditorTranslations(is_korean=...)`. Editor dialogs are modal and recreated per open, so they pick up the current language at construction. Adding live-switch to the editor menubar/main window is a separate concern and is OUT of scope. Only the recorder side already has `retranslateUi`; do not extend it into the editor here.
- No visual redesign. i18n is string-routing only; do not change layouts, colors, or widget types while routing strings (except where Part C explicitly refactors `settings_dialog.py`).
- No new translation languages. Only `ko` (verbatim existing literal) and `en` (authored per the glossary).
- No edits to `cli/` or `core/` (no `import wx` there — architecture boundary).

---

## Shared Conventions (apply to EVERY Part A task)

### S1. i18n key namespace & naming

All new keys go in the **`"editor"`** section of BOTH `resources/i18n/en.json` and `resources/i18n/ko.json`. Keys are flat `lower_snake_case`, domain-prefixed, matching existing convention (`effects_*`, `text_*`, `sticker_*`, `crop_*`, `resize_*`, `speed_*`, `pencil_*`, `msg_*`, `menu_*`, `toolbar_*`, `frame_list_*`, `help_*`, `canvas_*`). Reuse an existing key if one already covers the exact string (the per-file tables below mark `[EXISTS]` where applicable — verify before adding a duplicate).

### S2. JSON edit pattern (both files, every task)

`en.json` and `ko.json` have identical key sets. For each new key:
- `ko.json` → value is the **verbatim existing Korean literal** (copy exactly, including punctuation, `\n`, trailing spaces, `•`/`•`).
- `en.json` → value is the **authored English** from the per-file table (already filled in below).
- Insert keys in the `"editor"` object, grouped by the file's domain prefix, keeping the file valid JSON (trailing-comma-free, UTF-8, 2-space indent to match existing style).
- After editing, validate: `.venv/Scripts/python.exe -c "import json; json.load(open('resources/i18n/en.json',encoding='utf-8')); json.load(open('resources/i18n/ko.json',encoding='utf-8')); print('json ok')"`

### S3. Editor translation-access idiom

In each editor source file being converted, add this import (top of file, with the other imports — `editor/` → `ui/i18n` is allowed):

```python
from ui.i18n import tr
```

Then replace literals:
- `label="한글"` → `label=tr("key")`
- `wx.StaticBox(parent, label="한글")` → `wx.StaticBox(parent, label=tr("key"))`
- `wx.MessageBox("한글", "제목", ...)` → `wx.MessageBox(tr("key"), tr("title_key"), ...)`
- f-strings with interpolation → use `tr()` named-arg formatting (the manager calls `text.format(**kwargs)`):
  - `f"현재 크기: {w} x {h} px"` → `tr("crop_info_size", w=w, h=h)` with EN `"Image size: {w} x {h} px"` / KO `"이미지 크기: {w} x {h} px"`
- ComboBox/choice lists → build the list with `tr()` per element.
- For files that ALREADY hold a translations instance (`self._translations`, `translations` param, `EditorTranslations`), keep using `self._translations.tr("key")` / `translations.tr("key")` for consistency with that file — it reaches the same singleton. Only add `from ui.i18n import tr` when the file has no translations handle. The per-file tasks state which idiom that file uses.

For `target_frame_hint_dialog_wx.py` specifically: it already has a `_tr()` with a hardcoded `defaults` dict and an optional `translations`. Keep `_tr()`, but (a) move its title off the hardcoded `"대상 프레임 선택"` to `self._tr("target_frame_hint_title")`, and (b) make `_tr()` fall back to module `tr()` instead of returning bare Korean: change the `defaults` path to `return tr(key, defaults.get(key, key))`. Add `from ui.i18n import tr`.

### S4. Translation glossary (EN canonical — use these EXACT strings for consistency)

| Korean | English |
|---|---|
| 적용 | Apply |
| 취소 | Cancel |
| 확인 (button) | OK |
| 확인 (dialog title / "하시겠습니까?") | Confirm |
| 초기화 | Reset |
| 추가 | Add |
| 오류 | Error |
| 경고 | Warning |
| 알림 | Notice |
| 완료 | Done |
| 메모리 경고 | Memory Warning |
| 메모리 부족 | Out of Memory |
| 너비: | Width: |
| 높이: | Height: |
| 크기: | Size: |
| 대상: | Target: |
| 색상 | Color |
| 색상 선택 | Pick Color |
| 미리보기 | Preview |
| 크기 | Size |
| 적용 대상 | Apply To |
| 현재 프레임만 | Current frame only |
| 선택한 프레임 | Selected frames |
| 모든 프레임 | All frames |
| 모두 | All |
| 선택 | Selected |
| 현재 | Current |
| 메모리가 부족하여 작업을 수행할 수 없습니다. | Not enough memory to perform this operation. |
| GIF 파일을 먼저 열어주세요 | Open a GIF file first. |
| Undo 오류:\n{e} | Undo error:\n{e} |
| 저장 | Save |
| 저장 완료 | Saved |
| 저장 실패:\n{e} | Save failed:\n{e} |

Any recurring Korean term not in this table: translate concisely in product-UI register (sentence case, no trailing period for labels/buttons; keep the period for full-sentence messages; preserve `\n` exactly).

### S5. Code transformation — worked archetype examples

**Archetype 1 — StaticBox form dialog (`effects_dialog_wx.py` excerpt):**

Before:
```python
self.adjust_box = wx.StaticBox(panel, label="조정")
apply_btn = wx.Button(self, wx.ID_OK, label="적용")
```
After:
```python
from ui.i18n import tr  # top of file
...
self.adjust_box = wx.StaticBox(panel, label=tr("effects_tab_adjust"))
apply_btn = wx.Button(self, wx.ID_OK, label=tr("common_apply"))
```

**Archetype 2 — `wx.MessageBox` (editor_main_window_wx.py uses `self` as parent):**

Before:
```python
wx.MessageBox("메모리가 부족하여 작업을 수행할 수 없습니다.", "경고", wx.OK | wx.ICON_WARNING)
```
After:
```python
wx.MessageBox(tr("msg_out_of_memory"), tr("common_warning"), wx.OK | wx.ICON_WARNING)
```
(`editor_main_window_wx.py` already imports/holds `self._translations`; per S3 use `self._translations.tr("msg_out_of_memory")` there. Both reach the same singleton; the file-task states the idiom.)

**Archetype 3 — f-string with interpolation:**

Before:
```python
self._info_label.SetLabel(f"현재 크기: {self._original_width} x {self._original_height} px")
```
After:
```python
self._info_label.SetLabel(tr("resize_cur_size", w=self._original_width, h=self._original_height))
```
EN `"Current size: {w} x {h} px"`, KO `"현재 크기: {w} x {h} px"`. (The manager applies `.format(**kwargs)`; only pass simple named args, never positional.)

**Archetype 4 — choice/combo list:**

Before:
```python
wx.ComboBox(panel, choices=["현재 프레임만", "선택한 프레임", "모든 프레임"])
```
After:
```python
wx.ComboBox(panel, choices=[tr("target_current_only"), tr("target_selected_full"), tr("target_all_full")])
```
If later code compares against the literal (e.g. `crop_dialog_wx.py` `_apply_preset` compares to `"전체"`), compare against an index or a stable internal token, NOT the translated label. For `crop_dialog` presets: store preset id on the button (`btn.preset_id = "full"`) and switch on that, not on label text. The file-task spells this out.

**Archetype 5 — menu Append (accelerator suffix preserved):**

Before:
```python
self._file_menu.Append(wx.ID_ANY, "열기(&O)...\tCtrl+O")
```
After:
```python
self._file_menu.Append(wx.ID_ANY, tr("menu_open"))
```
EN `"Open(&O)...\tCtrl+O"`, KO `"열기(&O)...\tCtrl+O"`. **Keep the `\t<accel>` and `(&X)` mnemonic inside the translated value** — both ko and en values carry the exact accelerator/mnemonic; only the human-readable part differs.

### S6. Per-task TDD/commit ritual (every Part A file task ends with this)

After the code+JSON edits for a file:
1. `.venv/Scripts/python.exe -c "import json; json.load(open('resources/i18n/en.json',encoding='utf-8')); json.load(open('resources/i18n/ko.json',encoding='utf-8')); print('json ok')"` → expect `json ok`
2. `.venv/Scripts/python.exe -m ruff check editor/ui/<file> --fix` → expect no remaining errors
3. `.venv/Scripts/python.exe -m pytest tests/unit/test_ui_design_system_contracts.py -v` → expect PASS (no regression; key-presence asserts still green)
4. Commit: `git add <file> resources/i18n/en.json resources/i18n/ko.json && git commit -m "i18n: <file> 한글 리터럴 tr() 라우팅"`

---

# Part A — Fix #1: Full editor-surface i18n

**Files (created/modified):**
- Modify: `resources/i18n/en.json`, `resources/i18n/ko.json` (every task)
- Modify: `editor/ui/dialogs/effects_dialog_wx.py`, `pencil_dialog_wx.py`, `resize_dialog_wx.py`, `speed_dialog_wx.py`, `sticker_dialog_wx.py`, `text_dialog_wx.py`, `crop_dialog_wx.py`, `target_frame_hint_dialog_wx.py`, `help_dialog_wx.py`
- Modify: `editor/ui/editor_main_window_wx.py`, `editor/ui/frame_list_widget_wx.py`, `editor/ui/canvas_widget_wx.py`
- Modify: `editor/ui/inline_toolbars/pencil_toolbar_wx.py`, `resize_toolbar_wx.py`, `watermark_toolbar_wx.py`
- Create: test additions in `tests/unit/test_ui_design_system_contracts.py` (Task A14)

> **Common keys** (add ONCE in Task A1, reused everywhere): `common_apply`=Apply/적용, `common_cancel`=Cancel/취소, `common_ok`=OK/확인, `common_reset`=Reset/초기화, `common_add`=Add/추가, `common_error`=Error/오류, `common_warning`=Warning/경고, `common_notice`=Notice/알림, `common_done`=Done/완료, `common_width_label`=Width:/너비:, `common_height_label`=Height:/높이:, `common_size_label`=Size:/크기:, `target_current_only`=Current frame only/현재 프레임만, `target_selected`=Selected frames/선택한 프레임, `target_all`=All frames/모든 프레임, `target_all_short`=All/모두, `target_selected_short`=Selected/선택, `target_current_short`=Current/현재, `apply_to`=Apply To/적용 대상, `msg_out_of_memory`=Not enough memory to perform this operation./메모리가 부족하여 작업을 수행할 수 없습니다., `msg_gif_open_required`=Open a GIF file first./GIF 파일을 먼저 열어주세요, `msg_undo_error`=Undo error:\n{e}/Undo 오류:\n{e}.

> **⚠ TARGET-KEY TAXONOMY (CORRECTED post-A1 — supersedes any stale inline text below).** A1 commit `5c0b47a` discovered `target_selected`/`target_all`/`target_current` ALREADY EXIST as **short** combo labels (`Selected`/`선택`, `All`/`모두`, `Current`/`현재`) actively consumed by `editor/utils/frame_targeting.py:31-33` — these were **NOT** redefined. Authoritative mapping for all downstream A-tasks:
> - **Full-sentence dialog combo choices** ("현재 프레임만 / 선택한 프레임 / 모든 프레임") → use `target_current_only` (=Current frame only/현재 프레임만), `target_selected_full` (=Selected frames/선택한 프레임), `target_all_full` (=All frames/모든 프레임). **Never** use bare `target_selected`/`target_all` for the full form.
> - **Short combo choices** ("모두 / 선택 / 현재", e.g. pencil_dialog:141) → use the pre-existing `target_all` / `target_selected` / `target_current` (matches frame_targeting.py). The A1-added `target_*_short` keys are redundant duplicates of these short values; either works, but prefer the pre-existing `target_all`/`target_selected`/`target_current` for consistency with the existing consumer.
> - Do NOT add/overwrite `target_selected`/`target_all`/`target_current`.

---

### Task A1: Add common/shared i18n keys + smoke harness

**Files:**
- Modify: `resources/i18n/en.json`, `resources/i18n/ko.json`
- Test: `tests/unit/test_ui_design_system_contracts.py` (new test function)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_ui_design_system_contracts.py`:

```python
def test_editor_i18n_common_keys_present_in_both_locales():
    for locale_path in ("resources/i18n/ko.json", "resources/i18n/en.json"):
        data = json.loads(_read(locale_path))
        editor = data.get("editor", {})
        for key in (
            "common_apply", "common_cancel", "common_ok", "common_reset",
            "common_add", "common_error", "common_warning", "common_notice",
            "common_done", "common_width_label", "common_height_label",
            "common_size_label", "target_current_only", "target_selected",
            "target_all", "target_all_short", "target_selected_short",
            "target_current_short", "apply_to", "msg_out_of_memory",
            "msg_gif_open_required", "msg_undo_error",
        ):
            assert key in editor, f"{key} missing in {locale_path}"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ui_design_system_contracts.py::test_editor_i18n_common_keys_present_in_both_locales -v`
Expected: FAIL (`common_apply missing in resources/i18n/ko.json`).

- [ ] **Step 3: Add the keys to both JSON files**

In the `"editor"` object of `resources/i18n/en.json` add (EN values):
```
"common_apply": "Apply", "common_cancel": "Cancel", "common_ok": "OK",
"common_reset": "Reset", "common_add": "Add", "common_error": "Error",
"common_warning": "Warning", "common_notice": "Notice", "common_done": "Done",
"common_width_label": "Width:", "common_height_label": "Height:",
"common_size_label": "Size:", "target_current_only": "Current frame only",
"target_selected": "Selected frames", "target_all": "All frames",
"target_all_short": "All", "target_selected_short": "Selected",
"target_current_short": "Current", "apply_to": "Apply To",
"msg_out_of_memory": "Not enough memory to perform this operation.",
"msg_gif_open_required": "Open a GIF file first.",
"msg_undo_error": "Undo error:\n{e}"
```
In the `"editor"` object of `resources/i18n/ko.json` add the SAME keys with verbatim Korean values:
```
"common_apply": "적용", "common_cancel": "취소", "common_ok": "확인",
"common_reset": "초기화", "common_add": "추가", "common_error": "오류",
"common_warning": "경고", "common_notice": "알림", "common_done": "완료",
"common_width_label": "너비:", "common_height_label": "높이:",
"common_size_label": "크기:", "target_current_only": "현재 프레임만",
"target_selected": "선택한 프레임", "target_all": "모든 프레임",
"target_all_short": "모두", "target_selected_short": "선택",
"target_current_short": "현재", "apply_to": "적용 대상",
"msg_out_of_memory": "메모리가 부족하여 작업을 수행할 수 없습니다.",
"msg_gif_open_required": "GIF 파일을 먼저 열어주세요",
"msg_undo_error": "Undo 오류:\n{e}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ui_design_system_contracts.py -v`
Expected: PASS (all tests, including the new one).

- [ ] **Step 5: Commit**

```bash
git add resources/i18n/en.json resources/i18n/ko.json tests/unit/test_ui_design_system_contracts.py
git commit -m "i18n: 에디터 공통 번역 키 + 키 존재 계약 테스트 추가"
```

---

### Task A2: `editor/ui/dialogs/effects_dialog_wx.py`

**Files:** Modify `editor/ui/dialogs/effects_dialog_wx.py`, `resources/i18n/{en,ko}.json`. Idiom: no existing translations handle → add `from ui.i18n import tr`.

Key table (add new keys; `common_*`/`target_*` already added in A1 — reuse, do NOT re-add):

| key | EN | KO (verbatim) | site |
|---|---|---|---|
| effects_dialog_title | Effects / Filters | 효과/필터 | :102 title |
| effects_brightness | Brightness | 밝기 | :147 |
| effects_contrast | Contrast | 대비 | :151 |
| effects_saturation | Saturation | 채도 | :155 |
| effects_sharpness | Sharpness | 선명도 | :159 |
| effects_gamma | Gamma | 감마 | :163 |
| effects_tab_adjust | Adjust | 조정 | :169 tab |
| effects_filter_original | Original | 원본 | :180 |
| effects_filter_grayscale | Grayscale | 흑백 | :181 |
| effects_filter_sepia | Sepia | 세피아 | :182 |
| effects_filter_invert | Invert | 반전 | :183 |
| effects_filter_blur | Blur | 블러 | :184 |
| effects_filter_sharpen | Sharpen | 샤픈 | :185 |
| effects_filter_emboss | Emboss | 엠보스 | :186 |
| effects_filter_outline | Outline | 윤곽선 | :187 |
| effects_filter_posterize | Posterize | 포스터 | :188 |
| effects_filter_solarize | Solarize | 솔라라이즈 | :189 |
| effects_filter_edge | Edge Boost | 엣지 강조 | :190 |
| effects_filter_vignette | Vignette | 비네트 | :191 |
| effects_tab_filter | Filters | 필터 | :206 tab |

(`적용 대상` :212 → `apply_to`; choices :217 (full-form "현재 프레임만/선택한 프레임/모든 프레임") → `target_current_only/target_selected_full/target_all_full` — see TARGET-KEY TAXONOMY note; `초기화` :229 → `common_reset`; `적용` :237 → `common_apply`; `취소` :243 → `common_cancel`.)

- [ ] **Step 1: Add `from ui.i18n import tr`** to the import block.
- [ ] **Step 2: Add the new keys above to both JSON `"editor"` sections** (EN from table, KO verbatim).
- [ ] **Step 3: Replace every Korean literal** at the listed sites with `tr("<key>")` (use the worked archetypes S5; filter buttons are built in a list — map each to its `effects_filter_*` key in order).
- [ ] **Step 4: Verify no Korean remains** — Run: `.venv/Scripts/python.exe -c "import re,pathlib; t=pathlib.Path('editor/ui/dialogs/effects_dialog_wx.py').read_text(encoding='utf-8'); import sys; m=[l for i,l in enumerate(t.splitlines(),1) if re.search(r'[가-힣]', l) and 'tr(' not in l and not l.strip().startswith('#')]; print('\n'.join(m) or 'CLEAN')"`
  Expected: `CLEAN` (only comments/docstrings may contain Korean; those are allowed).
- [ ] **Step 5: Ritual S6** (json ok → ruff → contracts pytest → commit `i18n: effects_dialog 한글 리터럴 tr() 라우팅`).

---

### Task A3: `editor/ui/dialogs/pencil_dialog_wx.py`

**Files:** Modify the dialog + JSON. Idiom: add `from ui.i18n import tr`.

| key | EN | KO (verbatim) | site |
|---|---|---|---|
| pencil_dialog_title | Pencil Settings | 펜슬 설정 | :18 |
| pencil_preview | Preview | 미리보기 | :35 |
| pencil_pen_color | Pen color | 펜 색상 | :49 |
| pencil_pick_color | Pick Color | 색상 선택 | :58 |
| pencil_pen_width | Pen width | 펜 두께 | :70 |
| pencil_duration | Display duration | 표시 지속 시간 | :95 |
| pencil_seconds_unit |  s |  초 | :111 (keep leading space) |
| pencil_duration_hint | The line you draw stays visible for the\nset duration starting from the selected frame. | 선택한 프레임부터 지정된 시간 동안\n그린 선이 표시됩니다. | :118 |
| pencil_start_drawing | Start Drawing | 그리기 시작 | :169 |

(`적용 대상` :131 → `apply_to`; `대상:` :136 → new `pencil_target_label`=Target:/대상:; choices :141 (short-form "모두/선택/현재") → pre-existing `target_all/target_selected/target_current` (matches frame_targeting.py — see TARGET-KEY TAXONOMY note); `취소` :163 → `common_cancel`.)

- [ ] **Step 1:** add import. **Step 2:** add keys (incl. `pencil_target_label`). **Step 3:** replace literals. **Step 4:** Korean-scan (as A2 Step 4, swap path). **Step 5:** ritual S6, commit `i18n: pencil_dialog 한글 리터럴 tr() 라우팅`.

---

### Task A4: `editor/ui/dialogs/resize_dialog_wx.py`

| key | EN | KO (verbatim) | site |
|---|---|---|---|
| resize_dialog_title | Resize | 크기 조절 | :27 |
| resize_new_size | New size | 새 크기 | :52 |
| resize_keep_ratio | Keep aspect ratio | 가로세로 비율 유지 | :96 |
| resize_resample | Resampling method | 리샘플링 방법 | :105 |
| resize_resample_nearest | Nearest (fast) | Nearest (빠름) | :20 |
| resize_resample_bicubic | Bicubic (recommended) | Bicubic (권장) | :22 |
| resize_resample_lanczos | Lanczos (high quality) | Lanczos (고품질) | :23 |
| resize_size_presets | Size presets | 크기 프리셋 | :123 |
| resize_cur_size | Current size: {w} x {h} px | 현재 크기: {w} x {h} px | :177 (f-string → Archetype 3, kwargs `w`,`h`) |

(`너비:` :59 → `common_width_label`; `높이:` :78 → `common_height_label`; `적용` :146 → `common_apply`; `취소` :152 → `common_cancel`. The resample dict keys at :20–23 are dict KEYS used for lookup — replace by introducing a stable id→label map: keep internal ids `"nearest"/"bicubic"/"lanczos"`, render labels via `tr(...)`, and look up by id, not by translated label.)

- [ ] Steps 1–5 as A3 pattern. Commit `i18n: resize_dialog 한글 리터럴 tr() 라우팅`.

---

### Task A5: `editor/ui/dialogs/speed_dialog_wx.py`

| key | EN | KO (verbatim) | site |
|---|---|---|---|
| speed_dialog_title | Speed | 속도 조절 | :19 |
| speed_multiplier | Speed multiplier | 속도 배율 | :40 |
| speed_hint | 1.0x = original speed, 2.0x = 2x faster, 0.5x = 2x slower | 1.0x = 원래 속도, 2.0x = 2배 빠르게, 0.5x = 2배 느리게 | :71 |
| speed_cur_duration | Current duration: {sec:.2f}s ({n} frames) | 현재 재생 시간: {sec:.2f}초 ({n}프레임) | :140 (f-string, kwargs `sec`,`n`) |
| speed_new_duration | Duration after change: {sec:.2f}s | 변경 후 재생 시간: {sec:.2f}초 | :175 (f-string, kwarg `sec`) |

(`적용` :113 → `common_apply`; `취소` :119 → `common_cancel`.)

- [ ] Steps 1–5. Commit `i18n: speed_dialog 한글 리터럴 tr() 라우팅`.

---

### Task A6: `editor/ui/dialogs/sticker_dialog_wx.py`

| key | EN | KO (verbatim) | site |
|---|---|---|---|
| sticker_dialog_title | Add Sticker/Shape | 스티커/도형 추가 | :45 |
| sticker_choose_shape | Choose shape | 도형 선택 | :82 |
| sticker_shape_rect | Rectangle | 사각형 | :90 |
| sticker_shape_circle | Circle | 원 | :91 |
| sticker_shape_triangle | Triangle | 삼각형 | :92 |
| sticker_shape_star | Star | 별 | :93 |
| sticker_shape_arrow | Arrow | 화살표 | :94 |
| sticker_shape_heart | Heart | 하트 | :95 |
| sticker_size_pos | Size & Position | 크기 및 위치 | :112 |
| sticker_color | Color | 색상 | :173 |
| sticker_fill | Fill | 채우기 | :180 |
| sticker_stroke | Stroke | 테두리 | :195 |
| sticker_opacity | Opacity: | 투명도: | :216 |

(`너비:` :145 → `common_width_label`; `높이:` :157 → `common_height_label`; `적용 대상` :237 → `apply_to`; choices :242 (full-form) → `target_current_only/target_selected_full/target_all_full` — see TARGET-KEY TAXONOMY note; `적용` :255 → `common_apply`; `취소` :261 → `common_cancel`. Shape buttons built as a list → map in order to `sticker_shape_*`; if downstream compares label text, switch to a stable shape id stored on the button.)

- [ ] Steps 1–5. Commit `i18n: sticker_dialog 한글 리터럴 tr() 라우팅`.

---

### Task A7: `editor/ui/dialogs/text_dialog_wx.py`

| key | EN | KO (verbatim) | site |
|---|---|---|---|
| text_dialog_title | Add Text | 텍스트 추가 | :17 |
| text_box | Text | 텍스트 | :30 |
| text_placeholder | Enter text | 텍스트를 입력하세요 | :38 |
| text_font | Font | 폰트 | :45 |
| text_size_label | Size: | 크기: | :52 (or reuse `common_size_label`) |
| text_bold | Bold | 굵게 | :65 |
| text_italic | Italic | 기울임 | :69 |
| text_color | Color | 색상 | :79 |
| text_color_label | Text: | 텍스트: | :86 |
| text_bg_label | Background: | 배경: | :97 |
| text_transparent | Transparent | 투명 | :104 |

(`크기:` :52 → reuse `common_size_label`; `추가` :119 → `common_add`; `취소` :125 → `common_cancel`.)

- [ ] Steps 1–5. Commit `i18n: text_dialog 한글 리터럴 tr() 라우팅`.

---

### Task A8: `editor/ui/dialogs/crop_dialog_wx.py`

| key | EN | KO (verbatim) | site |
|---|---|---|---|
| crop_dialog_title | Crop Image | 이미지 자르기 | :18 |
| crop_area | Crop area | 크롭 영역 | :37 |
| crop_size_presets | Size presets | 크기 프리셋 | :90 |
| crop_preset_full | Full | 전체 | :96 |
| crop_preset_center_half | Center 1/2 | 중앙 1/2 | :96 |
| crop_preset_center_3q | Center 3/4 | 중앙 3/4 | :96 |
| crop_info_size | Image size: {w} x {h} px | 이미지 크기: {w} x {h} px | :138 (f-string, kwargs `w`,`h`) |

(`너비:` :66 → `common_width_label`; `높이:` :76 → `common_height_label`; `적용` :112 → `common_apply`; `취소` :118 → `common_cancel`.)

- [ ] **Step 3 special:** `_apply_preset` at :153/:158/:165 compares against `"전체"/"중앙 1/2"/"중앙 3/4"`. Replace label-string comparison with stable ids: when creating each preset button set `btn.preset_id = "full"|"half"|"3q"`, bind to a handler that reads `evt.GetEventObject().preset_id`, and switch on the id — NOT on the translated label.
- [ ] Steps 1,2,4,5 as standard. Commit `i18n: crop_dialog 한글 리터럴 tr() 라우팅 + 프리셋 id 분리`.

---

### Task A9: `editor/ui/dialogs/target_frame_hint_dialog_wx.py`

This file already has `_tr()` + optional `translations`. Per S3 special handling.

| key | EN | KO (verbatim) |
|---|---|---|
| target_frame_hint_title | Select Target Frames | 대상 프레임 선택 |
| target_frame_hint_message | Frame selection guide:\n\n• Current frame: applies only to the frame you are viewing\n• Selected frames: applies to the frames selected in the frame list\n• All frames: applies to every frame\n\nUse Shift+Click or Ctrl+Click in the frame list\nto select multiple frames. | 프레임 선택 안내:\n\n• 현재 프레임: 현재 보고 있는 프레임에만 적용\n• 선택한 프레임: 프레임 목록에서 선택한 프레임들에 적용\n• 모든 프레임: 전체 프레임에 적용\n\n프레임 목록에서 Shift+클릭 또는 Ctrl+클릭으로\n여러 프레임을 선택할 수 있습니다. |
| dont_show_again | Don't show this again | 다음부터 이 안내를 표시하지 않음 |

(`ok` → reuse `common_ok`.)

- [ ] **Step 1:** add `from ui.i18n import tr`.
- [ ] **Step 2:** add the 3 keys above to both JSON; ensure `ok` maps to existing `common_ok` (update `_tr` callers to use `common_ok`).
- [ ] **Step 3:** change constructor `title="대상 프레임 선택"` → `title=self._tr("target_frame_hint_title")` (call AFTER `self._translations` is assigned — reorder so `_translations` is set before `super().__init__` title needs it; if wx requires title at `super().__init__`, pass `tr("target_frame_hint_title")` from module `tr` instead). Change `_tr` body: `return tr(key, defaults.get(key, key))` so it resolves via singleton, with the Korean dict as last-resort default.
- [ ] **Step 4:** Korean-scan. **Step 5:** ritual, commit `i18n: target_frame_hint_dialog tr() 일원화`.

---

### Task A10: `editor/ui/dialogs/help_dialog_wx.py` (help prose — full)

**This is the largest single file.** It has module constants `APP_SUMMARY`/`EDITOR_SUMMARY`, section headings + body prose, shortcut tables, product-info, and `AboutDialog`. Idiom: add `from ui.i18n import tr`.

- [ ] **Step 1: Read the whole file** `editor/ui/dialogs/help_dialog_wx.py` and enumerate every Korean literal (module constants, `_add_section` headings/bodies, shortcut rows, `AboutDialog`). The agent inventory in `docs/UI-REVIEW-2026-05-15.md` audit + the gsd-ui-review run identified these anchors: :13-16, :18-21, :29, :79-82, :87, :106-122, :128-153, :158-188, :193-213, :268, :296, :311.
- [ ] **Step 2: Define keys** under `help_*` prefix, one per discrete string/paragraph: `help_app_summary`, `help_editor_summary`, `help_dialog_title`, `help_tab_summary`, `help_tab_features`, `help_tab_shortcuts`, `help_tab_about`, `help_sec_app_summary_title`, `help_sec_app_summary_body`, `help_sec_flow_title`, `help_sec_flow_body`, `help_sec_frames_title`, `help_sec_frames_body`, `help_sec_image_title`, `help_sec_image_body`, `help_sec_overlay_title`, `help_sec_overlay_body`, `help_sec_files_title`, `help_sc_files_body`, `help_sec_edit_title`, `help_sc_edit_body`, `help_sec_tools_title`, `help_sc_tools_body`, `help_sec_product_title`, `help_product_body`, `help_sec_design_title`, `help_design_body`, `help_about_title`. (`확인` → `common_ok`.) For multi-line prose keep `\n` exactly; keep version `f"앱 버전: {APP_VERSION}"` style → `tr("help_app_version", v=APP_VERSION)` EN `"App version: {v}"` / KO `"앱 버전: {v}"` (same for editor version / last-modified / developer rows at :296).
- [ ] **Step 3:** Author EN for each `help_*` key as faithful product-doc English of the verbatim Korean read in Step 1 (sentence case, preserve line breaks, keep the literal shortcut tokens like `Ctrl+O`, `Space` unchanged inside the value — only translate the description after the token). Add KO = verbatim, EN = authored, to both JSON.
- [ ] **Step 4:** Replace all literals (module constants become `tr(...)` calls evaluated at dialog-construction time — move them from module scope into the method that builds the page, or wrap as functions, since `tr()` must run after the singleton language is set; do NOT call `tr()` at module import time).
- [ ] **Step 5:** Korean-scan; ritual S6; commit `i18n: help_dialog 한글 프로즈 전체 tr() 라우팅`.

> Note: `help_dialog` is prose-heavy; allocate the most review time here. The static guard (Task A14) allowlist will NOT include this file — it must be fully clean.

---

### Task A11: `editor/ui/editor_main_window_wx.py` — messageboxes + menus + tooltips

Idiom: file already holds `self._translations` (an `EditorTranslations`). Use `self._translations.tr("key")`. Where a `self._translations` is not yet available at call time (early init), use module `from ui.i18n import tr` (add the import).

This file has ~80 strings. Group into sub-commits to keep diffs reviewable.

- [ ] **Step 1: Menu labels & menubar (lines 585–667, plus :498 tooltip, :421 label).**
  Keys `menu_*` (carry `(&X)`/`\t<accel>` inside both ko & en values per S5 Archetype 5): `menu_new`,`menu_open`,`menu_open_image_seq`,`menu_recent`,`menu_clear_recent`,`menu_exit`,`menu_select_all`,`menu_delete_frame`,`menu_duplicate_frame`,`menu_remove_dup`,`menu_mosaic`,`menu_speech`,`menu_watermark`,`menu_split_save`,`menu_merge_end`,`menu_insert_here`,`menu_actual_size`,`menu_fit_screen`,`menu_gpu_accel`,`menu_gpu_info`,`menu_help`,`menu_about` (`f"XGif 정보  v{__version__}"` → `tr("menu_about", v=__version__)` EN `"About XGif  v{v}"` KO `"XGif 정보  v{v}"`), menubar tuples `menubar_file/edit/manage/view/settings/help` (EN `"File(&F)"`… KO `"파일(&F)"`…), `tip_play_pause` (:498, EN `"Play/Pause (Space)"` KO `"재생/일시정지 (Space)"`), `info_memory_label` (:421, EN `"Memory:"` KO `"메모리:"`), `recent_none` (:1977, EN `"(none)"` KO `"(없음)"`), `menu_gpu_accel_nogpu` (:2074, EN `"GPU Acceleration (no GPU)"` KO `"GPU 가속 사용 (GPU 없음)"`).
  Add keys to JSON, replace literals. Commit `i18n: editor_main_window 메뉴/메뉴바 tr() 라우팅`.
- [ ] **Step 2: All `wx.MessageBox`/`wx.MessageDialog` (the ~50 sites listed in `docs/UI-REVIEW-2026-05-15.md` detailed findings + the gsd-ui-review inventory: lines 772, 838-914, 1155-1736, 1754-2032).**
  Reuse `common_error/common_warning/common_notice/common_done/msg_out_of_memory/msg_gif_open_required/msg_undo_error/common_ok`. New keys for the rest under `msg_*` (f-strings → kwargs): e.g. `msg_open_failed`=`File could not be opened:\n{e}`/`파일을 열 수 없습니다:\n{e}`; `msg_save_failed`/`저장 실패:\n{e}`; `msg_saved`=`Saved.\nFile size: {kb:.1f} KB`/`저장되었습니다.\n파일 크기: {kb:.1f} KB`; `msg_confirm_save`=`Save changes?`/`변경사항을 저장하시겠습니까?` (title `Confirm`/`확인` → new `common_confirm`); `msg_invalid_frame_index`/`유효하지 않은 프레임 인덱스입니다.`; `msg_frame_duplicated_no_undo`=`Frame duplicated.\n(Undo unavailable due to memory: {mb:.1f}MB)`/verbatim; `msg_dup_removed_no_undo`/`msg_dup_removed`/`msg_dup_remove_error`; `msg_video_decoder_unavailable`; `msg_video_info_unavailable`; `msg_image_seq_*`; `msg_video_*`; `msg_flip_error`/`msg_reverse_error`/`msg_reduce_error`/`msg_speed_error`/`msg_delay_error`/`msg_yoyo_error`; `msg_min_one_frame`; `msg_split_select_frames`; `msg_no_frames_to_save`; `msg_recent_cleared`; `msg_confirm_clear_recent`; `msg_memory_warning_body`/`msg_memory_expanded`; `msg_low_end_enabled`. Dialog/Progress titles → `title_saving`,`title_split_save`,`title_merge`,`title_insert`,`title_video_convert`,`title_convert_done`,`title_memory_warning`,`prog_*` message strings; `wx.DirDialog`/`wx.FileDialog`/`NumberEntryDialog` titles & prompts → `dlg_*` keys (e.g. `dlg_choose_image_seq_folder`,`dlg_frame_delay_prompt`,`dlg_delay_ms`,`dlg_set_frame_delay`,`dlg_split_save`,`dlg_choose_merge_gif`,`dlg_choose_insert_gif`,`dlg_fps_prompt`,`dlg_fps`,`dlg_video_to_gif`). For EN, follow the glossary + concise product English; KO = verbatim. Add all to both JSON. Replace literals. Commit `i18n: editor_main_window 메시지박스/다이얼로그 tr() 라우팅`.
- [ ] **Step 3: Korean-scan** the whole file (A2 Step 4 with this path). Any remaining Hangul outside comments/docstrings → route it. **Step 4:** ritual S6 (json/ruff/contracts). Final commit for this file `i18n: editor_main_window 잔여 한글 정리`.

---

### Task A12: `editor/ui/frame_list_widget_wx.py`

Idiom: file uses `translations.tr(...) if translations else "..."` pattern in places (e.g. :46). Use the same `translations` handle; for the messageboxes at :529/:540/:552/:554 reuse `common_error`/`msg_out_of_memory` and add `msg_frame_delete_failed`=`Failed to delete frame:\n{e}`/`프레임 삭제 실패:\n{e}`, `msg_undo_failed`=`Undo failed:\n{e}`/`실행 취소 실패:\n{e}`, `msg_frame_delete_error`=`An error occurred while deleting frames:\n{e}`/`프레임 삭제 중 오류가 발생했습니다:\n{e}` (title for :552 is `메모리 부족` → new `common_out_of_memory`=`Out of Memory`/`메모리 부족`).

- [ ] Steps 1–5 standard. Commit `i18n: frame_list_widget tr() 라우팅`.

---

### Task A13: inline toolbars + canvas empty state

**Files:** `editor/ui/inline_toolbars/pencil_toolbar_wx.py`, `resize_toolbar_wx.py`, `watermark_toolbar_wx.py`, `editor/ui/canvas_widget_wx.py`.

- [ ] **pencil_toolbar_wx.py:** `:115` `"캔버스가 초기화되지 않았습니다."` → new `msg_pencil_canvas_not_init`=`The canvas is not initialized.`/verbatim; `:120` `"그려진 선이 없습니다."` → existing `msg_pencil_no_lines` if present (verify in JSON; the agent noted it EXISTS) else add; `:125` `"적용할 프레임이 없습니다."` → existing `msg_pencil_no_frames` if present else add; `:140` → `msg_pencil_apply_error`=`An error occurred while applying the pencil strokes:\n{e}`/verbatim; titles → `common_warning`/`common_error`. Use the toolbar's `translations` handle (it already uses `translations.tr` elsewhere).
- [ ] **resize_toolbar_wx.py:** `:60` `"비율 유지"` → `resize_keep_ratio_short`=`Keep ratio`/`비율 유지` (route the raw `wx.CheckBox` literal through `tr()`).
- [ ] **watermark_toolbar_wx.py:** `:170` `"워터마크 이미지 선택"` → `dlg_choose_watermark_image`; `:171` wildcard → `dlg_image_wildcard`=`Image files (*.png;*.jpg;*.jpeg;*.bmp;*.gif)|*.png;*.jpg;*.jpeg;*.bmp;*.gif` / KO verbatim (the `|...` machine part stays identical in both — only the human label before `|` translates); `:183` already uses `translations.tr("msg_error")` — add `msg_watermark_load_failed`=`Failed to load image: {e}`/`이미지 로드 실패: {e}` and use it.
- [ ] **canvas_widget_wx.py:** `:340-341` English literals `"No frame loaded"` / `"Open a GIF to preview edits here"` → `canvas_no_frame_title`=`No frame loaded`/`불러온 프레임이 없습니다`, `canvas_no_frame_detail`=`Open a GIF to preview edits here`/`GIF를 열면 여기에서 편집을 미리볼 수 있습니다`. canvas has no translations handle → add `from ui.i18n import tr`; wrap the two `dc.DrawText` strings in `tr(...)`.
- [ ] Add all keys to both JSON. Korean-scan each file. Ritual S6. Commit `i18n: 인라인 툴바 + 캔버스 빈상태 tr() 라우팅`.

---

### Task A14: Korean-literal static guard (regression lock)

**Files:** Test `tests/unit/test_ui_design_system_contracts.py`.

- [ ] **Step 1: Write the guard test**

```python
import re

# Files whose Korean inside string literals is intentional/allowed:
_KO_LITERAL_ALLOWLIST = {
    # i18n data & tests are not UI implementation:
    # (resources/i18n/*.json and tests/** are not scanned — scan targets editor/ui only)
}
_HANGUL = re.compile(r"[가-힣]")

def _string_literal_lines_with_hangul(path: str):
    """Lines containing Hangul inside a quoted string (not comments/docstrings)."""
    src = _read(path)
    offenders = []
    for i, line in enumerate(src.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if not _HANGUL.search(line):
            continue
        # crude: Hangul present AND a quote present AND not obviously a comment-only line
        if ('"' in line or "'" in line) and "tr(" not in line:
            offenders.append(f"{path}:{i}: {stripped[:120]}")
    return offenders

def test_no_hardcoded_korean_in_editor_ui_implementation():
    import glob
    targets = []
    for pat in ("editor/ui/**/*.py",):
        targets += glob.glob(pat, recursive=True)
    offenders = []
    for path in sorted(targets):
        norm = path.replace("\\", "/")
        if norm in _KO_LITERAL_ALLOWLIST:
            continue
        offenders += _string_literal_lines_with_hangul(norm)
    assert not offenders, "Hardcoded Korean string literals remain:\n" + "\n".join(offenders)
```

- [ ] **Step 2: Run it**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ui_design_system_contracts.py::test_no_hardcoded_korean_in_editor_ui_implementation -v`
Expected after A2–A13: PASS. If it FAILS, the failure list names exact `file:line` — route each remaining literal through `tr()` (it is a real miss), or, only for genuinely non-UI Korean (e.g. a Korean substring inside a regex or a developer-facing log string), add that precise file to `_KO_LITERAL_ALLOWLIST` with a one-line comment justifying it. Docstrings/comments are already excluded; do not allowlist whole files to silence real UI misses.

- [ ] **Step 3: Re-run full contract suite**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ui_design_system_contracts.py -v`
Expected: PASS (all functions).

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_ui_design_system_contracts.py
git commit -m "test: 에디터 UI 한글 리터럴 정적 가드 추가 (i18n 회귀 잠금)"
```

---

# Part B — Fix #2: Unpin the editor window from 1008×840

**Files:**
- Modify: `editor/ui/editor_main_window_wx.py:329-334`
- Test: `tests/unit/test_ui_design_system_contracts.py` (new test)

**Background (verified):** `class MainWindow(wx.Frame)` (`:155`), `super().__init__(None, title="XGif Editor", size=(1680, 1120))`. In `_setup_ui` (`:329-334`):
```python
self.SetMinSize((1008, 840))
self.SetSize((1008, 840))
```
The proven reusable clamp is `ThemedDialog.fit_to_content` (`ui/theme.py:424-444`): `display_idx = wx.Display.GetFromWindow(self); display = wx.Display(display_idx if display_idx >= 0 else 0); screen = display.GetClientArea(); new_w = min(new_w, screen.width - 40); new_h = min(new_h, screen.height - 40)`. `MainWindow` is a `wx.Frame`, not a `ThemedDialog`, so we replicate the clamp inline (a true interaction-floor min + screen-clamped initial size). Interaction floor chosen: `(880, 620)` — below this the toolbar/frame-list/canvas no longer usable; this is a justified minimum per the audit Stop Condition.

### Task B1: Failing min-size/clamp test

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_ui_design_system_contracts.py`:

```python
def test_editor_window_is_not_hard_pinned_to_1008x840():
    src = _read("editor/ui/editor_main_window_wx.py")
    # The exact hard-pin pair must be gone:
    assert "self.SetMinSize((1008, 840))" not in src
    assert "self.SetSize((1008, 840))" not in src
    # A real interaction-floor minimum must exist:
    assert "self.SetMinSize((880, 620))" in src
    # Initial size must be screen-clamped via the shared display pattern:
    assert "wx.Display.GetFromWindow(self)" in src
    assert ".GetClientArea()" in src
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ui_design_system_contracts.py::test_editor_window_is_not_hard_pinned_to_1008x840 -v`
Expected: FAIL (`self.SetMinSize((1008, 840))` still present).

### Task B2: Implement the clamp

- [ ] **Step 3: Replace lines 333–334**

In `editor/ui/editor_main_window_wx.py` `_setup_ui`, replace:
```python
        self.SetMinSize((1008, 840))
        self.SetSize((1008, 840))
```
with:
```python
        # 상호작용이 가능한 최소 크기(작업 영역 플로어). 이 아래로는
        # 툴바/프레임목록/캔버스가 사용 불가하므로 정당한 최소값.
        self.SetMinSize((880, 620))
        # 초기 크기는 선호 크기를 화면 작업영역에 클램프
        # (ui.theme.ThemedDialog.fit_to_content 와 동일 패턴).
        preferred_w, preferred_h = 1008, 840
        display_idx = wx.Display.GetFromWindow(self)
        display = wx.Display(display_idx if display_idx >= 0 else 0)
        screen = display.GetClientArea()
        init_w = min(preferred_w, screen.width - 40)
        init_h = min(preferred_h, screen.height - 40)
        self.SetSize((init_w, init_h))
```
(`wx` is already imported in this file. No new import.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ui_design_system_contracts.py::test_editor_window_is_not_hard_pinned_to_1008x840 -v`
Expected: PASS.

### Task B3: Regression + commit

- [ ] **Step 5: Full suite + lint**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v -k "design_system or screen_recorder_runtime"` then `.venv/Scripts/python.exe -m ruff check editor/ui/editor_main_window_wx.py --fix`
Expected: PASS, no ruff errors.

- [ ] **Step 6: Commit**

```bash
git add editor/ui/editor_main_window_wx.py tests/unit/test_ui_design_system_contracts.py
git commit -m "fix: 에디터 메인 윈도우 1008x840 고정 해제 — 화면 클램프 적용"
```

---

# Part C — Fix #3: FormSection/FormRow primitives + button-stack convergence

**Files:**
- Modify: `ui/design_system.py` (add `FormSection`, `FormRow`)
- Modify: `ui/settings_dialog.py` (refactor `_init_ui` groups to `FormSection`/`FormRow`)
- Modify: `editor/ui/icon_toolbar_wx.py` (make `FlatIconButton` delegate to shared icon drawing) — see Task C5 scope note
- Modify: `ui/capture_control_bar.py` (delete dead `FlatButton`)
- Test: `tests/unit/test_ui_design_system_contracts.py`

**Verified facts:** `ui/design_system.py` imports `from ui.theme import Colors, Fonts, Sizes, ThemedDialog`; `CommandButton(parent, label="", size=wx.DefaultSize, *, icon_type=None, ...)`; `class FormSection`/`FormRow` do NOT exist anywhere in `.py`. `FlatButton` (`ui/capture_control_bar.py:17`) has **zero instantiation sites** in main app (only `BootStrapper/ui_main.py` has its own independent copy) → dead code in XGif_v5. `FlatIconButton` (`editor/ui/icon_toolbar_wx.py:48`) is live (play button, frame_list icons, toolbar group buttons) and uses `IconFactory.create_bitmap`. `settings_dialog.py` is `class SettingsDialog(ThemedDialog)`, `_init_ui` builds 6+ `wx.StaticBox`+`wx.StaticBoxSizer` groups with repeated `label.SetMinSize((130, -1))`.

> **Scope decision for button convergence:** Fully merging `FlatIconButton` into `CommandButton` is high-risk (different sizing model, `IconFactory` bitmaps, no-cache paint, active-mode toggling used by `IconToolbar.set_edit_mode`). The audit's acceptance is "recorder and editor use the same icon primitives" — pragmatic, low-risk satisfaction: (a) **delete the dead `FlatButton`** (removes one of the three stacks outright), (b) add `FormSection`/`FormRow` and adopt them in `settings_dialog`, (c) record `FlatIconButton`↔`CommandButton` consolidation as a **follow-up** (a true merge needs its own plan; doing it blind here risks editor toolbar regressions). This closes the P1 acceptance items that are safely closable now and is explicitly noted as partial in the commit message + a `[NOTE]` appended to the audit doc's Escalations.

### Task C1: Add `FormSection` + `FormRow` primitives (TDD)

**Files:** Modify `ui/design_system.py`; Test `tests/unit/test_ui_design_system_contracts.py`.

- [ ] **Step 1: Write the failing test**

Append:
```python
def test_design_system_exposes_form_section_and_row():
    ds = _read("ui/design_system.py")
    assert "class FormSection" in ds
    assert "class FormRow" in ds
    # FormSection groups titled content without raw StaticBox chrome:
    assert "wx.StaticBox" not in ds.split("class FormSection")[1].split("class ")[1] \
        if "class FormSection" in ds else False
```
(If the split-based assertion is brittle in the executor's hands, simplify to: `assert "class FormSection" in ds and "class FormRow" in ds` plus the settings-dialog adoption test in C3 — the adoption test is the real contract.)

- [ ] **Step 2: Run it**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ui_design_system_contracts.py::test_design_system_exposes_form_section_and_row -v`
Expected: FAIL (`class FormSection` absent).

- [ ] **Step 3: Implement the primitives**

Append to `ui/design_system.py` (uses already-imported `Colors, Fonts, Sizes`):
```python
class FormRow(wx.Panel):
    """A label + control row with consistent label column width.

    Replaces the repeated `wx.StaticText.SetMinSize((130, -1))` + manual
    BoxSizer pattern. The label column width is a single shared constant.
    """

    LABEL_COL_WIDTH = 140

    def __init__(self, parent, label: str, control: wx.Window, *, label_for_check: bool = False):
        super().__init__(parent)
        self.SetBackgroundColour(parent.GetBackgroundColour())
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        if label:
            text = wx.StaticText(self, label=label)
            text.SetForegroundColour(Colors.TEXT_SECONDARY)
            text.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
            text.SetMinSize((self.LABEL_COL_WIDTH, -1))
            sizer.Add(text, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        control.Reparent(self)
        sizer.Add(control, 1, wx.ALIGN_CENTER_VERTICAL)
        self.SetSizer(sizer)


class FormSection(wx.Panel):
    """A titled content group: bold section title + optional description +
    vertically stacked rows. Replaces wx.StaticBox/StaticBoxSizer chrome with
    spacing+heading hierarchy (audit P1)."""

    def __init__(self, parent, title: str, description: str = ""):
        super().__init__(parent)
        self.SetBackgroundColour(parent.GetBackgroundColour())
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        heading = wx.StaticText(self, label=title)
        heading.SetForegroundColour(Colors.TEXT_PRIMARY)
        heading.SetFont(Fonts.get_font(Fonts.SIZE_LABEL, bold=True))
        self._sizer.Add(heading, 0, wx.BOTTOM, 6)
        if description:
            desc = wx.StaticText(self, label=description)
            desc.SetForegroundColour(Colors.TEXT_SECONDARY)
            desc.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
            self._sizer.Add(desc, 0, wx.BOTTOM, 8)
        self.SetSizer(self._sizer)

    def add(self, window: wx.Window, *, gap: int = 6):
        window.Reparent(self)
        self._sizer.Add(window, 0, wx.EXPAND | wx.BOTTOM, gap)
        return window

    def add_row(self, label: str, control: wx.Window):
        row = FormRow(self, label, control)
        return self.add(row)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ui_design_system_contracts.py::test_design_system_exposes_form_section_and_row -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/design_system.py tests/unit/test_ui_design_system_contracts.py
git commit -m "feat: design_system FormSection/FormRow 폼 섹션 프리미티브 추가"
```

### Task C2: Smoke test the primitives instantiate under a wx.App

- [ ] **Step 1: Write the test** (append):
```python
def test_form_section_instantiates_without_error():
    import wx
    from ui.design_system import FormSection, FormRow
    app = wx.App()
    frame = wx.Frame(None)
    sec = FormSection(frame, "Title", "desc")
    sec.add_row("Label:", wx.TextCtrl(frame))
    assert sec.GetSizer() is not None
    frame.Destroy()
    app.Destroy()
```
- [ ] **Step 2: Run** `...::test_form_section_instantiates_without_error -v` → Expected: PASS (if headless wx unavailable in CI, mark `@pytest.mark.skipif` on `wx.App` failure — but locally it must pass).
- [ ] **Step 3: Commit** `git commit -am "test: FormSection 인스턴스화 스모크 테스트"`

### Task C3: Adopt FormSection/FormRow in `settings_dialog.py`

**Files:** Modify `ui/settings_dialog.py` (`_init_ui` lines ~54–215).

- [ ] **Step 1: Write the failing contract test** (append):
```python
def test_settings_dialog_uses_form_section_not_staticbox():
    src = _read("ui/settings_dialog.py")
    assert "from ui.design_system import" in src and "FormSection" in src
    assert "wx.StaticBox(" not in src
    assert "wx.StaticBoxSizer(" not in src
    assert "SetMinSize((130, -1))" not in src
```
- [ ] **Step 2: Run** → Expected: FAIL (`wx.StaticBox(` present).
- [ ] **Step 3: Refactor `_init_ui`.** Change the import line `from ui.design_system import CommandButton` → `from ui.design_system import CommandButton, FormSection, FormRow`. For EACH of the 6 groups (언어/미리보기/메모리/GPU/오디오/오버레이/인터랙션) replace the `wx.StaticBox`+`wx.StaticBoxSizer`+manual `SetMinSize((130,-1))` block with:
```python
lang_section = FormSection(self.scroll_panel, tr('language'))
lang_section.add_row(tr('language') + ":", self.lang_combo)   # combo created without StaticBox parent → parent=self.scroll_panel then Reparent handled by FormRow
scroll_sizer.Add(lang_section, 0, wx.EXPAND | wx.ALL, 10)
```
Apply the same shape to every group: section title = the old `wx.StaticBox` label `tr(...)`; each label+control becomes `section.add_row(label, control)`; checkboxes (no label column) become `section.add(checkbox)`. Keep all existing widget construction, event bindings, `retranslateUi` references, and `self.<widget>` attributes intact — only the grouping container changes. Update `retranslateUi` if it set `self.lang_box.SetLabel(...)`-style calls on the removed StaticBoxes: store the `FormSection` heading via keeping a reference (`self.lang_section = lang_section`) and translate by recreating text is out of scope (non-goal: editor live-retrans; settings already has `retranslateUi` for recorder — preserve existing behavior, and for section titles that were previously retranslated, set the FormSection heading text through a small `set_title()` helper added to `FormSection` if and only if `retranslateUi` referenced it; otherwise leave as-is).
- [ ] **Step 4: Run** the settings test + full contracts → Expected: PASS.
- [ ] **Step 5:** `.venv/Scripts/python.exe -m ruff check ui/settings_dialog.py --fix`; manual note: settings dialog is wx GUI → add a line to the commit body requesting manual smoke (`/test-automation` is ui-skip for editor but settings is recorder-side; manual visual check recommended).
- [ ] **Step 6: Commit** `git commit -am "refactor: settings_dialog StaticBox 폼시트 → FormSection/FormRow"`

### Task C4: Delete dead `FlatButton`

**Files:** Modify `ui/capture_control_bar.py`.

- [ ] **Step 1: Confirm dead** Run: `.venv/Scripts/python.exe -c "import subprocess"` then grep: `.venv/Scripts/python.exe -m pytest -q` is not it — use: search repo for `FlatButton(` instantiations excluding BootStrapper and the class def. Run:
  `git grep -n "FlatButton(" -- "ui/" "editor/" "main.py" ":!ui/capture_control_bar.py"` → Expected: **no output** (zero call sites). If any appear, STOP — do not delete; record `[BLOCK]` and convert call sites to `CommandButton` first.
- [ ] **Step 2: Write the failing test** (append):
```python
def test_dead_flatbutton_removed_from_capture_control_bar():
    src = _read("ui/capture_control_bar.py")
    assert "class FlatButton(" not in src
```
- [ ] **Step 3: Run** → FAIL (class still defined).
- [ ] **Step 4: Delete the `class FlatButton(wx.Control): ...` block** (`ui/capture_control_bar.py:17` through end of class, ~:213). Leave all other classes/imports intact. (Note: `BootStrapper/ui_main.py` has its OWN independent `FlatButton` — DO NOT touch BootStrapper, it is an isolated app per architecture-boundaries.md.)
- [ ] **Step 5: Run** test + `.venv/Scripts/python.exe -m pytest tests/ -v -k "dark_controls or design_system or capture"` + `ruff check ui/capture_control_bar.py --fix` → Expected: PASS, no errors.
- [ ] **Step 6: Commit** `git commit -am "refactor: 미사용 FlatButton 제거 (CommandButton로 일원화)"`

### Task C5: Record FlatIconButton convergence as a follow-up (no code change)

- [ ] **Step 1:** Append a `[NOTE]` to the `## Escalations` section of `docs/UI-REVIEW-2026-05-15.md`:
```
- [NOTE] FlatIconButton↔CommandButton 완전 통합은 별도 계획 필요: 사이징 모델/IconFactory
  비트맵/무캐시 페인트/IconToolbar.set_edit_mode active 토글 차이로 인해 blind 병합은
  에디터 툴바 회귀 위험. Top Fix #3의 안전 가능 항목(죽은 FlatButton 제거 +
  FormSection/FormRow 도입 + settings_dialog 채택)은 완료; FlatIconButton 통합은 후속.
```
- [ ] **Step 2: Commit** `git add docs/UI-REVIEW-2026-05-15.md && git commit -m "docs: UI 리뷰 후속 항목 기록 (FlatIconButton 통합 follow-up)"`

---

## Self-Review

**1. Spec coverage (vs `docs/UI-REVIEW-2026-05-15.md` Top 3):**
- Top Fix #1 (editor i18n + Korean static guard) → Part A, Tasks A1–A14. Covers all 9 dialog files, `editor_main_window_wx.py` (messageboxes+menus+tooltips), `frame_list_widget_wx.py`, inline toolbars, canvas empty state, help prose, + the static guard the audit's P6 specified. ✅
- Top Fix #2 (unpin 1008×840 via fit_to_content clamp + min-size test) → Part B, Tasks B1–B3. ✅
- Top Fix #3 (FormSection/FormRow + button convergence) → Part C, Tasks C1–C5. Dead `FlatButton` removed; `FormSection`/`FormRow` added & adopted in `settings_dialog`; full `FlatIconButton` merge explicitly deferred with rationale (risk-managed partial — matches audit's own "partial" framing of P1). ✅
- Audit "minor recommendations" (localize empty-canvas copy, editor ad-hoc `wx.Font`, fixed `300x300`/`560x480` previews, adopt StatusPill/InlineBanner in main_window, fixed-size static check, scaling QA checklist) — empty-canvas copy is covered (A13). The other minors are explicitly NOT in Top-3 and out of scope for this plan; noted here so they are not silently dropped.

**2. Placeholder scan:** No "TBD"/"implement later". Every Part A file task carries its exact key table (EN authored, KO verbatim) + the worked archetypes (S5) + the Korean-scan verification command. Part B/C steps contain literal code. The one judgement-bearing task (A10 help prose) gives an explicit "read file then apply pattern + glossary" procedure with the full key list — concrete, not a placeholder, because the transformation rule and key set are fully specified.

**3. Type/name consistency:** `tr` import path `from ui.i18n import tr` is consistent across all Part A tasks. `FormSection`/`FormRow` API (`.add()`, `.add_row()`, `FormRow.LABEL_COL_WIDTH`) defined in C1, consumed identically in C3. `common_*`/`target_*` keys defined once in A1, referenced (not re-added) in A2–A13. Test file `tests/unit/test_ui_design_system_contracts.py` extended additively; existing 3 functions untouched (S6 ritual re-runs the full file each task to catch regressions).

**Fixed during review:** Clarified that A1 owns the shared keys and later tasks must not re-add them (prevents duplicate-key JSON corruption). Clarified C3 must not break existing `retranslateUi` (scope-guarded). Added the C4 `git grep` dead-code gate with a `[BLOCK]` stop condition (prevents deleting `FlatButton` if a hidden call site exists).

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-15-ui-review-top3-fixes.md`.**

Recommended sequencing: **Part B (3 tasks) → Part C (5 tasks) → Part A (14 tasks)** — smallest/safest first, the large i18n sweep last. The user requested all three; this order de-risks and yields early green commits.

Post-implementation (per `.claude/rules/workflow-orchestrator.md`, L-grade): this plan is STEP 2 (Implement). After it, STEP 3 `/test-automation` (editor `ui-only-skip` → manual smoke notice for `editor/ui/`; `core` untouched) and STEP 4 `/code-reviewer` (full 5-agent) are the harness's responsibility — surface that to the user at completion, do not self-run.

Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration. Best for the 22-task volume here; each task is self-contained with its own test/commit.

**2. Inline Execution** — execute tasks in this session via superpowers:executing-plans, batch with checkpoints.

**Which approach?**
