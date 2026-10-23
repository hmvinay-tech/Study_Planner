# Study Planner - Makefile
# Common development and deployment commands

.PHONY: help install dev test lint format type-check security build up down logs shell migrate superuser collectstatic clean

# Default target
help:
	@echo "Study Planner - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  make install      - Install dependencies"
	@echo "  make dev          - Start development server (Docker)"
	@echo "  make dev-local    - Start development server (local)"
	@echo "  make shell        - Open Django shell"
	@echo "  make migrate      - Run migrations"
	@echo "  make superuser    - Create superuser"
	@echo ""
	@echo "Testing & Quality:"
	@echo "  make test         - Run tests with coverage"
	@echo "  make test-watch   - Run tests in watch mode"
	@echo "  make lint         - Run linters (ruff)"
	@echo "  make format       - Format code (black + ruff)"
	@echo "  make type-check   - Run type checker (mypy)"
	@echo "  make security     - Run security scans"
	@echo ""
	@echo "Docker:"
	@echo "  make build        - Build Docker images"
	@echo "  make up           - Start all services"
	@echo "  make down         - Stop all services"
	@echo "  make logs         - View logs"
	@echo "  make clean        - Clean up Docker resources"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy-staging   - Deploy to staging"
	@echo "  make deploy-prod      - Deploy to production"
	@echo ""

# ============================================
# Development
# ============================================

install:
	pip install -r requirements.txt
	pre-commit install

dev:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build

dev-local:
	python manage.py runserver

shell:
	python manage.py shell_plus 2>/dev/null || python manage.py shell

migrate:
	python manage.py migrate

superuser:
	python manage.py createsuperuser

collectstatic:
	python manage.py collectstatic --noinput

# ============================================
# Testing & Quality
# ============================================

test:
	pytest planner/tests.py -v --cov=planner --cov=config --cov-report=term-missing

test-watch:
	ptw planner/tests.py -- -v

test-unit:
	pytest planner/tests.py -m "unit" -v

test-api:
	pytest planner/tests.py -m "api" -v

test-integration:
	pytest planner/tests.py -m "integration" -v

lint:
	ruff check .

format:
	ruff format .
	ruff check --fix .

type-check:
	mypy planner config

security:
	bandit -r planner config -f json -o bandit-report.json
	safety check --json

# ============================================
# Docker
# ============================================

build:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml build

up:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

down:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml down

down-v:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml down -v

logs:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

logs-web:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml logs -f web

logs-celery:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml logs -f celery_worker celery_beat

clean:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml down -v --remove-orphans
	docker system prune -f

# ============================================
# Database
# ============================================

db-shell:
	docker-compose exec db psql -U study_user -d study_planner

db-backup:
	docker-compose exec db pg_dump -U study_user study_planner > backup_$(date +%Y%m%d_%H%M%S).sql

db-restore:
	@read -p "Backup file: " file; \
	docker-compose exec -T db psql -U study_user -d study_planner < $$file

# ============================================
# Deployment
# ============================================

deploy-staging:
	@echo "Deploying to staging..."
	# Add your staging deployment commands

deploy-prod:
	@echo "Deploying to production..."
	# Add your production deployment commands

# ============================================
# Utilities
# ============================================

check:
	@echo "Running all checks..."
	$(MAKE) lint
	$(MAKE) type-check
	$(MAKE) security
	$(MAKE) test

init-gamification:
	python manage.py init_gamification

create-admin:
	python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Admin user created')
else:
    print('Admin user already exists')
"

reset-db:
	@echo "Resetting database..."
	python manage.py flush --no-input
	python manage.py migrate
	$(MAKE) init-gamification
	$(MAKE) create-admin
	@echo "Database reset complete"

# Default
.DEFAULT_GOAL := help