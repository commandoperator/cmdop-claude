from todo_app.models.todo import TodoCreate


def test_create_todo(todo_service):
    todo = todo_service.create(TodoCreate(title='Buy milk'))
    assert todo.id == 1
    assert todo.title == 'Buy milk'
    assert not todo.completed


def test_list_todos(todo_service):
    todo_service.create(TodoCreate(title='Task 1'))
    todo_service.create(TodoCreate(title='Task 2'))
    todos = todo_service.list_todos()
    assert len(todos) == 2
