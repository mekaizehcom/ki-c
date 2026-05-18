.PHONY: up down logs ps build test prod cert bootstrap fmt

COMPOSE = docker compose
PROD = docker compose -f docker-compose.yml -f docker-compose.prod.yml

bootstrap:
	bash infra/scripts/bootstrap.sh

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=120

ps:
	$(COMPOSE) ps

build:
	$(COMPOSE) build

test:
	$(COMPOSE) exec -T tessa-api pytest -q || \
	  docker run --rm -v $(PWD)/services/api:/srv -w /srv python:3.12-slim \
	    sh -c "pip install -q -r requirements.txt pytest && pytest -q"

prod:
	$(PROD) up -d --build

cert:
	bash infra/scripts/issue-cert.sh
