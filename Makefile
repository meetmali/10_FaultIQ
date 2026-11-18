.PHONY: help setup up down logs api worker frontend test test-api test-pipeline test-frontend lint format typecheck check

export DOTNET_CLI_TELEMETRY_OPTOUT := 1
export DOTNET_NOLOGO := 1

help:  ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

setup:  ## Install all dependencies locally (.NET, Python, Node)
	cd api && dotnet restore --locked-mode
	cd pipeline && uv sync --frozen
	cd frontend && npm ci

up:  ## Start postgres, api, worker and frontend in Docker
	docker compose up --build

down:  ## Stop the Docker services
	docker compose down

logs:  ## Follow the Docker service logs
	docker compose logs -f

api:  ## Run the .NET API locally with hot reload (no Docker)
	cd api && ASPNETCORE_ENVIRONMENT=Development dotnet watch --project src/FaultIQ.Api run --urls http://localhost:8000

worker:  ## Run the Python worker locally (no Docker)
	cd pipeline && uv run python -m worker

frontend:  ## Run the frontend dev server locally (no Docker)
	cd frontend && npm run dev

test: test-api test-pipeline test-frontend  ## Run all tests

test-api:  ## Run .NET API tests
	cd api && dotnet test

test-pipeline:  ## Run Python pipeline tests
	cd pipeline && uv run pytest

test-frontend:  ## Run frontend tests
	cd frontend && npm test

lint:  ## Lint and format-check everything
	cd api && dotnet format --verify-no-changes
	cd pipeline && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint

format:  ## Auto-format .NET and Python code
	cd api && dotnet format
	cd pipeline && uv run ruff format . && uv run ruff check --fix .

typecheck:  ## Type-check / compile everything (warnings are errors)
	cd api && dotnet build --no-restore
	cd pipeline && uv run mypy
	cd frontend && npm run typecheck

check: lint typecheck test  ## Everything CI runs
