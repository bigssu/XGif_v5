"""Undo/Redo + 트랜잭션 테스트."""

import pytest
from editor.core.undo_manager import (
    UndoManager, LambdaAction, UndoTransaction,
)


@pytest.fixture
def manager():
    return UndoManager(max_history=10)


class TestUndoRedo:
    def test_execute_and_undo(self, manager):
        results = []
        manager.execute_lambda(
            "add",
            lambda: results.append(1),
            lambda: results.pop(),
        )
        assert results == [1]
        manager.undo()
        assert results == []

    def test_redo(self, manager):
        results = []
        manager.execute_lambda("add", lambda: results.append(1), lambda: results.pop())
        manager.undo()
        manager.redo()
        assert results == [1]

    def test_undo_empty_returns_false(self, manager):
        assert manager.undo() is False

    def test_redo_empty_returns_false(self, manager):
        assert manager.redo() is False

    def test_can_undo(self, manager):
        assert not manager.can_undo
        manager.execute_lambda("x", lambda: None, lambda: None)
        assert manager.can_undo

    def test_max_history(self):
        mgr = UndoManager(max_history=3)
        for i in range(5):
            mgr.execute_lambda(f"action_{i}", lambda: None, lambda: None)
        assert mgr.undo_count == 3


class TestGroupAction:
    def test_begin_end_group(self, manager):
        results = []
        manager.begin_group("batch")
        manager.execute_lambda("a", lambda: results.append("a"), lambda: results.pop())
        manager.execute_lambda("b", lambda: results.append("b"), lambda: results.pop())
        manager.end_group()

        assert results == ["a", "b"]
        assert manager.undo_count == 1  # one group

        manager.undo()
        assert results == []

    def test_rollback_group(self, manager):
        results = []
        manager.begin_group("batch")
        manager.execute_lambda("a", lambda: results.append("a"), lambda: results.pop())
        manager.execute_lambda("b", lambda: results.append("b"), lambda: results.pop())
        manager.rollback_group()
        assert results == []
        assert manager.undo_count == 0


class TestUndoTransaction:
    def test_context_manager_success(self, manager):
        results = []
        with manager.transaction("batch"):
            manager.execute_lambda("a", lambda: results.append("a"), lambda: results.pop())
            manager.execute_lambda("b", lambda: results.append("b"), lambda: results.pop())

        assert results == ["a", "b"]
        assert manager.undo_count == 1

        manager.undo()
        assert results == []

    def test_context_manager_exception_rolls_back(self, manager):
        results = []
        with pytest.raises(ValueError):
            with manager.transaction("fail"):
                manager.execute_lambda("a", lambda: results.append("a"), lambda: results.pop())
                raise ValueError("test error")

        assert results == []  # rolled back
        assert manager.undo_count == 0
