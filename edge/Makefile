# CNC302 — ирмэгийн давхаргын товчлолууд (RASPBERRY PI 3B дээр)
#
#   make bridge     .env-ээс conf.d/bridge.conf үүсгэнэ   ← ЭХЛЭЭД
#   make up         mosquitto асаана
#   make link       гүүрний төлөвийг харна (1 = холбогдсон)
#   make agent      ирмэгийн агентыг ажиллуулна

SHELL := /bin/bash
ENV   := .env
TPL   := mosquitto/conf.d/bridge.conf.template
OUT   := mosquitto/conf.d/bridge.conf

.PHONY: help bridge up down restart ps logs link mem agent venv clean check

help:
	@echo "CNC302 — ирмэгийн давхарга (Raspberry Pi 3B)"
	@echo ""
	@echo "  make bridge     .env → conf.d/bridge.conf"
	@echo "  make up         mosquitto асаах"
	@echo "  make link       гүүрний төлөв (1=холбогдсон, 0=тасарсан)"
	@echo "  make agent      ирмэгийн агент (venv)"
	@echo "  make mem        санах ойн үлдэгдэл + throttle"
	@echo "  make check      бэлэн байдлын шалгалт"
	@echo "  make logs       mosquitto-гийн лог"
	@echo "  make down       зогсоох"

$(ENV):
	@echo "✗ .env олдсонгүй.  cp .env.example .env  → дараа нь засна уу." >&2
	@exit 1

# .env дэх утгуудыг загварт орлуулж bridge.conf үүсгэнэ.
bridge: $(ENV)
	@set -a; source $(ENV); set +a; \
	if [ "$$CLOUD_HOST" = "192.168.1.100" ]; then \
	  echo "⚠  CLOUD_HOST хэвээрээ байна. Зөөврийн компьютерийнхээ IP-г бичнэ үү."; \
	fi; \
	sed -e "s|__CLOUD_HOST__|$$CLOUD_HOST|g" \
	    -e "s|__CLOUD_PORT__|$$CLOUD_PORT|g" \
	    -e "s|__SITE__|$$SITE|g" \
	    -e "s|__AREA__|$$AREA|g" \
	    -e "s|__LINE__|$$LINE|g" \
	    -e "s|__DEVICE_ID__|$$DEVICE_ID|g" \
	    $(TPL) > $(OUT); \
	echo "✓ $(OUT) үүслээ  →  $$CLOUD_HOST:$$CLOUD_PORT"

up: bridge
	docker compose up -d
	@sleep 3 && docker compose ps

down:
	docker compose down

restart: bridge
	docker compose restart mosquitto

ps:
	@docker compose ps
	@docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}'

logs:
	docker compose logs -f --tail=80 mosquitto

# Гүүр холбогдсон эсэх. 1 = холбогдсон.
link: $(ENV)
	@set -a; source $(ENV); set +a; \
	echo "гүүрний төлөв (Ctrl+C зогсооно):"; \
	mosquitto_sub -h localhost -t "\$$SYS/broker/connection/#" -v \
	  -t "cnc302/$$SITE/$$AREA/$$LINE/$$DEVICE_ID/bridge/state" -v

mem:
	@free -h
	@echo ""
	@printf 'throttle : '; vcgencmd get_throttled 2>/dev/null || echo 'n/a'
	@printf 'темп     : '; vcgencmd measure_temp 2>/dev/null || \
	  awk '{printf "%.1f°C\n", $$1/1000}' /sys/class/thermal/thermal_zone0/temp
	@printf 'ачаалал  : '; cut -d' ' -f1-3 /proc/loadavg

venv:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r agent/requirements.txt

agent: $(ENV)
	@test -d .venv || $(MAKE) venv
	set -a; source $(ENV); set +a; .venv/bin/python agent/edge_agent.py

check:
	@printf 'docker      '; docker --version >/dev/null 2>&1 && echo OK || echo '✗'
	@printf 'mosquitto   '; docker compose ps --status running 2>/dev/null | grep -q mosquitto && echo OK || echo '✗'
	@printf 'bridge.conf '; test -f $(OUT) && echo OK || echo '✗ (make bridge)'
	@printf 'swap        '; free -m | awk '/Swap/{if ($$2>=1900) print "OK (" $$2 " MB)"; else print "✗ " $$2 " MB — SETUP.md Б.4"}'
	@printf 'cgroup      '; grep -q '^memory.*1$$' /proc/cgroups && echo OK || echo '✗ — SETUP.md Б.4'
	@printf 'NTP         '; timedatectl show -p NTPSynchronized --value | grep -q yes && echo OK || echo '✗'
	@printf 'үлдэгдэл    '; free -m | awk '/Mem:/{print $$7 " MB available"}'

clean:
	docker compose down -v
	rm -f $(OUT)
