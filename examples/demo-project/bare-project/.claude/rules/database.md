# Database Rules

## SQLAlchemy Configuration
- Use async engine: create_async_engine()
- Session factory: async_sessionmaker()
- Connection string: From pydantic-settings DATABASE_URL
- Pool configuration: Set in engine options

## Model Definitions
- Base class: declarative_base()
- Table names: Explicit with __tablename__
- Columns: Use mapped_column() with proper types
- Relationships: Define with relationship() and back_populates
- Indexes: Add for frequently queried columns

## Async Session Management
- Session dependency: Provide via fastapi.Depends()
- Session lifecycle: Request-scoped sessions
- Always use async with for session context
- Close sessions automatically via middleware

## Query Patterns
- Use await session.execute() for queries
- Filter with where() not filter_by() for async
- Select specific columns, not full objects when possible
- Eager load relationships with selectinload() or joinedload()

## Transactions
- Use async with session.begin() for explicit transactions
- Let FastAPI handle commit/rollback via middleware
- Manual commits only for complex multi-operation logic
- Always rollback on exceptions

## Migration Strategy
- Alembic for schema migrations
- Revision files in alembic/versions/
- Auto-generate with alembic revision --autogenerate
- Apply with alembic upgrade head

## Examples
```python
# Good async model
class Todo(Base):
    __tablename__ = "todos"
    
    id = mapped_column(Integer, primary_key=True)
    title = mapped_column(String(255), nullable=False)
    completed = mapped_column(Boolean, default=False)

# Good async query
async def get_todos(db: AsyncSession):
    result = await db.execute(select(Todo).where(Todo.completed == False))
    return result.scalars().all()
```