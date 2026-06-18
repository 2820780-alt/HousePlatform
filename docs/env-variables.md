# Переменные окружения — BUILD DATA PLATFORM

Создайте файл `.env` в корне проекта на основе этих переменных.

## Database
```
DATABASE_URL=postgresql+asyncpg://platform:platform_secret@db:5432/buildplatform
DATABASE_URL_SYNC=postgresql://platform:platform_secret@db:5432/buildplatform
POSTGRES_USER=platform
POSTGRES_PASSWORD=platform_secret
POSTGRES_DB=buildplatform
```

## Redis
```
REDIS_URL=redis://redis:6379/0
```

## JWT Auth
```
JWT_SECRET_KEY=change-me-to-random-secret-key-min-32-chars
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30
```

## App
```
APP_ENV=development
APP_DEBUG=true
APP_HOST=0.0.0.0
APP_PORT=8000
```

## Admin seed
```
ADMIN_EMAIL=admin@buildplatform.ru
ADMIN_PASSWORD=admin123
```

## Ollama AI
```
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b
```

## File upload
```
MAX_UPLOAD_SIZE_MB=50
TEMP_UPLOAD_DIR=/tmp/uploads
```
