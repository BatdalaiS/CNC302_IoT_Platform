# CNC302 — түгээмэл коммандын товчлол
# Ашиглах: make up | make ps | make logs S=emqx | make down

SHELL := /bin/bash
COMPOSE := docker compose
CORE := --profile core
PIPE := --profile core --profile pipeline
APP  := --profile core --profile pipeline --profile app

.PHONY: help up up-pipe up-app ps logs health down clean stats measure

help:
	@echo "up       — core профайл асаах (Лаб 1+)"
	@echo "up-pipe  — core + pipeline (Лаб 5+)"
	@echo "up-app   — core + pipeline + app (Лаб 7+)"
	@echo "ps       — үйлчилгээний төлөв"
	@echo "health   — healthcheck-ийн төлөв"
	@echo "logs S=x — тухайн үйлчилгээний лог (S=emqx|thingsboard|influxdb|grafana)"
	@echo "stats    — нөөцийн хэрэглээ (нэг агшин)"
	@echo "measure  — нөөцийн хэмжилтийг CSV болгон бичих"
	@echo "down     — зогсоох (өгөгдөл хадгалагдана)"
	@echo "clean    — зогсоож БҮХ өгөгдлийг устгах (болгоомжтой!)"

up:
	$(COMPOSE) $(CORE) up -d

up-pipe:
	$(COMPOSE) $(PIPE) up -d

up-app:
	$(COMPOSE) $(APP) up -d

ps:
	$(COMPOSE) ps

health:
	@docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'cnc302|NAMES'

logs:
	$(COMPOSE) logs -f --tail=100 $(S)

stats:
	@docker stats --no-stream --format \
	  'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'

measure:
	@bash ../tools/measure_stack.sh

down:
	$(COMPOSE) --profile core --profile pipeline --profile app --profile ai down

clean:
	@read -p "БҮХ өгөгдөл устана. Итгэлтэй байна уу? [yes/N] " a; \
	 [ "$$a" = "yes" ] && $(COMPOSE) --profile core --profile pipeline --profile app --profile ai down -v || echo "Цуцлагдлаа"
