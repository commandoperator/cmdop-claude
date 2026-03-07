# CLI Development Rules

## Entry Point
- Main CLI: src/my_cli/main.py
- Use if __name__ == "__main__": block
- Parse arguments with argparse or click
- Separate business logic from CLI parsing

## Command Structure
- Subcommands for different operations (create, list, update)
- Consistent argument naming (kebab-case for CLI, snake_case in code)
- Help text for all commands and arguments
- Exit codes: 0 for success, non-zero for errors

## Integration with App
- Reuse application models and logic
- Share configuration via pydantic-settings
- Use same database connection logic
- Avoid duplicating business logic

## Error Handling
- Catch exceptions and print user-friendly messages
- Log detailed errors to stderr or log file
- Validate inputs before calling application logic
- Provide helpful error messages with suggestions

## Output Format
- Default: Human-readable table format
- Optional: JSON output with --json flag
- Progress indicators for long operations
- Color output for success/warning/error messages

## Testing CLI
- Test via subprocess.run()
- Mock external dependencies
- Capture stdout/stderr for assertions
- Test all exit code scenarios

## Examples
```python
# Good structure
import argparse
from todo_app.database import get_async_session
from todo_app.models import Todo

async def create_todo(title: str):
    async with get_async_session() as session:
        todo = Todo(title=title)
        session.add(todo)
        await session.commit()
        return todo

def main():
    parser = argparse.ArgumentParser(description="Todo CLI")
    parser.add_argument("--title", required=True, help="Todo title")
    
    args = parser.parse_args()
    
    # Run async function
    import asyncio
    todo = asyncio.run(create_todo(args.title))
    print(f"Created todo: {todo.id}")

if __name__ == "__main__":
    main()
```