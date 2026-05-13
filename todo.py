"""Simple in-memory TODO list."""
from dataclasses import dataclass, field
from typing import List


@dataclass
class Task:
    id: int
    title: str
    done: bool = False


@dataclass
class TodoList:
    tasks: List[Task] = field(default_factory=list)
    _next_id: int = 1

    def add(self, title: str) -> Task:
        task = Task(id=self._next_id, title=title)
        self.tasks.append(task)
        self._next_id += 1
        return task

    def complete(self, task_id: int) -> Task:
        for task in self.tasks:
            if task.id == task_id:
                task.done = True
                return task
        raise KeyError(f"Task {task_id} not found")

    def remove(self, task_id: int) -> None:
        self.tasks = [t for t in self.tasks if t.id != task_id]

    def pending(self) -> List[Task]:
        return [t for t in self.tasks if not t.done]
