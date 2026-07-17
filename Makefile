# =============================================================================
# EquityMind — developer & container workflow
# =============================================================================
# Local development uses `uv`; container targets use Docker Compose.
# Run `make` or `make help` to list targets.
# =============================================================================

# Use docker compose v2 if present, else fall back to legacy docker-compose.
COMPOSE ?= docker compose
IMAGE   ?= equitymind:latest

.DEFAULT_GOAL := help
.PHONY: help install sync run api test lint format typecheck check clean \
        build up down logs shell prod-up prod-down prod-logs

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ---- Local (uv) -------------------------------------------------------------
install: ## Install/refresh the locked environment (uv sync)
	uv sync

sync: install

run: ## Run the CLI, e.g. `make run ARGS="run AAPL MSFT --no-ai"`
	uv run equitymind $(ARGS)

api: ## Launch the FastAPI server locally (no Docker)
	uv run uvicorn equitymind.api.server:app --reload --port 8000

test: ## Run the test suite
	uv run pytest

lint: ## Ruff lint + format check
	uv run ruff check src tests app scripts
	uv run ruff format --check src tests app scripts

format: ## Auto-fix lint issues and format the code
	uv run ruff check --fix src tests app scripts
	uv run ruff format src tests app scripts

typecheck: ## Static type-check with mypy
	uv run mypy

check: lint typecheck test ## Run the full CI gate locally

clean: ## Remove caches and generated artifacts
	rm -rf .pytest_cache .equitymind_cache reports \
		$(shell find . -type d -name __pycache__)

# ---- Containers (Docker) ----------------------------------------------------
build: ## Build the Docker image
	$(COMPOSE) build

up: ## Build (if needed) and serve frontend :3000, API :8000
	$(COMPOSE) up --build -d --remove-orphans
	@echo "EquityMind frontend -> http://localhost:3000"
	@echo "EquityMind API      -> http://localhost:8000 (docs: /docs)"

down: ## Stop and remove the containers
	$(COMPOSE) down

# ---- Production (see deploy/DEPLOY.md) ---------------------------------------
prod-up: ## Prod: build & start on loopback (frontend :5180, api :8020)
	$(COMPOSE) -f docker-compose.prod.yaml up -d --build
	@echo "frontend -> 127.0.0.1:5180 | api -> 127.0.0.1:8020 (за хостовым nginx)"

prod-down: ## Prod: stop and remove containers
	$(COMPOSE) -f docker-compose.prod.yaml down

prod-logs: ## Prod: tail container logs
	$(COMPOSE) -f docker-compose.prod.yaml logs -f

logs: ## Tail container logs
	$(COMPOSE) logs -f

shell: ## Open a shell inside the running api container
	$(COMPOSE) exec api /bin/bash
