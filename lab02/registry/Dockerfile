# CNC302 — төхөөрөмжийн бүртгэл (зөөврийн компьютер дээр ажиллана)
FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
RUN useradd -u 10002 -m reg && mkdir -p /data && chown reg /data
USER reg
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import httpx,sys;sys.exit(0 if httpx.get('http://localhost:8090/health',timeout=3).status_code==200 else 1)"
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8090"]
