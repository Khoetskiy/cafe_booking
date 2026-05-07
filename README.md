
# ☕ Cafe Booking API - Сервис бронирования столов в кафе

**Веб-сервис для бронирования столов в кафе с поддержкой ролей пользователей и напоминаниями**

**CafeBooking** — это платформа для управления кафе, бронирования столов по временным слотам, регистрации пользователей и фоновых задач. Пользователи могут бронировать столы, администраторы и менеджеры — управлять заведениями и получать уведомления о событиях.

## Основные возможности

- **Управление пользователями**: Регистрация, блокировка(деактивация), аутентификация и авторизация через JSON Web Tokens (JWT).
- **Управление кафе**: Добавление/редактирование кафе, столов и временных слотов.
- **Бронирование столов**: Выбор времени, бронирование, изменение бронирования.
- **Напоминания и уведомления**: Фоновые задачи через Celery для напоминаний о бронированиях; уведомления администраторам о событиях.
- **Роли пользователей**: Поддержка разных ролей (пользователь, администратор, менеджер кафе).

## API Endpoints

Сервис предоставляет REST API для всех функций. Примеры всех маршрутов указаны в документации — используйте интерактивную документацию Swagger.

>**Полная документация API Swagger:** [Система бронирования мест в кафе - Swagger UI](https://cafebooking.hopto.org/docs)

## 🔐 Security & Permissions (**ЕСЛИ НАДО — ИЗМЕНИТЬ**)

- **JWT Authentication**: Все защищённые маршруты требуют действительного JWT токена.
- **Role-Based Access Control**: Роли определяют доступ к ресурсам и действиям.
- **Password Hashing**: Пароли пользователей хранятся в виде хэшей для безопасности.
- **Input Validation**: Все входные данные проходят валидацию через Pydantic модели.
- **CORS**: Настроены разрешённые источники для обеспечения безопасности при взаимодействии с фронтендом.
- **Secure Configuration**: Все чувствительные данные (секретные ключи, настройки базы данных) хранятся в переменных окружения и не включены в кодовую базу.
- **HTTPS**: Рекомендуется использовать HTTPS в продакшене для защиты данных при передаче.

### 👤 Users

| Метод | Endpoint                           | Описание                       | Админ | Менеджер | Пользователь | Гость |
| ----- | ---------------------------------- | ------------------------------ | ----- | -------- | ------------ | ----- |
| GET   | `/api/v1/users`                      | Получить список пользователей  | ✅     | ❌        | ❌            | ❌     |
| POST  | `/api/v1/users`                      | Регистрация пользователя       | ✅     | ❌        | ❌            | ✅     |
| GET   | `/api/v1/users/me`                   | Получить текущего пользователя | ✅     | ✅        | ✅            | ❌     |
| PATCH | `/api/v1/users/me`                   | Обновить свой профиль          | ✅     | ✅        | ✅            | ❌     |
| GET   | `/api/v1/users/{user_id}`            | Получить пользователя по ID    | ✅     | ❌        | ❌            | ❌     |
| PATCH | `/api/v1/users/{user_id}`            | Обновить пользователя по ID    | ✅     | ❌        | ❌            | ❌     |
| PATCH | `/api/v1/users/{user_id}/role`       | Изменить роль пользователя     | ✅     | ❌        | ❌            | ❌     |
| POST  | `/api/v1/users/{user_id}/activate`   | Активировать пользователя      | ✅     | ❌        | ❌            | ❌     |
| POST  | `/api/v1/users/{user_id}/deactivate` | Деактивировать пользователя    | ✅     | ❌        | ❌            | ❌     |

#### Принципы доступа

- Администратор имеет полный доступ ко всем операциям.
- Менеджер не имеет доступа к управлению пользователями.
- Обычный пользователь может управлять только своим профилем (`/me`).
- Гость может только зарегистрироваться.
- Системные поля (`role`, `is_active`, `cafe_id`) изменяются только через специализированные эндпоинты.

### ☕ Cafes

| Метод | Endpoint                               | Описание                          | Админ | Менеджер                      | Пользователь     | Гость |
|------|----------------------------------------|-----------------------------------|------|------------------------------|------------------|-------|
| GET  | `/api/v1/cafes`                          | Получить список кафе              | ✅    | ✅ (активные + своё)          | ✅ (только активные) | ❌     |
| POST | `/api/v1/cafes`                          | Создать новое кафе                | ✅    | ❌                            | ❌                | ❌     |
| GET  | `/api/v1/cafes/{cafe_id}`                | Получить кафе по ID               | ✅    | ✅ (активные + своё)          | ✅ (только активные) | ❌     |
| PATCH| `/api/v1/cafes/{cafe_id}`                | Обновить данные кафе              | ✅    | ✅ (только своё)              | ❌                | ❌     |
| PATCH| `/api/v1/cafes/{cafe_id}/managers`       | Обновить список менеджеров        | ✅    | ❌                            | ❌                | ❌     |
| POST | `/api/v1/cafes/{cafe_id}/activate`       | Активировать кафе                 | ✅    | ❌                            | ❌                | ❌     |
| POST | `/api/v1/cafes/{cafe_id}/deactivate`     | Деактивировать кафе               | ✅    | ❌                            | ❌                | ❌     |

#### Бизнес-ограничения

- Менеджер может быть привязан только к одному кафе.
- У одного кафе может быть несколько менеджеров.
- Управление менеджерами доступно только администраторам.
- Деактивация кафе не удаляет менеджеров.

### 🍽️ Table

| Метод | Endpoint                                             | Описание                  | Админ         | Менеджер (своё кафе) | Менеджер (чужое) | Пользователь | Гость |
| ----- | ---------------------------------------------------- | ------------------------- | ------------- | -------------------- | ---------------- | ------------ | ----- |
| GET   | `/api/v1/cafes/{cafe_id}/tables`                       | Получить список столов    | ✅ (+show_all) | ✅ все (+show_all)    | ✅ активные       | ✅ активные   | ❌     |
| POST  | `/api/v1/cafes/{cafe_id}/tables`                       | Создать стол              | ✅             | ✅                    | ❌                | ❌            | ❌     |
| GET   | `/api/v1/cafes/{cafe_id}/tables/{table_id}`            | Получить стол по ID       | ✅             | ✅                    | ✅ активные       | ✅ активные   | ❌     |
| PATCH | `/api/v1/cafes/{cafe_id}/tables/{table_id}`            | Обновить стол по ID       | ✅             | ✅                    | ❌                | ❌            | ❌     |
| POST  | `/api/v1/cafes/{cafe_id}/tables/{table_id}/activate`   | Активировать стол по ID   | ✅             | ✅                    | ❌                | ❌            | ❌     |
| POST  | `/api/v1/cafes/{cafe_id}/tables/{table_id}/deactivate` | Деактивировать стол по ID | ✅             | ✅                    | ❌                | ❌            | ❌     |

### 🕰️ Slot

| Метод | Endpoint | Описание | Админ | Менеджер (своё кафе) | Менеджер (чужое) | Пользователь | Гость |
| ----- | -------- | -------- | ----- | -------------------- | ---------------- | ------------ | ----- |
| GET | `/api/v1/cafes/{cafe_id}/time_slots` | Получить список слотов | ✅ (+show_all) | ✅ (+show_all) | ✅ активные | ✅ активные | ❌ |
| POST | `/api/v1/cafes/{cafe_id}/time_slots` | Создать слот | ✅ | ✅ | ❌ | ❌ | ❌ |
| GET | `/api/v1/cafes/{cafe_id}/time_slots/{slot_id}` | Получить слот по ID | ✅ | ✅ | ✅ активный | ✅ активный | ❌ |
| PATCH | `/api/v1/cafes/{cafe_id}/time_slots/{slot_id}` | Обновить слот по ID | ✅ | ✅ | ❌ | ❌ | ❌ |
| POST | `/api/v1/cafes/{cafe_id}/time_slots/{slot_id}/activate` | Активировать слот | ✅ | ✅ | ❌ | ❌ | ❌ |
| POST | `/api/v1/cafes/{cafe_id}/time_slots/{slot_id}/deactivate` | Деактивировать слот | ✅ | ✅ | ❌ | ❌ | ❌ |

- `activate_time_slot` проверяет точный дубль и пересечения перед активацией.
- Создание запрещает точный дубль с неактивным слотом, но разрешает пересечение с неактивным.

### 📅 Bookings

| Метод | Endpoint                                   | Описание                 | Admin              | Manager своё кафе        | Manager чужое кафе | User владелец | User чужая | Guest |
| ----- | ------------------------------------------ | ------------------------ | ------------------ | ------------------------ | ------------------ | ------------- | ---------- | ----- |
| GET   | `/api/v1/bookings`                         | Управленческий список    | ✅ все + `show_all` | ✅ своё кафе + `show_all` | ❌                  | ❌             | ❌          | ❌     |
| POST  | `/api/v1/bookings`                         | Создать бронь            | ✅                  | ✅                        | ✅ как пользователь | ✅             | –          | ❌     |
| GET   | `/api/v1/bookings/me`                      | Мои брони                | ✅                  | ✅                        | ✅                  | ✅             | –          | ❌     |
| GET   | `/api/v1/bookings/{booking_id}`            | Получить бронь           | ✅                  | ✅ своё кафе              | ❌                  | ✅ своя        | ❌          | ❌     |
| PATCH | `/api/v1/bookings/{booking_id}`            | Обновить бронь           | ✅                  | ✅ своё кафе              | ❌                  | ✅ своя        | ❌          | ❌     |
| POST  | `/api/v1/bookings/{booking_id}/confirm`    | Подтвердить бронирование | ✅                  | ✅                        | ❌                  | ❌             | ❌          | ❌     |
| POST  | `/api/v1/bookings/{booking_id}/cancel`     | Отменить бронирование    | ✅                  | ✅                        | ❌                  | ✅             | ❌          | ❌     |
| POST  | `/api/v1/bookings/{booking_id}/complete`   | Завершить бронирование   | ✅                  | ✅                        | ❌                  | ❌             | ❌          | ❌     |
| POST  | `/api/v1/bookings/{booking_id}/activate`   | Активировать бронь       | ✅                  | ✅                        | ❌                  | ❌             | ❌          | ❌     |
| POST  | `/api/v1/bookings/{booking_id}/deactivate` | Деактивировать бронь     | ✅                  | ✅                        | ❌                  | ❌             | ❌          | ❌     |

### 🗃️ Media

|Метод|Endpoint|Описание|Admin|Manager|User|Guest|
|---|---|---|---|---|---|---|
|GET|`/api/v1/media`|Список изображений|✅|❌|❌|❌|
|POST|`/api/v1/media`|Загрузить изображение|✅|✅|❌|❌|
|GET|`/api/v1/media/{media_id}`|Получить изображение|✅|✅|✅|❌|
|DELETE|`/api/v1/media/{media_id}`|Удалить файл и очистить photo_id|✅|❌|❌|❌|

### 🧑‍⚕️ Health

| Метод | Endpoint               | Описание                                                                                                      | Admin | Manager | User | Guest |
| ----- | ---------------------- | ------------------------------------------------------------------------------------------------------------- | ----- | ------- | ---- | ----- |
| GET   | `/api/v1/health/live`  | Проверка живости сервиса (liveness probe)    | ✅     | ✅       | ✅    | ✅     |
| GET   | `/api/v1/health/ready` | Проверка готовности сервиса (readiness probe) | ✅     | ✅       | ✅    | ✅     |

## Технологии

### Backend

![FastAPI](https://img.shields.io/badge/FastAPI-0.124.2-009688?style=for-the-badge&logo=fastapi&logoColor=white) ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0.45-092E20?style=for-the-badge&logo=sqlalchemy&logoColor=white) ![Alembic](https://img.shields.io/badge/Alembic-1.17.2-4CAF50?style=for-the-badge&logo=python&logoColor=white) ![Celery](https://img.shields.io/badge/Celery-5.6.0-37814A?style=for-the-badge&logo=celery&logoColor=white) ![Redis](https://img.shields.io/badge/Redis-7.1.0-DC382D?style=for-the-badge&logo=redis&logoColor=white) ![PyJWT](https://img.shields.io/badge/PyJWT-2.10.1-000000?style=for-the-badge&logo=json-web-tokens&logoColor=white) ![Uvicorn](https://img.shields.io/badge/Uvicorn-0.38.0-2BDE6B?style=for-the-badge&logo=python&logoColor=white) ![Pillow](https://img.shields.io/badge/Pillow-10.2.0-FF6B6B?style=for-the-badge&logo=python&logoColor=white) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)

### DevOps и инструменты

![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white) ![Nginx](https://img.shields.io/badge/Nginx-009639?style=for-the-badge&logo=nginx&logoColor=white) ![Flower](https://img.shields.io/badge/Flower-2.0.1-FFD700?style=for-the-badge&logo=python&logoColor=black) ![Ruff](https://img.shields.io/badge/Ruff-0.7.6-FF69B4?style=for-the-badge&logo=python&logoColor=white) ![Pre-commit](https://img.shields.io/badge/Pre--commit-4CAF50?style=for-the-badge&logo=git&logoColor=white)

> **Полный перечень зависимостей указан в**: `src/requirements.txt`

## Настройка окружения

Проект использует **один файл окружения `.env`**, который должен находиться в папке `infra/`, там же есть `.env.example` для того, **чтобы ознакомиться с необходимыми переменными окружения**.

```bash
# infra/.env.example

# APP
APP_TITLE=Система бронирования мест в кафе
APP_DESCRIPTION=Сервис для бронирования мест в кафе
LOG_LEVEL=INFO
CORS_ORIGINS=["http://localhost:3000"]

# Initial admin bootstrap
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_EMAIL=example@mail.com
INITIAL_ADMIN_PASSWORD=example123

# JWT
# Use for generate secret: openssl rand -hex 32
SECRET_KEY=1503c29a914e23494a51468c5dbcea92b4c1a0ab6708f560ad8e86c7513042a7
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=3600

# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=cafe
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Flower
FLOWER_USER=admin
FLOWER_PASSWORD=strong_password

```

## Запуск приложения

### 1. Локальный запуск backend + db

Удобен для разработки. Запускаем FastAPI **локально**, а базу данных — в **Docker**.

1. Создайте виртуальное окружение и установите зависимости :

```bash
python3 -m venv .venv  # windows: python -m venv .venv
source .venv/bin/activate
```

1. Поднимите только базу данных:

```bash
docker compose -f infra/docker-compose.yml up db --build
```

(Пробрасывает порт 5432 наружу.)

1. Запустите backend:

```bash
cd src
uvicorn app.main:app --reload
```

Backend подключается к `localhost:5432`.

1. Создание и применение миграций:

```bash
cd src
alembic revision --autogenerate -m 'description' # (при необходимости)
alembic upgrade head
```

После запуска сервис доступен по адресу: `http://localhost:8000`, или Swagger docs `http://localhost:8000/docs`

### 2. Локальный запуск в Docker

Для полной разработки в контейнерах:

```bash
docker compose -f infra/docker-compose.yml up --build
```

- Внутри: `RUN_IN_DOCKER=yes`, подключение к `db`.
- Все сервисы в одной сети.

После запуска сервис доступен по адресу: `http://localhost:8000`, или Swagger docs `http://localhost:8000/docs`

### 3. Деплой на удаленный сервер (*условный production*)

> **Требует настройки `.env` для безопасности. Используйте на удалённом сервере.**

1. Предварительно настройте удаленный сервер (Nginx, Docker).

```
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

1. Добавьте `.env` на сервер. (например через `scp`)
2. Настройте Nginx: внешнюю конфигурацию на сервере и внутреннюю в Docker (примеры в `infra/nginx/nginx.conf` и `infra/nginx/nginx_server.conf`).
3. Запустите:

```bash
sudo docker compose -f docker-compose.prod.yml up -d --build
```

Путь к файлу зависит, от того где вы сохраните docker-compose на сервере.

**Предлагаемая структура:**

```
.
├── docker-compose.prod.yml
├── nginx/
│   └── nginx.conf
│   └── .env
```

> `docker-compose.prod.yml` - подразумевает использование образов из DockerHub.

## Автоматическое создание администратора

При старте приложения создаётся администратор, если он отсутствует в БД. Данные берутся из `.env`:

```shell
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_EMAIL=example@mail.com
INITIAL_ADMIN_PASSWORD=example123
```

## 🔔 Фоновые задачи (Celery)

Celery используется для:

- отправки напоминаний о бронировании
- уведомления администратора о событиях бронирования - Брокер и backend: Redis -Запуск воркера происходит в отдельном контейнере celery. Логи Celery можно смотреть через:

```shell
docker logs cafe-celery
```

## Модель ролей

В системе используются следующие роли:

- **ADMIN** — полный доступ ко всем ресурсам
- **MANAGER** — управление кафе и связанными сущностями
- **USER** — управление собственным профилем
- **GUEST** — доступ только к регистрации

> [!warning] Менеджер не имеет дополнительных прав в домене пользователей и обладает расширенными правами только в домене кафе.

Права доступа пользователей реализованы на уровне сервисов и эндпоинтов.

## Стилистика и разработка

Для стилизации кода используются `Ruff` и `Pre-commit`. Зависимости в `requirements_style.txt`.

Команды:

- Проверка:

```bash
ruff check
```

- Автофикс:

```bash
ruff check --fix
```

- Установка хуков:

```bash
pre-commit install
```
