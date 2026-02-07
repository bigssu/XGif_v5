"""
FrameListWidget - Honeycam 스타일 프레임 목록 (wxPython 버전)

PyQt6 QTableWidget를 wx.grid.Grid로 마이그레이션
"""
import wx
import wx.grid as grid
from typing import TYPE_CHECKING, List
from ..utils.wx_events import (
    FrameSelectedEvent, FrameDeletedEvent, FrameDelayChangedEvent,
    EVT_FRAME_SELECTED, EVT_FRAME_DELETED, EVT_FRAME_DELAY_CHANGED
)

if TYPE_CHECKING:
    from .main_window import MainWindow
    from ..utils.translations import Translations


class FrameListWidget(wx.Panel):
    """Honeycam 스타일 프레임 목록 위젯 (wxPython)"""

    def __init__(self, main_window: 'MainWindow', parent=None):
        if parent is None:
            parent = main_window
        super().__init__(parent)
        self._main_window = main_window
        self._updating = False  # 프로그래밍적 업데이트 중 플래그

        self._setup_ui()

    def _setup_ui(self):
        """UI 초기화"""
        # 메인 레이아웃
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 번역 시스템 가져오기
        translations = getattr(self._main_window, '_translations', None)

        # 프레임 그리드 생성
        self._grid = grid.Grid(self)
        self._grid.CreateGrid(0, 2)  # 0행, 2열로 시작

        # 헤더 설정
        header1 = translations.tr("frame_list_number") if translations else "번호"
        header2 = translations.tr("frame_list_time") if translations else "프레임 시간"
        self._grid.SetColLabelValue(0, header1)
        self._grid.SetColLabelValue(1, header2)

        # 그리드 설정
        self._grid.SetSelectionMode(grid.Grid.SelectRows)
        self._grid.EnableEditing(True)
        self._grid.SetRowLabelSize(0)  # 행 라벨 숨김

        # 다중 선택 활성화 (ExtendedSelection 모드)
        # wxPython에서는 기본적으로 다중 선택이 활성화되어 있지만 명시적으로 설정
        # Ctrl+클릭으로 여러 행 선택, Shift+클릭으로 범위 선택 가능
        self._grid.EnableDragGridSize(False)  # 그리드 크기 조정 비활성화

        # 컬럼 크기 설정
        self._grid.SetColSize(0, 42)  # 번호 컬럼
        self._grid.SetColSize(1, 150)  # 프레임 시간 컬럼 (자동 확장)
        self._grid.SetColFormatFloat(1, -1, 2)  # 시간 컬럼은 float 형식

        # 컬럼 0은 읽기 전용
        attr = grid.GridCellAttr()
        attr.SetReadOnly(True)
        attr.SetAlignment(wx.ALIGN_CENTER, wx.ALIGN_CENTER)
        self._grid.SetColAttr(0, attr)

        # 컬럼 1 (시간)은 중앙 정렬
        attr_time = grid.GridCellAttr()
        attr_time.SetAlignment(wx.ALIGN_CENTER, wx.ALIGN_CENTER)
        self._grid.SetColAttr(1, attr_time)

        # 그리드 스타일 설정
        self._grid.SetDefaultCellBackgroundColour(wx.Colour(45, 45, 45))
        self._grid.SetDefaultCellTextColour(wx.Colour(255, 255, 255))
        self._grid.SetLabelBackgroundColour(wx.Colour(64, 64, 64))
        self._grid.SetLabelTextColour(wx.Colour(255, 255, 255))
        self._grid.SetGridLineColour(wx.Colour(64, 64, 64))
        self._grid.SetSelectionBackground(wx.Colour(0, 120, 212))
        self._grid.SetSelectionForeground(wx.Colour(255, 255, 255))

        # 이벤트 바인딩
        # 선택 변경 감지를 위한 여러 이벤트
        self._grid.Bind(grid.EVT_GRID_RANGE_SELECT, self._on_range_select)
        self._grid.Bind(grid.EVT_GRID_SELECT_CELL, self._on_cell_selected)
        self._grid.Bind(grid.EVT_GRID_CELL_LEFT_CLICK, self._on_cell_left_click)
        self._grid.Bind(grid.EVT_GRID_CELL_CHANGED, self._on_cell_changed)
        self._grid.Bind(grid.EVT_GRID_CELL_LEFT_DCLICK, self._on_cell_double_clicked)
        self._grid.Bind(grid.EVT_GRID_CELL_RIGHT_CLICK, self._on_right_click)
        self._grid.Bind(wx.EVT_KEY_DOWN, self._on_key_down)

        # 선택 변경 감지용 타이머 (안전장치)
        self._selection_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_selection_timer, self._selection_timer)
        self._last_selection = set()

        # 윈도우 파괴 시 타이머 정리
        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_frame_list_destroy)

        main_sizer.Add(self._grid, 1, wx.EXPAND | wx.ALL, 0)

        # 하단 버튼 영역
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 삭제 버튼 (휴지통 아이콘)
        delete_tooltip = translations.tr("frame_list_delete_tooltip") if translations else "선택한 프레임 삭제 (Delete)"
        self._delete_btn = self._create_icon_button("🗑️", delete_tooltip)
        self._delete_btn.Bind(wx.EVT_BUTTON, self._on_delete_clicked)
        button_sizer.Add(self._delete_btn, 0, wx.ALL, 5)

        # 시간 설정 버튼 (시계 아이콘)
        time_tooltip = translations.tr("frame_list_time_tooltip") if translations else "선택한 프레임 시간 일괄 설정"
        self._time_btn = self._create_icon_button("⏱️", time_tooltip)
        self._time_btn.Bind(wx.EVT_BUTTON, self._on_time_clicked)
        button_sizer.Add(self._time_btn, 0, wx.ALL, 5)

        # 프레임 추가 버튼 (플러스 아이콘)
        add_tooltip = translations.tr("frame_list_add_tooltip") if translations else "프레임 복제"
        self._add_btn = self._create_icon_button("➕", add_tooltip)
        self._add_btn.Bind(wx.EVT_BUTTON, self._on_add_clicked)
        button_sizer.Add(self._add_btn, 0, wx.ALL, 5)

        button_sizer.AddStretchSpacer()
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)

        # 배경색 설정
        self.SetBackgroundColour(wx.Colour(45, 45, 45))

    def _on_frame_list_destroy(self, event):
        """윈도우 파괴 시 타이머 정리 (PyDeadObjectError 방지)"""
        if event.GetEventObject() is self:
            try:
                self._selection_timer.Stop()
            except Exception:
                pass
        event.Skip()

    def _create_icon_button(self, icon_text: str, tooltip: str) -> wx.Button:
        """아이콘 버튼 생성 (임시: 텍스트 기반)"""
        btn = wx.Button(self, label=icon_text, size=(32, 32))
        btn.SetToolTip(tooltip)
        btn.SetBackgroundColour(wx.Colour(64, 64, 64))
        btn.SetForegroundColour(wx.Colour(255, 255, 255))
        return btn

    def refresh(self):
        """프레임 목록 새로고침"""
        self._updating = True
        # 선택 타이머 중지
        if self._selection_timer.IsRunning():
            self._selection_timer.Stop()

        if not self._main_window:
            self._grid.ClearGrid()
            if self._grid.GetNumberRows() > 0:
                self._grid.DeleteRows(0, self._grid.GetNumberRows())
            self._updating = False
            return

        frames = self._main_window.frames
        if not frames:
            self._grid.ClearGrid()
            if self._grid.GetNumberRows() > 0:
                self._grid.DeleteRows(0, self._grid.GetNumberRows())
            self._updating = False
            return

        # 행 수 조정
        current_rows = self._grid.GetNumberRows()
        needed_rows = frames.frame_count

        print(f"프레임 리스트 refresh: current_rows={current_rows}, needed_rows={needed_rows}")

        if current_rows < needed_rows:
            self._grid.AppendRows(needed_rows - current_rows)
        elif current_rows > needed_rows:
            self._grid.DeleteRows(0, current_rows - needed_rows)

        # 프레임 데이터 채우기
        frame_count = 0
        for i, frame in enumerate(frames):
            frame_count += 1
            if frame is None:
                continue

            try:
                # 번호 컬럼
                self._grid.SetCellValue(i, 0, str(i + 1))
                self._grid.SetCellAlignment(i, 0, wx.ALIGN_CENTER, wx.ALIGN_CENTER)
                self._grid.SetReadOnly(i, 0, True)

                # 프레임 시간 컬럼 (초 단위로 표시)
                delay_ms = getattr(frame, 'delay_ms', 100)  # 기본값 100ms
                seconds = delay_ms / 1000.0
                self._grid.SetCellValue(i, 1, f"{seconds:.2f}s")
                self._grid.SetCellAlignment(i, 1, wx.ALIGN_CENTER, wx.ALIGN_CENTER)

                # ms 값을 cell data로 저장 (나중에 편집 시 사용)
                # wxPython에서는 SetCellValue의 세 번째 인자로 데이터를 저장할 수 없으므로
                # 별도의 딕셔너리에 저장
                if not hasattr(self, '_cell_data'):
                    self._cell_data = {}
                self._cell_data[(i, 1)] = delay_ms

            except Exception as e:
                print(f"프레임 리스트 업데이트 오류 (프레임 {i}): {e}")
                continue

        print(f"프레임 루프 완료: 처리된 프레임 수 = {frame_count}")

        # 선택된 프레임들을 그리드에 반영
        if not frames.is_empty:
            # 선택 해제
            self._grid.ClearSelection()

            # 선택된 프레임들 선택
            selected_indices = frames.selected_indices
            if selected_indices:
                first_selected = selected_indices[0]

                # 첫 번째 선택된 프레임을 현재 프레임으로 설정
                if 0 <= first_selected < frames.frame_count and frames.current_index != first_selected:
                    frames.current_index = first_selected

                # 모든 선택된 행을 선택 상태로 설정
                for idx in selected_indices:
                    if isinstance(idx, int) and 0 <= idx < frames.frame_count:
                        self._grid.SelectRow(idx, addToSelected=True)

                # 첫 번째 선택된 행으로 스크롤
                self._grid.MakeCellVisible(first_selected, 0)

                # _last_selection 업데이트
                self._last_selection = set(selected_indices)
            else:
                # 선택된 프레임이 없으면 현재 프레임만 선택
                if 0 <= frames.current_index < frames.frame_count:
                    self._grid.SelectRow(frames.current_index)
                    self._last_selection = {frames.current_index}

        self._updating = False

    def _on_range_select(self, event):
        """범위 선택 처리 (다중 선택 시)"""
        print(f"[이벤트] _on_range_select 호출됨 - Selecting: {event.Selecting()}, _updating: {self._updating}")

        if self._updating:
            event.Skip()
            return

        # 선택이 추가/변경되는 경우에만 처리
        if event.Selecting():
            # 타이머를 사용하여 선택 처리 지연 (Grid가 선택 상태를 업데이트할 시간을 줌)
            self._selection_timer.Start(50, wx.TIMER_ONE_SHOT)

        event.Skip()

    def _on_cell_selected(self, event):
        """단일 셀 선택 처리"""
        print(f"[이벤트] _on_cell_selected 호출됨 - Row: {event.GetRow()}, _updating: {self._updating}")

        if self._updating:
            event.Skip()
            return

        # 타이머를 사용하여 선택 처리 지연
        self._selection_timer.Start(50, wx.TIMER_ONE_SHOT)

        event.Skip()

    def _on_cell_left_click(self, event):
        """셀 클릭 처리 (모든 클릭을 감지)"""
        print(f"[이벤트] _on_cell_left_click 호출됨 - Row: {event.GetRow()}, _updating: {self._updating}")

        if not self._updating:
            # 타이머를 사용하여 선택 처리 지연
            self._selection_timer.Start(50, wx.TIMER_ONE_SHOT)

        event.Skip()

    def _on_selection_timer(self, event):
        """선택 변경 타이머 (지연 후 처리)"""
        print(f"[타이머] _on_selection_timer 호출됨")
        self._process_selection_change()

    def _process_selection_change(self):
        """선택 변경 실제 처리 (이벤트 핸들러에서 호출)"""
        if self._updating:
            print(f"[선택 처리] _updating=True이므로 스킵")
            return

        selected_rows = self._get_selected_rows()
        selected_set = set(selected_rows)

        # 중복 처리 방지 - 선택이 변경되지 않았으면 스킵
        if selected_set == self._last_selection:
            print(f"[선택 처리] 선택이 변경되지 않음 - 스킵")
            return

        self._last_selection = selected_set
        frames = self._main_window.frames

        print(f"[선택 처리] selected_rows={selected_rows}, frame_count={frames.frame_count}")

        if selected_rows:
            first_selected = selected_rows[0]

            # 선택된 프레임 업데이트
            print(f"[선택 처리] deselect_all() 호출")
            frames.deselect_all()

            for row in selected_rows:
                frames.select_frame(row, add_to_selection=True)
                print(f"[선택 처리] 프레임 {row} 선택됨")

            print(f"[선택 처리] 최종 selected_indices={frames.selected_indices}")
            print(f"[선택 처리] 최종 selected_indices 타입={type(frames.selected_indices)}")

            # 현재 프레임을 첫 번째 선택 항목으로 설정
            print(f"[선택 처리] current_index 변경 전: {frames.current_index}")
            frames.current_index = first_selected
            print(f"[선택 처리] current_index 변경 후: {frames.current_index}")

            # 이벤트 발생
            evt = FrameSelectedEvent([first_selected])
            wx.PostEvent(self, evt)

            # 프리뷰 창 즉시 업데이트 - Refresh() 후 즉시 Update() 호출하여 강제로 그리기
            if hasattr(self._main_window, '_canvas') and self._main_window._canvas:
                print(f"[선택 처리] 캔버스 업데이트 시작: 프레임 {first_selected}")
                self._main_window._canvas.Refresh()
                self._main_window._canvas.Update()  # 즉시 페인트 이벤트 처리
                print("[선택 처리] 캔버스 업데이트 완료")
        else:
            print(f"[선택 처리] selected_rows가 비어있음")

    def _on_cell_changed(self, event):
        """셀 변경 처리"""
        row = event.GetRow()
        col = event.GetCol()

        if self._updating or col != 1:
            event.Skip()
            return

        if not self._main_window:
            event.Skip()
            return

        # 변경된 값 가져오기
        value_str = self._grid.GetCellValue(row, col)

        # 초 단위를 ms로 변환
        try:
            # "0.05s" 형태에서 숫자 추출
            seconds = float(value_str.replace('s', '').strip())
            ms = int(seconds * 1000)
            ms = max(10, min(10000, ms))  # 10ms ~ 10000ms 범위 제한
        except ValueError:
            # 파싱 실패 시 기본값
            ms = 100
            seconds = 0.1

        # 표시 형식 업데이트
        self._updating = True
        self._grid.SetCellValue(row, col, f"{seconds:.2f}s")
        self._updating = False

        # ms 값 저장
        if not hasattr(self, '_cell_data'):
            self._cell_data = {}
        self._cell_data[(row, col)] = ms

        # 프레임 딜레이 업데이트
        frames = self._main_window.frames
        if not frames or frames.is_empty:
            event.Skip()
            return

        if row < 0 or row >= frames.frame_count:
            event.Skip()
            return

        try:
            frame = frames[row]
            if frame:
                frame.delay_ms = ms
                self._main_window._is_modified = True

                # 이벤트 발생
                evt = FrameDelayChangedEvent(row, ms)
                wx.PostEvent(self, evt)
        except (IndexError, AttributeError) as e:
            print(f"프레임 딜레이 업데이트 오류: {e}")

        event.Skip()

    def _on_cell_double_clicked(self, event):
        """셀 더블클릭 처리"""
        row = event.GetRow()
        col = event.GetCol()

        if col == 1:
            # 딜레이 컬럼 - 편집 모드로 진입
            self._grid.EnableCellEditControl()

        event.Skip()

    def _on_right_click(self, event):
        """우클릭 메뉴 표시"""
        translations = getattr(self._main_window, '_translations', None)

        menu = wx.Menu()

        # 삭제 메뉴
        delete_text = translations.tr("frame_list_delete_action") if translations else "선택한 프레임 삭제"
        delete_item = menu.Append(wx.ID_ANY, f"{delete_text}\tDelete")
        menu.Bind(wx.EVT_MENU, lambda e: self.delete_selected_frames(), delete_item)

        # 복제 메뉴
        duplicate_text = translations.tr("frame_list_duplicate_action") if translations else "프레임 복제"
        duplicate_item = menu.Append(wx.ID_ANY, f"{duplicate_text}\tCtrl+D")
        menu.Bind(wx.EVT_MENU, lambda e: self._duplicate_frame(), duplicate_item)

        menu.AppendSeparator()

        # 모두 선택 메뉴
        select_all_text = translations.tr("frame_list_select_all_action") if translations else "모두 선택"
        select_all_item = menu.Append(wx.ID_ANY, f"{select_all_text}\tCtrl+A")
        menu.Bind(wx.EVT_MENU, lambda e: self._grid.SelectAll(), select_all_item)

        menu.AppendSeparator()

        # 시간 설정 서브메뉴
        time_menu_text = translations.tr("frame_list_time_menu") if translations else "프레임 시간 설정"
        time_submenu = wx.Menu()

        for ms in [50, 100, 150, 200, 500, 1000]:
            item = time_submenu.Append(wx.ID_ANY, f"{ms}ms ({ms/1000:.2f}s)")
            time_submenu.Bind(wx.EVT_MENU, lambda e, t=ms: self._set_selected_delay(t), item)

        menu.AppendSubMenu(time_submenu, time_menu_text)

        # 메뉴 표시
        self.PopupMenu(menu)
        menu.Destroy()

        event.Skip()

    def _on_key_down(self, event):
        """키 이벤트 처리"""
        keycode = event.GetKeyCode()

        if keycode == wx.WXK_DELETE:
            self.delete_selected_frames()
        elif keycode == ord('A') and event.ControlDown():
            self._grid.SelectAll()
            # 전체 선택 후 선택 처리
            self._selection_timer.Start(50, wx.TIMER_ONE_SHOT)
        elif keycode == ord('D') and event.ControlDown():
            self._duplicate_frame()
        else:
            event.Skip()

    def _get_selected_rows(self) -> List[int]:
        """선택된 행 인덱스 목록 반환"""
        selected = set()

        # GetSelectedRows()가 항상 신뢰할 수 없으므로, 직접 확인
        rows = self._grid.GetSelectedRows()
        if rows:
            selected.update(rows)

        # 선택된 셀들로부터도 행 추출
        cells = self._grid.GetSelectedCells()
        for cell in cells:
            selected.add(cell[0])

        # 선택된 블록들로부터도 행 추출
        blocks = self._grid.GetSelectionBlockTopLeft()
        if blocks:
            bottom_rights = self._grid.GetSelectionBlockBottomRight()
            for (top_left, bottom_right) in zip(blocks, bottom_rights):
                for row in range(top_left[0], bottom_right[0] + 1):
                    selected.add(row)

        return sorted(selected)

    def delete_selected_frames(self):
        """선택한 프레임 삭제"""
        selected_rows = self._get_selected_rows()
        if not selected_rows:
            return

        frames = self._main_window.frames

        # 최소 1개 프레임은 남겨야 함
        if len(selected_rows) >= frames.frame_count:
            return

        try:
            # Undo 등록
            undo_mgr = self._main_window.undo_manager
            old_frames = frames.clone()
            selected_rows_copy = selected_rows.copy()
            memory_usage = old_frames.get_memory_usage()

            def execute():
                try:
                    for row in reversed(selected_rows_copy):
                        if 0 <= row < frames.frame_count:
                            frames.delete_frame(row)
                    self._main_window._refresh_all()
                except Exception as e:
                    wx.MessageBox(f"프레임 삭제 실패:\n{str(e)}", "오류", wx.OK | wx.ICON_ERROR)
                    raise

            def undo():
                try:
                    # 프레임 컬렉션 복원
                    frames._frames = old_frames._frames
                    frames._current_index = old_frames._current_index
                    frames._selected_indices = old_frames._selected_indices.copy()
                    self._main_window._refresh_all()
                except Exception as e:
                    wx.MessageBox(f"실행 취소 실패:\n{str(e)}", "오류", wx.OK | wx.ICON_ERROR)
                    raise

            # Undo 등록 및 실행
            undo_mgr.execute_lambda(f"프레임 삭제 ({len(selected_rows)}개)", execute, undo, memory_usage)
            self._main_window._is_modified = True

            # 이벤트 발생
            evt = FrameDeletedEvent(selected_rows)
            wx.PostEvent(self, evt)

        except MemoryError:
            wx.MessageBox("메모리가 부족하여 작업을 수행할 수 없습니다.", "메모리 부족", wx.OK | wx.ICON_WARNING)
        except Exception as e:
            wx.MessageBox(f"프레임 삭제 중 오류가 발생했습니다:\n{str(e)}", "오류", wx.OK | wx.ICON_ERROR)

    def _duplicate_frame(self):
        """현재 프레임 복제"""
        selected_rows = self._get_selected_rows()
        if not selected_rows:
            return

        frames = self._main_window.frames
        frames.duplicate_frame(selected_rows[0])

        self._main_window._is_modified = True
        self.refresh()
        if hasattr(self._main_window, '_update_info_bar'):
            self._main_window._update_info_bar()

    def _set_selected_delay(self, delay_ms: int):
        """선택한 프레임들의 딜레이 설정"""
        selected_rows = self._get_selected_rows()
        if not selected_rows:
            return

        frames = self._main_window.frames
        if not frames or frames.is_empty:
            return

        for row in selected_rows:
            if 0 <= row < frames.frame_count:
                try:
                    frame = frames[row]
                    if frame:
                        frame.delay_ms = delay_ms
                except (IndexError, AttributeError) as e:
                    print(f"프레임 딜레이 설정 오류 (프레임 {row}): {e}")

        self._main_window._is_modified = True
        self.refresh()
        if hasattr(self._main_window, '_update_info_bar'):
            self._main_window._update_info_bar()

    def _on_delete_clicked(self, event):
        """삭제 버튼 클릭"""
        self.delete_selected_frames()

    def _on_time_clicked(self, event):
        """시간 설정 버튼 클릭"""
        self._show_bulk_time_dialog()

    def _on_add_clicked(self, event):
        """추가 버튼 클릭"""
        self._duplicate_frame()

    def _show_bulk_time_dialog(self):
        """일괄 시간 설정 다이얼로그"""
        selected_rows = self._get_selected_rows()
        if not selected_rows:
            return

        # 현재 선택된 프레임의 딜레이를 기본값으로 (ms -> s 변환)
        frames = self._main_window.frames
        if not frames or frames.is_empty or not selected_rows:
            return

        first_row = selected_rows[0]
        if 0 <= first_row < frames.frame_count:
            try:
                frame = frames[first_row]
                current_delay_ms = frame.delay_ms if frame and hasattr(frame, 'delay_ms') else 100
            except (IndexError, AttributeError):
                current_delay_ms = 100
        else:
            current_delay_ms = 100
        current_delay_s = current_delay_ms / 1000.0

        # 번역 시스템 가져오기
        translations = getattr(self._main_window, '_translations', None)

        # 다이얼로그 생성
        dialog_title = translations.tr("frame_list_time_dialog_title") if translations else "프레임 시간 설정"
        dialog = wx.Dialog(self, title=dialog_title, size=(210, 110),
                          style=wx.DEFAULT_DIALOG_STYLE)

        # 스타일 설정
        dialog.SetBackgroundColour(wx.Colour(45, 45, 45))

        # 레이아웃
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.AddSpacer(12)

        # 라벨과 입력 필드
        input_sizer = wx.BoxSizer(wx.HORIZONTAL)
        input_sizer.AddSpacer(12)

        time_label_text = translations.tr("frame_list_time_label") if translations else "시간 (초):"
        label = wx.StaticText(dialog, label=time_label_text)
        label.SetForegroundColour(wx.Colour(200, 200, 200))
        input_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # 스핀 컨트롤
        spin = wx.SpinCtrlDouble(dialog, value=str(current_delay_s),
                                 min=0.01, max=10.0, initial=current_delay_s, inc=0.01)
        spin.SetDigits(2)
        spin.SetSize((70, -1))
        input_sizer.Add(spin, 0, wx.ALIGN_CENTER_VERTICAL)

        input_sizer.AddSpacer(12)
        main_sizer.Add(input_sizer, 0, wx.EXPAND)

        main_sizer.AddSpacer(12)

        # 버튼
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        apply_text = translations.tr("frame_list_apply") if translations else "적용"
        ok_btn = wx.Button(dialog, label=apply_text, size=(60, -1))
        ok_btn.SetBackgroundColour(wx.Colour(0, 120, 212))
        ok_btn.SetForegroundColour(wx.Colour(255, 255, 255))
        ok_btn.Bind(wx.EVT_BUTTON, lambda e: dialog.EndModal(wx.ID_OK))
        button_sizer.Add(ok_btn, 0, wx.RIGHT, 5)

        cancel_text = translations.tr("frame_list_cancel") if translations else "취소"
        cancel_btn = wx.Button(dialog, label=cancel_text, size=(60, -1))
        cancel_btn.SetBackgroundColour(wx.Colour(64, 64, 64))
        cancel_btn.SetForegroundColour(wx.Colour(255, 255, 255))
        cancel_btn.Bind(wx.EVT_BUTTON, lambda e: dialog.EndModal(wx.ID_CANCEL))
        button_sizer.Add(cancel_btn, 0, wx.RIGHT, 12)

        main_sizer.Add(button_sizer, 0, wx.EXPAND)
        main_sizer.AddSpacer(12)

        dialog.SetSizer(main_sizer)

        # 다이얼로그 실행
        if dialog.ShowModal() == wx.ID_OK:
            delay_ms = int(spin.GetValue() * 1000)
            self._set_selected_delay(delay_ms)

        dialog.Destroy()

    def select_frame(self, index: int):
        """특정 프레임 선택"""
        if 0 <= index < self._grid.GetNumberRows():
            # 이미 선택된 행이면 중복 업데이트 방지
            current_selected = self._get_selected_rows()
            if current_selected and current_selected[0] == index and len(current_selected) == 1:
                return

            self._updating = True
            self._grid.ClearSelection()
            self._grid.SelectRow(index)
            self._grid.MakeCellVisible(index, 0)
            self._updating = False

    def update_texts(self, translations: 'Translations'):
        """텍스트 업데이트"""
        # 헤더 업데이트
        self._grid.SetColLabelValue(0, translations.tr("frame_list_number"))
        self._grid.SetColLabelValue(1, translations.tr("frame_list_time"))

        # 버튼 툴팁 업데이트
        self._delete_btn.SetToolTip(translations.tr("frame_list_delete_tooltip"))
        self._time_btn.SetToolTip(translations.tr("frame_list_time_tooltip"))
        self._add_btn.SetToolTip(translations.tr("frame_list_add_tooltip"))
