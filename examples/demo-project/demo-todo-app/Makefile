.PHONY: run test lint

run:
	uvicorn todo_app.main:app --reload

test:
	pytest -v

lint:
	black src/ tests/
