.DEFAULT_GOAL := help

VENV       := .venv
PYTHON     := $(VENV)/bin/python
PIP        := $(VENV)/bin/pip
PYTEST     := $(VENV)/bin/pytest
MANAGE     := $(PYTHON) manage.py

.PHONY: help venv install install-dev migrate makemigrations run shell superuser \
        test test-fast lint format check schema import-data clean

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

venv: ## Create the project virtualenv (.venv) if it doesn't exist
	test -d $(VENV) || python3 -m venv $(VENV)

install: venv ## Install runtime dependencies into .venv
	$(PIP) install -U pip
	$(PIP) install -r requirements/base.txt

install-dev: venv ## Install runtime + dev/test dependencies into .venv
	$(PIP) install -U pip
	$(PIP) install -r requirements/dev.txt

migrate: ## Apply database migrations
	$(MANAGE) migrate

makemigrations: ## Generate new migrations from model changes
	$(MANAGE) makemigrations

run: ## Run the dev server
	$(MANAGE) runserver

shell: ## Open a Django shell
	$(MANAGE) shell

superuser: ## Create a Django admin superuser
	$(MANAGE) createsuperuser

import-data: ## Run the full Phase 1 CSV -> Postgres data migration (see docs/IMPORT_RUNBOOK.md)
	$(MANAGE) import_all

test: ## Run the full pytest suite
	$(PYTEST)

test-fast: ## Run pytest, stopping at the first failure
	$(PYTEST) -x -q

lint: ## Check code style with ruff (no changes)
	ruff check .

format: ## Auto-format code with ruff
	ruff format .

check: ## Django system check (settings/config sanity)
	$(MANAGE) check

schema: ## Write the current OpenAPI schema to schema.yaml (drf-spectacular)
	$(MANAGE) spectacular --file schema.yaml

clean: ## Remove caches and bytecode
	find . -type d -name "__pycache__" -not -path "./$(VENV)/*" -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
