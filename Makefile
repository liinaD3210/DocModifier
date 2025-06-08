# Переменные
REGISTRY = cr.yandex
REPOSITORY = crpg2rfe9anbhi4rem21
IMAGE_NAME = docmodifier
TAG ?= 0.0.1
export TAG 
FULL_IMAGE = $(REGISTRY)/$(REPOSITORY)/$(IMAGE_NAME):$(TAG)

# Команды для работы с Docker
.PHONY: build push login pull

# Сборка и пуш образа
build-and-push: build push

# Сборка образа через docker-compose
build:
	docker compose build

# Пуш образа в реестр
push:
	docker-compose push

# Авторизация в Yandex Container Registry
login:
	yc iam create-token | docker login --username iam --password-stdin $(REGISTRY)

# Получение образа из реестра
pull:
	docker pull $(FULL_IMAGE)

# Запуск контейнера
run:
	docker-compose up -d

# Остановка контейнера
stop:
	docker-compose down

# Просмотр логов
logs:
	docker-compose logs -f

# Очистка
clean:
	docker-compose down -v
	docker system prune -f 