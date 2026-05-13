"""Tests for the TODO list."""
import pytest
from todo import TodoList


def test_add_task():
    todo = TodoList()
    task = todo.add("Buy milk")
    assert task.id == 1
    assert task.title == "Buy milk"
    assert task.done is False


def test_complete_task():
    todo = TodoList()
    task = todo.add("Buy milk")
    todo.complete(task.id)
    assert task.done is True


def test_complete_missing_task_raises():
    todo = TodoList()
    with pytest.raises(KeyError):
        todo.complete(999)


def test_remove_task():
    todo = TodoList()
    todo.add("A")
    todo.add("B")
    todo.remove(1)
    assert len(todo.tasks) == 1
    assert todo.tasks[0].title == "B"


def test_pending_excludes_done():
    todo = TodoList()
    todo.add("A")
    b = todo.add("B")
    todo.complete(b.id)
    pending = todo.pending()
    assert len(pending) == 1
    assert pending[0].title == "A"
