# ---------- base: dependências de execução ----------
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- dev: usado pelo VS Code (Dev Container) ----------
FROM base AS dev
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
# Usuário sem privilégios de root (o Claude Code roda como este usuário)
RUN useradd -m -s /bin/bash dev && mkdir -p /home/dev/.claude && chown -R dev:dev /home/dev /app
USER dev
CMD ["sleep", "infinity"]

# ---------- prod: imagem enxuta só com a API ----------
FROM base AS prod
COPY src ./src
COPY dados ./dados
COPY prompts ./prompts
RUN useradd -m app
USER app
EXPOSE 8000
CMD ["uvicorn", "agente_contabil.api:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "src"]
