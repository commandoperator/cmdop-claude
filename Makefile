.PHONY: run dev install install-global test lint clean build publish publish-test patch minor major

PORT ?= 8501
PYTHON ?= python

# ── Dev ──────────────────────────────────────────────────────────────

run:
	PYTHONPATH=./src:$$PYTHONPATH $(PYTHON) -m streamlit run src/cmdop_claude/ui/main.py --server.port $(PORT)

dev:
	PYTHONPATH=./src:$$PYTHONPATH $(PYTHON) -m streamlit run src/cmdop_claude/ui/main.py --server.port $(PORT) --server.runOnSave true

install:
	pip install -e .

install-global:
	pip install .

test:
	python -m pytest tests/ -q

lint:
	black src/ tests/
	isort src/ tests/

# ── Version bump ─────────────────────────────────────────────────────

VERSION := $(shell python -c "import tomli; print(tomli.load(open('pyproject.toml','rb'))['project']['version'])")

patch:
	@python -c "\
	parts = '$(VERSION)'.split('.'); \
	parts[2] = str(int(parts[2]) + 1); \
	v = '.'.join(parts); \
	print(f'$(VERSION) → {v}'); \
	t = open('pyproject.toml').read(); \
	open('pyproject.toml','w').write(t.replace('version = \"$(VERSION)\"', f'version = \"{v}\"'))"

minor:
	@python -c "\
	parts = '$(VERSION)'.split('.'); \
	parts[1] = str(int(parts[1]) + 1); parts[2] = '0'; \
	v = '.'.join(parts); \
	print(f'$(VERSION) → {v}'); \
	t = open('pyproject.toml').read(); \
	open('pyproject.toml','w').write(t.replace('version = \"$(VERSION)\"', f'version = \"{v}\"'))"

major:
	@python -c "\
	parts = '$(VERSION)'.split('.'); \
	parts[0] = str(int(parts[0]) + 1); parts[1] = '0'; parts[2] = '0'; \
	v = '.'.join(parts); \
	print(f'$(VERSION) → {v}'); \
	t = open('pyproject.toml').read(); \
	open('pyproject.toml','w').write(t.replace('version = \"$(VERSION)\"', f'version = \"{v}\"'))"

# ── Build & Publish ──────────────────────────────────────────────────

build: clean
	python -m build

publish: build
	python -m twine upload dist/*

publish-test: build
	python -m twine upload --repository testpypi dist/*

# ── Clean ────────────────────────────────────────────────────────────

clean:
	rm -rf dist/ build/ src/*.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
