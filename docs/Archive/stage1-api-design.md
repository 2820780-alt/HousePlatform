# ЭТАП 1 — ПРОЕКТИРОВАНИЕ API

## ПРИНЦИПЫ
- REST API (FastAPI)
- Аутентификация: JWT Bearer tokens
- Авторизация: role-based (ADMIN, SUPPLIER)
- Версионирование: /api/v1/
- Пагинация: offset/limit
- Формат ответа: JSON
- Валидация: Pydantic v2

---

## ГРУППЫ ЭНДПОИНТОВ

### 1. AUTH — Аутентификация
| Метод | Путь | Описание | Роли |
|-------|------|----------|------|
| POST | /api/v1/auth/register | Регистрация | Public |
| POST | /api/v1/auth/login | Логин (JWT) | Public |
| POST | /api/v1/auth/refresh | Обновление токена | Auth |
| GET | /api/v1/auth/me | Текущий пользователь | Auth |
| PUT | /api/v1/auth/me | Обновление профиля | Auth |

---

### 2. ADMIN — Управление платформой

#### 2.1 Управление пользователями
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/v1/admin/users | Список пользователей |
| GET | /api/v1/admin/users/{id} | Карточка пользователя |
| PUT | /api/v1/admin/users/{id} | Обновить пользователя |
| PATCH | /api/v1/admin/users/{id}/status | Изменить статус |

#### 2.2 Управление поставщиками
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/v1/admin/suppliers | Список поставщиков |
| POST | /api/v1/admin/suppliers | Создать поставщика |
| GET | /api/v1/admin/suppliers/{id} | Карточка поставщика |
| PUT | /api/v1/admin/suppliers/{id} | Обновить поставщика |
| PATCH | /api/v1/admin/suppliers/{id}/status | Изменить статус |

#### 2.3 Загрузка от имени поставщика
| Метод | Путь | Описание |
|-------|------|----------|
| POST | /api/v1/admin/suppliers/{id}/upload | Загрузить документ |
| GET | /api/v1/admin/datasources | Все загрузки |
| GET | /api/v1/admin/datasources/{id} | Детали загрузки |
| POST | /api/v1/admin/datasources/{id}/reprocess | Перезапуск обработки |

#### 2.4 Модерация
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/v1/admin/moderation/pending | Позиции на проверку |
| GET | /api/v1/admin/moderation/{rpl_id} | Детали позиции |
| POST | /api/v1/admin/moderation/{rpl_id}/approve | Подтвердить |
| POST | /api/v1/admin/moderation/{rpl_id}/reject | Отклонить |
| POST | /api/v1/admin/moderation/{rpl_id}/merge | Объединить с материалом |
| POST | /api/v1/admin/moderation/{rpl_id}/create-material | Создать новый материал |

#### 2.5 Управление материалами
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/v1/admin/materials | Список материалов |
| POST | /api/v1/admin/materials | Создать материал |
| GET | /api/v1/admin/materials/{id} | Карточка материала |
| PUT | /api/v1/admin/materials/{id} | Обновить материал |
| POST | /api/v1/admin/materials/{id}/merge/{other_id} | Объединить дубли |
| GET | /api/v1/admin/materials/{id}/offers | Предложения по материалу |
| GET | /api/v1/admin/materials/{id}/price-history | История цен |

#### 2.6 Управление категориями
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/v1/admin/categories | Дерево категорий |
| POST | /api/v1/admin/categories | Создать категорию |
| PUT | /api/v1/admin/categories/{id} | Обновить категорию |
| GET | /api/v1/admin/categories/{id}/schema | Схема характеристик |
| PUT | /api/v1/admin/categories/{id}/schema | Обновить схему |

#### 2.7 Управление единицами измерения
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/v1/admin/units | Список единиц |
| POST | /api/v1/admin/units | Создать единицу |
| PUT | /api/v1/admin/units/{id} | Обновить единицу |
| GET | /api/v1/admin/units/{id}/aliases | Синонимы единицы |
| POST | /api/v1/admin/units/{id}/aliases | Добавить синоним |
| GET | /api/v1/admin/units/conversions | Конвертации |
| POST | /api/v1/admin/units/conversions | Создать конвертацию |

#### 2.8 Аудит
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/v1/admin/audit | Лог событий |

---

### 3. SUPPLIER — Личный кабинет поставщика

#### 3.1 Профиль компании
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/v1/supplier/profile | Мой профиль |
| PUT | /api/v1/supplier/profile | Обновить профиль |

#### 3.2 Филиалы
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/v1/supplier/branches | Мои филиалы |
| POST | /api/v1/supplier/branches | Создать филиал |
| PUT | /api/v1/supplier/branches/{id} | Обновить филиал |
| DELETE | /api/v1/supplier/branches/{id} | Удалить филиал |

#### 3.3 Загрузка документов
| Метод | Путь | Описание |
|-------|------|----------|
| POST | /api/v1/supplier/upload | Загрузить документ |
| GET | /api/v1/supplier/uploads | История загрузок |
| GET | /api/v1/supplier/uploads/{id} | Детали загрузки |

#### 3.4 Мои товары
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/v1/supplier/products | Мои товарные позиции |
| GET | /api/v1/supplier/products/{id} | Детали позиции |
| PUT | /api/v1/supplier/products/{id} | Исправить позицию |
| POST | /api/v1/supplier/products/{id}/confirm | Подтвердить |
| POST | /api/v1/supplier/products/{id}/reprocess | Повторная обработка |

#### 3.5 Мои предложения
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/v1/supplier/offers | Мои предложения |
| PUT | /api/v1/supplier/offers/{id} | Обновить цену/остаток |

#### 3.6 Ошибки
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/v1/supplier/errors | Позиции с ошибками |

---

## СЦЕНАРИИ

### Сценарий: Регистрация поставщика
1. POST /auth/register (role=SUPPLIER)
2. POST /auth/login → JWT
3. PUT /supplier/profile → заполнение карточки
4. POST /supplier/branches → добавление филиалов

### Сценарий: Загрузка прайса поставщиком
1. POST /supplier/upload (file + branch_id + price_date)
2. Система: создаёт DataSource, запускает обработку
3. GET /supplier/uploads/{id} → статус обработки
4. GET /supplier/products → список извлечённых позиций
5. GET /supplier/errors → позиции с ошибками
6. PUT /supplier/products/{id} → исправление ошибок
7. POST /supplier/products/{id}/confirm → подтверждение

### Сценарий: Админ загружает прайс
1. POST /admin/suppliers → создание поставщика (если нового)
2. POST /admin/suppliers/{id}/upload (file + branch_id + price_date)
3. GET /admin/datasources/{id} → статус
4. GET /admin/moderation/pending → позиции для проверки
5. POST /admin/moderation/{id}/approve → подтверждение
6. POST /admin/moderation/{id}/merge → объединение дублей

### Сценарий: Модерация
1. GET /admin/moderation/pending?status=review_required
2. Для каждой позиции:
   - Показать: original_name, normalized_name, category, attributes, matched_material, confidence
   - Действия: approve / reject / merge / create-material
3. POST /admin/moderation/{id}/approve → материал + offer + price_history

---

## ФОРМАТ ОШИБОК
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Описание ошибки",
    "details": [...]
  }
}
```

## ФОРМАТ ПАГИНАЦИИ
```json
{
  "items": [...],
  "total": 150,
  "offset": 0,
  "limit": 20
}
```
