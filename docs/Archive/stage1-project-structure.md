# ЭТАП 1 — СТРУКТУРА ПРОЕКТА

```
build-data-platform/
│
├── docker-compose.yml          # PostgreSQL + Redis + App + Ollama
├── Dockerfile                  # Python app container
├── .env.example                # Пример переменных окружения
├── .gitignore
├── requirements.txt
├── alembic.ini                 # Конфигурация миграций
├── README.md
│
├── docs/                       # Документация
│   ├── stage1-er-model.md
│   ├── stage1-api-design.md
│   └── stage1-project-structure.md
│
├── backup/                     # Скрипты бэкапа
│   ├── backup_db.sh
│   └── restore_db.sh
│
├── migrations/                 # Alembic миграции
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── app/                        # Основное приложение
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, startup
│   ├── config.py               # Настройки из .env
│   ├── database.py             # SQLAlchemy engine, session
│   │
│   ├── models/                 # SQLAlchemy модели
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── supplier.py
│   │   ├── supplier_branch.py
│   │   ├── supplier_account.py
│   │   ├── data_source.py
│   │   ├── raw_product_line.py
│   │   ├── material.py
│   │   ├── material_category.py
│   │   ├── material_alias.py
│   │   ├── material_attribute.py
│   │   ├── material_category_schema.py
│   │   ├── unit.py
│   │   ├── unit_alias.py
│   │   ├── unit_conversion.py
│   │   ├── supplier_offer.py
│   │   ├── price_history.py
│   │   ├── audit_event.py
│   │   └── enums.py            # Все enum-типы
│   │
│   ├── schemas/                # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── supplier.py
│   │   ├── branch.py
│   │   ├── datasource.py
│   │   ├── raw_product_line.py
│   │   ├── material.py
│   │   ├── category.py
│   │   ├── unit.py
│   │   ├── offer.py
│   │   ├── price_history.py
│   │   ├── moderation.py
│   │   └── audit.py
│   │
│   ├── api/                    # Роутеры API
│   │   ├── __init__.py
│   │   ├── deps.py             # Зависимости (get_db, get_current_user)
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py       # Главный роутер v1
│   │   │   ├── auth.py
│   │   │   ├── admin_users.py
│   │   │   ├── admin_suppliers.py
│   │   │   ├── admin_materials.py
│   │   │   ├── admin_categories.py
│   │   │   ├── admin_units.py
│   │   │   ├── admin_moderation.py
│   │   │   ├── admin_datasources.py
│   │   │   ├── admin_audit.py
│   │   │   ├── supplier_profile.py
│   │   │   ├── supplier_branches.py
│   │   │   ├── supplier_upload.py
│   │   │   ├── supplier_products.py
│   │   │   ├── supplier_offers.py
│   │   │   └── supplier_errors.py
│   │
│   ├── services/               # Бизнес-логика
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── supplier_service.py
│   │   ├── upload_service.py
│   │   ├── parsing_service.py      # OCR + парсинг файлов
│   │   ├── normalization_service.py # Нормализация названий
│   │   ├── dedup_service.py         # Поиск дублей
│   │   ├── material_service.py
│   │   ├── offer_service.py
│   │   ├── price_service.py
│   │   ├── unit_service.py
│   │   ├── moderation_service.py
│   │   └── audit_service.py
│   │
│   ├── processing/             # Pipeline обработки документов
│   │   ├── __init__.py
│   │   ├── pipeline.py         # Главный pipeline
│   │   ├── ocr.py              # PaddleOCR + Tesseract
│   │   ├── table_extractor.py  # Извлечение таблиц
│   │   ├── line_extractor.py   # Извлечение строк
│   │   ├── normalizer.py       # Программная нормализация
│   │   ├── category_detector.py # Определение категории
│   │   ├── attribute_extractor.py # Извлечение характеристик
│   │   ├── dedup_scorer.py     # Скоринг совпадений
│   │   └── ai_helper.py        # Обёртка для Ollama
│   │
│   └── core/                   # Утилиты
│       ├── __init__.py
│       ├── security.py         # JWT, hashing
│       └── exceptions.py       # Кастомные исключения
│
├── seeds/                      # Начальные данные
│   ├── units.json
│   ├── unit_aliases.json
│   ├── categories.json
│   └── category_schemas.json
│
├── tests/                      # Тесты
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_supplier.py
│   ├── test_upload.py
│   ├── test_normalization.py
│   └── test_dedup.py
│
└── ui/                         # Frontend (будущее, Jinja2 пока)
    └── ...
```

## ТЕХНОЛОГИЧЕСКИЙ СТЕК

| Компонент | Технология | Почему |
|-----------|-----------|--------|
| Backend | FastAPI | Async, OpenAPI, Pydantic |
| ORM | SQLAlchemy 2.0 | Гибкость, миграции, PostgreSQL |
| Миграции | Alembic | Стандарт для SQLAlchemy |
| БД | PostgreSQL 16 | JSONB, GIN, масштабирование |
| Кэш/очереди | Redis | Для фоновых задач |
| Фоновые задачи | Celery или arq | Обработка документов async |
| Auth | JWT (python-jose) | Stateless, scalable |
| OCR | PaddleOCR + Tesseract | Бесплатно, локально |
| AI | Ollama (Qwen/Llama/Mistral) | Бесплатно, заменяемо |
| Контейнеризация | Docker Compose | Воспроизводимость |
| PDF | pdfplumber | Таблицы из PDF |
| Excel | openpyxl/pandas | Парсинг XLS/XLSX |
