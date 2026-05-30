.PHONY: install lint fmt type test eval-ranking eval-rag up down

install:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

type:
	uv run mypy packages apps tests

test:
	uv run pytest -q

# eval targets are implemented in Steps 5 and 7 respectively
eval-ranking:
	uv run python -m evaluation.ranking.run

eval-rag:
	uv run python -m evaluation.ragas.run

up:
	docker compose -f infra/compose/docker-compose.yml up -d

down:
	docker compose -f infra/compose/docker-compose.yml down
