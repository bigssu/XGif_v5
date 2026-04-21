"""
UndoManager - 실행 취소/다시 실행 관리
"""
from __future__ import annotations
from typing import Optional, Callable, List
from abc import ABC, abstractmethod

from ..utils.logger import get_logger

# 로거 초기화
_logger = get_logger()


class UndoableAction(ABC):
    """실행 취소 가능한 작업의 추상 클래스"""

    @abstractmethod
    def execute(self) -> None:
        """작업 실행"""
        pass

    @abstractmethod
    def undo(self) -> None:
        """작업 취소"""
        pass

    def redo(self) -> None:
        """작업 재실행 (기본: execute 호출)"""
        self.execute()

    @property
    @abstractmethod
    def description(self) -> str:
        """작업 설명"""
        pass

    @property
    def memory_usage(self) -> int:
        """메모리 사용량 (바이트)"""
        return 0


class LambdaAction(UndoableAction):
    """람다 기반 간단한 액션"""

    def __init__(self, description: str,
                 execute_func: Callable[[], None],
                 undo_func: Callable[[], None],
                 memory_usage: int = 0):
        self._description = description
        self._execute_func = execute_func
        self._undo_func = undo_func
        self._memory_usage = memory_usage

    def execute(self) -> None:
        try:
            _logger.debug(f"LambdaAction.execute 호출됨: {self._description}")
            self._execute_func()
            _logger.debug(f"LambdaAction.execute 완료: {self._description}")
        except Exception:
            _logger.error(f"Undo action execute error: {self._description}", exc_info=True)
            raise

    def undo(self) -> None:
        try:
            self._undo_func()
        except Exception:
            _logger.error(f"Undo action undo error: {self._description}", exc_info=True)
            raise

    @property
    def description(self) -> str:
        return self._description

    @property
    def memory_usage(self) -> int:
        return self._memory_usage


class GroupAction(UndoableAction):
    """여러 액션을 하나로 묶은 그룹 액션"""

    def __init__(self, description: str, actions: List[UndoableAction]):
        self._description = description
        self._actions = actions

    def execute(self) -> None:
        for action in self._actions:
            action.execute()

    def undo(self) -> None:
        # 역순으로 취소
        for action in reversed(self._actions):
            action.undo()

    def redo(self) -> None:
        for action in self._actions:
            action.redo()

    @property
    def description(self) -> str:
        return self._description

    @property
    def memory_usage(self) -> int:
        return sum(a.memory_usage for a in self._actions)


class UndoManager:
    """Undo/Redo 관리자"""

    def __init__(self, max_history: int = 50,
                 max_memory_mb: float = 500):
        self._undo_stack: List[UndoableAction] = []
        self._redo_stack: List[UndoableAction] = []
        self._max_history = max_history
        self._max_memory = int(max_memory_mb * 1024 * 1024)

        # 그룹 작업용
        self._group_depth = 0
        self._group_description = ""
        self._group_actions: List[UndoableAction] = []

        # 상태 변경 콜백
        self._state_changed_callback: Optional[Callable[[], None]] = None

    # === 액션 실행 ===
    def execute(self, action: UndoableAction) -> None:
        """새 액션 실행 (히스토리에 추가)"""
        _logger.debug(f"UndoManager.execute 호출됨: {action.description}, group_depth={self._group_depth}")
        # 그룹 모드일 때는 그룹에 추가
        if self._group_depth > 0:
            _logger.debug(f"UndoManager.execute 그룹 모드에서 실행: {action.description}")
            action.execute()
            self._group_actions.append(action)
            return

        # 액션 실행
        _logger.debug(f"UndoManager.execute 일반 모드에서 실행: {action.description}")
        action.execute()
        _logger.debug(f"UndoManager.execute 완료: {action.description}")

        # Redo 스택 클리어
        self._redo_stack.clear()

        # Undo 스택에 추가
        self._undo_stack.append(action)

        # 히스토리 크기 제한
        self._trim_history()

        self._notify_state_changed()

    def execute_lambda(self, description: str,
                       execute_func: Callable[[], None],
                       undo_func: Callable[[], None],
                       memory_usage: int = 0) -> None:
        """람다 기반 액션 실행"""
        action = LambdaAction(description, execute_func, undo_func, memory_usage)
        self.execute(action)

    # === Undo/Redo ===
    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def undo(self) -> bool:
        """실행 취소"""
        if not self.can_undo:
            return False

        action = self._undo_stack.pop()
        try:
            action.undo()
        except Exception:
            # undo 실패 시 redo 스택에 넣어 재시도 가능하게 유지
            self._redo_stack.append(action)
            self._notify_state_changed()
            raise
        self._redo_stack.append(action)

        self._notify_state_changed()
        return True

    def redo(self) -> bool:
        """다시 실행"""
        if not self.can_redo:
            return False

        action = self._redo_stack.pop()
        try:
            action.redo()
        except Exception:
            # redo 실패 시 undo 스택에 복원
            self._undo_stack.append(action)
            self._notify_state_changed()
            raise
        self._undo_stack.append(action)

        self._notify_state_changed()
        return True

    def undo_multiple(self, count: int) -> int:
        """여러 단계 실행 취소"""
        undone = 0
        for _ in range(count):
            if self.undo():
                undone += 1
            else:
                break
        return undone

    def redo_multiple(self, count: int) -> int:
        """여러 단계 다시 실행"""
        redone = 0
        for _ in range(count):
            if self.redo():
                redone += 1
            else:
                break
        return redone

    # === 히스토리 관리 ===
    def clear(self) -> None:
        """히스토리 초기화"""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._notify_state_changed()

    @property
    def undo_count(self) -> int:
        return len(self._undo_stack)

    @property
    def redo_count(self) -> int:
        return len(self._redo_stack)

    @property
    def undo_descriptions(self) -> List[str]:
        """Undo 가능한 작업 설명 목록"""
        return [a.description for a in reversed(self._undo_stack)]

    @property
    def redo_descriptions(self) -> List[str]:
        """Redo 가능한 작업 설명 목록"""
        return [a.description for a in reversed(self._redo_stack)]

    @property
    def last_undo_description(self) -> str:
        """마지막 Undo 작업 설명"""
        return self._undo_stack[-1].description if self._undo_stack else ""

    @property
    def last_redo_description(self) -> str:
        """마지막 Redo 작업 설명"""
        return self._redo_stack[-1].description if self._redo_stack else ""

    # === 그룹 작업 ===
    def begin_group(self, description: str) -> None:
        """그룹 작업 시작"""
        if self._group_depth == 0:
            self._group_description = description
            self._group_actions.clear()
        self._group_depth += 1

    def end_group(self) -> None:
        """그룹 작업 종료"""
        if self._group_depth <= 0:
            return

        self._group_depth -= 1

        if self._group_depth == 0 and self._group_actions:
            group_action = GroupAction(
                self._group_description,
                self._group_actions.copy()
            )

            # Redo 스택 클리어
            self._redo_stack.clear()

            # Undo 스택에 추가 (이미 실행됨)
            self._undo_stack.append(group_action)

            self._trim_history()
            self._notify_state_changed()

            self._group_actions.clear()

    @property
    def is_in_group(self) -> bool:
        return self._group_depth > 0

    # === 설정 ===
    @property
    def max_history(self) -> int:
        return self._max_history

    @max_history.setter
    def max_history(self, value: int) -> None:
        self._max_history = max(1, value)
        self._trim_history()

    # === 콜백 ===
    def set_state_changed_callback(self, callback: Optional[Callable[[], None]]) -> None:
        """상태 변경 콜백 설정"""
        self._state_changed_callback = callback

    def _notify_state_changed(self) -> None:
        if self._state_changed_callback:
            self._state_changed_callback()

    # === 트랜잭션 ===
    def transaction(self, description: str) -> "UndoTransaction":
        """배치 작업을 원자적으로 묶는 컨텍스트 매니저.

        Usage:
            with undo_manager.transaction("전체 프레임 이펙트"):
                undo_manager.execute(action1)
                undo_manager.execute(action2)
            # → Ctrl+Z 한 번에 모두 복원

        예외 발생 시 그룹 내 모든 액션을 자동 rollback.
        """
        return UndoTransaction(self, description)

    def rollback_group(self) -> None:
        """현재 그룹 내 모든 액션을 역순으로 undo 실행 후 그룹 해제."""
        if self._group_depth <= 0:
            return
        # 그룹 내 축적된 액션을 역순 undo
        for action in reversed(self._group_actions):
            try:
                action.undo()
            except Exception as e:
                _logger.error("Rollback action failed: %s", e)
        self._group_actions.clear()
        self._group_depth = 0

    # === 내부 ===
    def _trim_history(self) -> None:
        """히스토리 크기 제한"""
        # 먼저 히스토리 개수 제한 (O(n) 일괄 삭제)
        excess = len(self._undo_stack) - self._max_history
        if excess > 0:
            del self._undo_stack[:excess]

        # 메모리 사용량 제한 (더 엄격하게 적용)
        total_memory = sum(a.memory_usage for a in self._undo_stack)
        # 메모리 제한의 80%를 초과하면 오래된 항목부터 제거
        memory_threshold = int(self._max_memory * 0.8)
        trim_count = 0
        while total_memory > memory_threshold and trim_count < len(self._undo_stack) - 1:
            total_memory -= self._undo_stack[trim_count].memory_usage
            trim_count += 1
        if trim_count > 0:
            del self._undo_stack[:trim_count]


class UndoTransaction:
    """배치 작업 원자성을 보장하는 컨텍스트 매니저.

    ``with undo_manager.transaction("desc"):`` 블록 내에서
    실행된 모든 액션은 하나의 그룹으로 묶인다.
    예외 발생 시 그룹 내 모든 액션을 자동 rollback한다.
    """

    def __init__(self, manager: UndoManager, description: str) -> None:
        self._manager = manager
        self._description = description

    def __enter__(self) -> "UndoTransaction":
        self._manager.begin_group(self._description)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            # 예외 발생 → rollback
            _logger.warning(f"UndoTransaction rollback: {self._description} ({exc_val})")
            self._manager.rollback_group()
            return False  # 예외 전파
        self._manager.end_group()
        return False
