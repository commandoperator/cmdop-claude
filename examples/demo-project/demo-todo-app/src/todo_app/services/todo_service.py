from datetime import datetime
from typing import Optional
from ..models.todo import TodoCreate, TodoUpdate, TodoResponse


class TodoService:
    """In-memory todo service (replace with DB later)."""

    def __init__(self):
        self._todos: dict[int, dict] = {}
        self._next_id = 1

    def list_todos(self, page: int = 1, size: int = 20) -> list[TodoResponse]:
        items = list(self._todos.values())
        start = (page - 1) * size
        return [TodoResponse(**t) for t in items[start:start + size]]

    def create(self, data: TodoCreate) -> TodoResponse:
        todo = {
            'id': self._next_id,
            'title': data.title,
            'description': data.description,
            'completed': False,
            'priority': data.priority,
            'created_at': datetime.utcnow(),
            'updated_at': None,
        }
        self._todos[self._next_id] = todo
        self._next_id += 1
        return TodoResponse(**todo)

    def get(self, todo_id: int) -> Optional[TodoResponse]:
        todo = self._todos.get(todo_id)
        return TodoResponse(**todo) if todo else None

    def update(self, todo_id: int, data: TodoUpdate) -> Optional[TodoResponse]:
        todo = self._todos.get(todo_id)
        if not todo:
            return None
        update = data.model_dump(exclude_unset=True)
        update['updated_at'] = datetime.utcnow()
        todo.update(update)
        return TodoResponse(**todo)

    def delete(self, todo_id: int) -> bool:
        return self._todos.pop(todo_id, None) is not None
