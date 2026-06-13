SHELL := /bin/bash
PYTHON ?= python3

.PHONY: init up down restart-litellm litellm-config migrate dev test fmt clean

init:
	@test -f .env || cp configs/.env.example .env
	@mkdir -p generated artifacts
	$(PYTHON) -m venv .venv
	. .venv/bin/activate && pip install -U pip && pip install -e ".[dev]"

litellm-config:
	@mkdir -p generated
	. .venv/bin/activate && python -m benchsvc.scripts.generate_litellm_config --output generated/litellm.config.yaml || \
	python -m benchsvc.scripts.generate_litellm_config --output generated/litellm.config.yaml

up: litellm-config
	docker compose up -d

down:
	docker compose down

restart-litellm: litellm-config
	docker compose up -d --force-recreate litellm

migrate:
	. .venv/bin/activate && alembic upgrade head

dev:
	. .venv/bin/activate && uvicorn benchsvc.main:app --reload --host 0.0.0.0 --port 8000

test:
	. .venv/bin/activate && pytest -q

fmt:
	. .venv/bin/activate && ruff check --fix src tests && ruff format src tests

clean:
	rm -rf .pytest_cache .ruff_cache generated/*.yaml artifacts/runs
