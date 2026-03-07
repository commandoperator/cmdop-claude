# API Development Rules

## FastAPI Patterns
- All endpoints must be async functions
- Response models must be Pydantic models
- Use dependency injection for shared logic (DB sessions, auth)
- Document endpoints with docstrings and response_model parameter

## Route Organization
- Group related endpoints in separate router files
- Prefix routes consistently (e.g., /api/v1/todos)
- Use APIRouter() for modular route definitions
- Import routers in main.py

## Request/Validation
- Request bodies: Use Pydantic models with Field() for validation
- Path/query params: Define in function signature with type hints
- Error responses: Use HTTPException with appropriate status codes
- Validation errors: Let FastAPI handle automatically (422)

## Database Integration
- Use async SQLAlchemy sessions
- Session dependency: Create via fastapi.Depends()
- Transaction management: Use context managers
- Rollback on exceptions, commit on success

## Examples
```python
# Good
@app.get("/todos/{id}", response_model=TodoResponse)
async def get_todo(id: int, db: Session = Depends(get_db)):
    todo = await db.get(Todo, id)
    if not todo:
        raise HTTPException(status_code=404)
    return todo

# Bad (sync DB call)
@app.get("/todos/{id}")
def get_todo(id: int):
    todo = db.query(Todo).filter_by(id=id).first()  # Blocking
    return todo
```