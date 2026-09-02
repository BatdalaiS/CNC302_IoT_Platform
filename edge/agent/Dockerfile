# CNC302 — ирмэгийн агент (Raspberry Pi 3B / arm64)
#
# Pi 3B дээр барихад 3–6 минут болно. Лаб 8-д K3s рүү оруулахдаа:
#   docker build -t cnc302/edge-agent:v1 .
#   docker save cnc302/edge-agent:v1 | sudo k3s ctr images import -
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY edge_agent.py .

# Root-оор ажиллах шаардлагагүй
RUN useradd -u 10001 -m agent
USER agent

HEALTHCHECK --interval=60s --timeout=5s --start-period=10s \
  CMD python -c "import sys;sys.exit(0)"

ENTRYPOINT ["python", "edge_agent.py"]
