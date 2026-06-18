# Запуск через Docker

Текущий Docker-контур соответствует `Master_Prompt_v1.0` и запускает API-first
backend.

## Запуск

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

Документация FastAPI:

```text
http://127.0.0.1:8000/docs
```

## Важно

Старые страницы `/`, `/admin`, `/supplier/{id}` относились к SQLite/SQLModel
прототипу и больше не являются основным интерфейсом проекта.

Текущий основной интерфейс разработки — `/api/v1`.
