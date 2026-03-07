from fastapi import APIRouter, HTTPException
from ..models.todo import TodoCreate, TodoUpdate, TodoResponse
from ..services.todo_service import TodoService

router = APIRouter(tags=['todos'])
_service = TodoService()


@router.get('/todos', response_model=list[TodoResponse])
def list_todos(page: int = 1, size: int = 20):
    return _service.list_todos(page=page, size=size)


@router.post('/todos', response_model=TodoResponse, status_code=201)
def create_todo(data: TodoCreate):
    return _service.create(data)


@router.get('/todos/{todo_id}', response_model=TodoResponse)
def get_todo(todo_id: int):
    todo = _service.get(todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail='Todo not found')
    return todo


@router.put('/todos/{todo_id}', response_model=TodoResponse)
def update_todo(todo_id: int, data: TodoUpdate):
    todo = _service.update(todo_id, data)
    if not todo:
        raise HTTPException(status_code=404, detail='Todo not found')
    return todo


@router.delete('/todos/{todo_id}', status_code=204)
def delete_todo(todo_id: int):
    if not _service.delete(todo_id):
        raise HTTPException(status_code=404, detail='Todo not found')
