# CNC302 — ирмэгийн агент (Raspberry Pi 3B / arm64)
#
# Лаб 8 (K3s agent нь Pi дээр, server нь зөөврийн компьютер дээрх VM):
# дүрсийг Pi дээр биш, ЗӨӨВРИЙН КОМПЬЮТЕР дээр arm64-д зориулж барина.
#   docker build --platform linux/arm64 -t cnc302/edge-agent:v1 edge/agent
#   docker save --platform linux/arm64 -o edge-agent-v1-arm64.tar cnc302/edge-agent:v1
# Дараа нь tar файлыг Pi-гийн /var/lib/rancher/k3s/agent/images/ хавтас руу
# хуулна — K3s agent эхлэхдээ тэндээс импортолно (imagePullPolicy: Never).
#   https://docs.docker.com/build/building/multi-platform/
#   https://docs.docker.com/reference/cli/docker/image/save/
#   https://docs.k3s.io/add-ons/import-images
# (`docker save --platform` нь Docker API 1.48+ шаардана — Docker Desktop-оо шинэчил.)
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY edge_agent.py .

# Root-оор ажиллах шаардлагагүй
RUN useradd -u 10001 -m agent
USER agent

# Тэмдэглэл: K3s (Kubernetes) нь Dockerfile-ийн HEALTHCHECK-ийг ашигладаггүй —
# Лаб 8-д liveness/readiness probe-ийг manifest-д бичнэ. Энд зөвхөн
# `docker run` үед python ажиллаж байгааг шалгана.
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s \
  CMD python -c "import sys;sys.exit(0)"

ENTRYPOINT ["python", "edge_agent.py"]
