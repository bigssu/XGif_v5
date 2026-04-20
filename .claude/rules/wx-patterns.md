# wxPython 필수 패턴 — XGif

## 스레드 안전성
- 백그라운드 스레드에서 GUI 위젯에 접근하면 크래시 또는 무응답이 발생한다.
- **규칙**: 백그라운드 스레드/프로세스에서 GUI를 업데이트할 때는 반드시 `wx.CallAfter()`를 사용한다.

```python
# 올바른 예
threading.Thread(target=lambda: wx.CallAfter(self.label.SetLabel, "완료")).start()

# 금지 — 크래시 유발
threading.Thread(target=lambda: self.label.SetLabel("완료")).start()
```

## 콤보박스 이벤트 내 크기 변경
- `EVT_COMBOBOX` 핸들러 안에서 직접 `SetSize()`/`Layout()`을 호출하면 드롭다운 위치가 어긋난다.
- **규칙**: 콤보박스 이벤트 핸들러 내 윈도우 크기 변경은 `wx.CallAfter()`로 지연한다.

## DPI 설정
- `SetProcessDpiAwareness(1)` — SYSTEM_AWARE만 허용
- `SetProcessDpiAwareness(2)` — PER_MONITOR_AWARE: wxPython ComboBox 드롭다운 크래시 유발, **절대 금지**
- 이 호출은 반드시 `import wx` 이전에 실행되어야 한다 (main.py 최상단 참조)

## 메뉴 이벤트 바인딩
```python
# 올바른 예
menu.Bind(wx.EVT_MENU, self.on_open, item_open)

# 금지 — 이벤트가 다른 메뉴 항목에도 전파됨
self.Bind(wx.EVT_MENU, self.on_open, item_open)
```

## 타이머 정리
- `wx.Timer`는 윈도우가 파괴된 후에도 이벤트를 발생시킬 수 있다.
- **규칙**: `EVT_WINDOW_DESTROY` 핸들러에서 반드시 `timer.Stop()`을 호출한다.

```python
self.Bind(wx.EVT_WINDOW_DESTROY, self._on_destroy)

def _on_destroy(self, event):
    if self._timer.IsRunning():
        self._timer.Stop()
    event.Skip()
```

## core/ 모듈에서 wx 사용
- `core/`는 wx 의존성이 없는 순수 엔진 레이어다.
- wx가 필요한 경우가 생기면 반드시 `wx.App.Get()` 으로 앱 존재 여부를 확인 후 분기한다.

## cli/ 모듈 규칙
- `cli/` 내 어떤 파일에서도 `import wx`는 허용되지 않는다.
- CLI 모드에서 wx를 불러오면 headless 환경에서 크래시가 발생한다.
