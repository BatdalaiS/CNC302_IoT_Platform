# CNC302 — үүлний давхаргын товчлолууд (ЗӨӨВРИЙН КОМПЬЮТЕР дээр)
#
#   make up          core профайлыг асаана
#   make ip          Pi-д өгөх IP хаягийг хэвлэнэ
#   make status      бүх үйлчилгээний төлөв
#
# ⚠ Энэ Makefile-ыг Raspberry Pi дээр ажиллуулахгүй. Pi-д ../edge/Makefile.

COMPOSE  := docker compose
CORE     := --profile core
PIPELINE := --profile core --profile pipeline
APP      := --profile core --profile pipeline --profile app
TB       := -f docker-compose.yml -f docker-compose.tb.yml --profile core --profile tb

.PHONY: help up up-pipeline up-app up-ai up-tb down clean ps logs status ip pull health

help:
	@echo "CNC302 — үүлний давхарга (зөөврийн компьютер)"
	@echo ""
	@echo "  make up            core: emqx, influxdb, grafana, registry"
	@echo "  make up-pipeline   core + nodered            (Лаб 5)"
	@echo "  make up-app        core + nodered + dex + graphql  (Лаб 7)"
	@echo "  make up-ai         + ollama                  (Лаб 8)"
	@echo "  make up-tb         core + ThingsBoard        (Лаб 2, сонголт)"
	@echo ""
	@echo "  make ip            Pi-гийн .env-д бичих CLOUD_HOST"
	@echo "  make status        үйлчилгээ + санах ой"
	@echo "  make health        эрүүл мэндийн шалгалт"
	@echo "  make logs S=emqx   нэг үйлчилгээний лог"
	@echo "  make down          зогсоох (өгөгдөл үлдэнэ)"
	@echo "  make clean         зогсоох + БҮХ ӨГӨГДЛИЙГ УСТГАХ"

up:
	$(COMPOSE) $(CORE) up -d
	@echo "" && $(MAKE) --no-print-directory ip

up-pipeline:
	$(COMPOSE) $(PIPELINE) up -d

up-app:
	$(COMPOSE) $(APP) up -d

up-ai:
	$(COMPOSE) --profile ai up -d ollama

up-tb:
	$(COMPOSE) $(TB) up -d

down:
	$(COMPOSE) --profile core --profile pipeline --profile app --profile ai down

clean:
	@printf 'БҮХ өгөгдөл устана. Итгэлтэй байна уу? [yes/N] ' && read a && [ "$$a" = yes ]
	$(COMPOSE) --profile core --profile pipeline --profile app --profile ai down -v

ps status:
	@$(COMPOSE) ps
	@echo ""
	@docker stats --no-stream --format \
	  'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' 2>/dev/null || true

logs:
	$(COMPOSE) logs -f --tail=100 $(S)

pull:
	$(COMPOSE) --profile core --profile pipeline --profile app --profile ai pull

health:
	@printf 'EMQX      '; curl -s -o /dev/null -w '%{http_code}\n' http://localhost:18083/status || echo DOWN
	@printf 'InfluxDB  '; curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8181/health  || echo DOWN
	@printf 'Grafana   '; curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000/api/health || echo DOWN
	@printf 'Registry  '; curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8090/health || echo DOWN

# Pi-гийн edge/.env файлд CLOUD_HOST= гэж бичих хаяг.
# Windows дээр ажиллахгүй бол:  ipconfig | findstr IPv4
ip:
	@echo "Pi-гийн edge/.env файлд бичих утга:"
	@ip -4 addr show scope global 2>/dev/null \
	   | awk '/inet /{split($$2,a,"/"); print "  CLOUD_HOST=" a[1]}' \
	 || ipconfig 2>/dev/null | grep -i 'IPv4' \
	 || echo "  (гараар олно уу: ipconfig / ifconfig)"
