import pytest


@pytest.fixture
def todo_service():
    from todo_app.services.todo_service import TodoService
    return TodoService()
