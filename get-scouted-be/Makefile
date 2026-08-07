.DEFAULT_GOAL := help

VENV       := .venv
PYTHON     := $(VENV)/bin/python
PIP        := $(VENV)/bin/pip
PYTEST     := $(VENV)/bin/pytest
MANAGE     := $(PYTHON) manage.py

COMPOSE      = docker compose
COMPOSE_PROD = docker compose -f docker-compose.prod.yml
LINES       ?= 100

.PHONY: help venv install install-dev migrate makemigrations run shell superuser \
        test test-fast lint format check schema import-data clean \
        docker-up docker-down docker-restart docker-build docker-deploy \
        docker-logs docker-logs-web docker-logs-db \
        docker-migrate docker-superuser docker-shell docker-collectstatic

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

# -----------------------------------------------------------------------
# Docker (local dev via docker-compose.yml, prod via docker-compose.prod.yml)
# See docs/deploy-docker-ec2.md for the full remote deploy walkthrough.
# -----------------------------------------------------------------------
docker-up: ## Start the local dev stack (db + web) in Docker
	$(COMPOSE) up -d

docker-down: ## Stop the local dev Docker stack
	$(COMPOSE) down

docker-restart: ## Restart the local dev Docker stack
	$(COMPOSE) restart

docker-build: ## Build the local dev Docker image
	$(COMPOSE) build

docker-deploy: ## Pull latest code, rebuild image, migrate, and restart prod containers (run ON the server)
	git pull
	docker build -t get-scouted-be:latest .
	$(COMPOSE_PROD) run --rm web python manage.py migrate --no-input
	$(COMPOSE_PROD) run --rm web python manage.py collectstatic --no-input
	$(COMPOSE_PROD) up -d --no-deps --force-recreate web

docker-logs: ## Tail logs for all prod containers (append LINES=N for length, default follows live)
	$(COMPOSE_PROD) logs -f --tail=$(LINES)

docker-logs-web: ## Tail logs for the prod web/gunicorn container
	$(COMPOSE_PROD) logs -f --tail=$(LINES) web

docker-logs-db: ## Tail logs for the prod db container
	$(COMPOSE_PROD) logs -f --tail=$(LINES) db

docker-migrate: ## Run migrations inside the prod web container
	$(COMPOSE_PROD) run --rm web python manage.py migrate --no-input

docker-superuser: ## Create a Django admin superuser inside the prod web container
	$(COMPOSE_PROD) run --rm web python manage.py createsuperuser

docker-shell: ## Open a Django shell inside the prod web container
	$(COMPOSE_PROD) exec web python manage.py shell

docker-collectstatic: ## Collect static files inside the prod web container
	$(COMPOSE_PROD) run --rm web python manage.py collectstatic --no-input
