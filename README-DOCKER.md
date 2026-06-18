# Запуск через Docker

Docker-контур запускает API-first backend, PostgreSQL и Redis.

## Полный запуск

```powershell
docker compose build
docker compose up
```

API будет доступен по адресу:

```text
http://127.0.0.1:8000
```

Проверка состояния:

```text
GET /api/v1/health
```

FastAPI docs:

```text
http://127.0.0.1:8000/docs
```

Material Hub viewer:

```text
http://127.0.0.1:8000/api/v1/admin/material-hub/view
```

## Только база и Redis

Для локального запуска FastAPI из `.venv` можно поднять только инфраструктуру:

```powershell
docker compose up db redis
```

Затем создать локальный `.env` на основе `.env.local.example`.

## Важно

Текущий основной интерфейс разработки - `/api/v1`.
