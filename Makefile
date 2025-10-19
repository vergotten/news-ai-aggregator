.PHONY: help build up down logs test clean

help:
	@echo "News Aggregator Commands"
	@echo "make build    - Build images"
	@echo "make up       - Start services"
	@echo "make down     - Stop services"
	@echo "make logs     - Show logs"
	@echo "make test     - Run tests"
	@echo "make clean    - Clean volumes"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

test:
	pytest tests/ -v

clean:
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
