.PHONY: run dev install install-global test lint clean build publish publish-test patch minor major release claude commit sync-docs

PORT ?= 8501
PYTHON ?= python

# ── Dev ──────────────────────────────────────────────────────────────

run:
	-pkill -f "streamlit run" 2>/dev/null; sleep 1
	PYTHONPATH=./src:$$PYTHONPATH $(PYTHON) -m streamlit run src/cmdop_claude/ui/main.py --server.port $(PORT)

dev:
	-pkill -f "streamlit run" 2>/dev/null; sleep 1
	PYTHONPATH=./src:$$PYTHONPATH $(PYTHON) -m streamlit run src/cmdop_claude/ui/main.py --server.port $(PORT) --server.runOnSave true

install:
	pip install -e .

install-global:
	pip install .

test:
	python -m pytest tests/ -q --ignore=tests/e2e

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

# ── Docs sync ────────────────────────────────────────────────────────

# Path to local djangocfg checkout (same pattern as projects/solution/django/Makefile)
DJANGO_CFG_LOCAL := $(HOME)/djangocfg
DOCS_SRC         := $(DJANGO_CFG_LOCAL)/@doc-internal
DOCS_DB          := src/cmdop_claude/docs/docs.db

sync-docs:
	@echo "Building docs FTS5 index from $(DOCS_SRC)..."
	@PYTHONPATH=./src python -c "\
from pathlib import Path; \
from cmdop_claude.services.docs_builder import build_db; \
n = build_db(Path('$(DOCS_SRC)'), Path('$(DOCS_DB)'), 'djangocfg'); \
print(f'Done. Indexed {n} files → $(DOCS_DB)')"

# ── Build & Publish ──────────────────────────────────────────────────

build: clean
	python -m build

publish: sync-docs build
	python -m twine upload dist/*

publish-test: sync-docs build
	python -m twine upload --repository testpypi dist/*

release: test patch
	@echo "── Building & publishing v$$(python -c "import tomli; print(tomli.load(open('pyproject.toml','rb'))['project']['version'])") ──"
	$(MAKE) build
	python -m twine upload dist/*
	git add pyproject.toml
	git commit -m "release: v$$(python -c "import tomli; print(tomli.load(open('pyproject.toml','rb'))['project']['version'])")"
	git push origin main

# ── Claude & Git ─────────────────────────────────────────────────────

claude:
	claude --dangerously-skip-permissions --chrome

commit:
	git add . && orc commit

# ── Clean ────────────────────────────────────────────────────────────

clean:
	rm -rf dist/ build/ src/*.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
