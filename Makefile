# Convenience targets. Everything here is also runnable by hand; see README.
.PHONY: up down logs test test-backend test-frontend lint smoke

up:            ## Build and start both services
	docker-compose up --build

down:          ## Stop and remove containers (add -v to drop the SQLite volume)
	docker-compose down

logs:          ## Tail container logs
	docker-compose logs -f

test: test-backend test-frontend  ## Run every test suite

test-backend:  ## pytest suite; API and store tests run against both stores
	cd backend && python -m pytest

test-frontend: ## Vitest + React Testing Library
	cd frontend && npm test

lint:          ## Ruff lint + format check
	cd backend && ruff check . && ruff format --check .

smoke:         ## End-to-end check against a running stack (BASE=http://localhost:5000)
	./scripts/smoke.sh $(or $(BASE),http://localhost:5000)
