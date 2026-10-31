PYTHON ?= python
.PHONY: dev test lint build
dev:
	docker compose up --build
test:
	cd backend && $(PYTHON) -m pytest -q
	cd frontend && npm test
lint:
	cd backend && $(PYTHON) -m ruff check .
	cd frontend && npm run lint
build:
	cd frontend && npm run build
