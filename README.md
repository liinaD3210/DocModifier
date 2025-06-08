
# DocModifier

**DocModifier** — это веб-приложение на Streamlit для автоматизированного редактирования .docx-документов с помощью LLM (Google Gemini). Пользователь загружает шаблон .docx и формулирует список изменений, которые должны быть внесены в документ.

## Требования

- **Python 3.11**
- **Docker** и **docker-compose** (для запуска через контейнер)
- **Yandex Cloud CLI** (`yc`) — для работы с Yandex Container Registry (опционально, если нужен пуш образа)
- **Google Gemini API ключ** — требуется переменная окружения `GOOGLE_API_KEY` (указывается в `.env`)

## Быстрый старт

1. Создайте файл `.env` в корне проекта и добавьте ваш ключ:
   ```
   GOOGLE_API_KEY=ваш_ключ
   ```
2. Соберите и запустите контейнер:
   ```
   make build
   make run
   ```
   Приложение будет доступно на [http://localhost:8501](http://localhost:8501)

## Основные команды Makefile

- `make build` — сборка Docker-образа
- `make run` — запуск контейнера приложения
- `make stop` — остановка контейнера
- `make logs` — просмотр логов приложения
- `make clean` — полная остановка и очистка контейнеров/томов
- `make login` — авторизация в Yandex Container Registry
- `make push` — пуш Docker-образа в реестр Yandex
- `make pull` — получить образ из реестра
- `make build-and-push` — сборка и пуш в одну команду

## Переменные окружения

- `GOOGLE_API_KEY` — ключ для доступа к Google Gemini API (обязателен)
- (Для работы с Yandex Container Registry: авторизация через `yc iam create-token`)