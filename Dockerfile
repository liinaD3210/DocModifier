# syntax=docker/dockerfile:1

####################  ЭТАП СБОРКИ  ####################
FROM python:3.11-slim AS builder

# 1. Только нужные системные пакеты (только-build слой)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

# 2. Poetry (фиксируем версию для воспроизводимости)
ENV POETRY_VERSION=2.1.3
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# 3. Копируем только манифесты зависимостей — кэш-слой
WORKDIR /app
COPY pyproject.toml poetry.lock ./


# 4. Собираем прод-зависимости внутрь проекта (.venv)
RUN poetry config virtualenvs.in-project true \
    && poetry install --only main --no-root --no-interaction

# 5. Добавляем исходники (последний слой, меняется чаще всего)
COPY . .

####################  РАНТАЙМ-ОБРАЗ  ####################
FROM python:3.11-slim

WORKDIR /app
# 6. Копируем всё из builder (код + готовое .venv)
COPY --from=builder /app /app

# 7. Переменные окружения
ENV PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    PATH="/app/.venv/bin:$PATH" \
    PIP_NO_CACHE_DIR=1

# (опционально) запускаемся не-root'ом
# RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
# USER appuser

# 8. Старт
CMD ["streamlit", "run", "/app/app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
