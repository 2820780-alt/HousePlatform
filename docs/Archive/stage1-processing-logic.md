# ЭТАП 1 — ЛОГИКА ОБРАБОТКИ ДОКУМЕНТОВ

## 1. ПОДДЕРЖИВАЕМЫЕ ФОРМАТЫ

| Формат | Метод парсинга |
|--------|---------------|
| PDF (текстовый) | pdfplumber |
| XLS | pandas + xlrd |
| XLSX | pandas + openpyxl |
| CSV | pandas |

❌ НЕ поддерживается:
- Фото
- Сканы
- Изображения
- OCR

---

## 2. PIPELINE ОБРАБОТКИ

```
Загрузка файла
    │
    ▼
Определение типа файла
    │
    ├── PDF → pdfplumber → extract_tables() / extract_text()
    ├── XLS/XLSX → pandas.read_excel()
    └── CSV → pandas.read_csv()
    │
    ▼
Извлечение строк (RawProductLine)
    │
    ├── Определить колонки: название / цена / единица / артикул / бренд
    ├── Записать каждую строку как RawProductLine
    └── Статус: EXTRACTED
    │
    ▼
Нормализация (по категории)
    │
    ├── lowercase, trim, убрать лишние символы
    ├── Определить категорию материала (program rules)
    ├── Применить схему характеристик (MaterialCategorySchema)
    ├── Извлечь ключевые атрибуты
    └── Статус: NORMALIZED
    │
    ▼
Поиск совпадений (DedupScorer)
    │
    ├── Fuzzy matching по normalized_name (rapidfuzz)
    ├── Проверка обязательных атрибутов (из CategorySchema)
    ├── Расчёт confidence_score
    └── Статус: MATCHED или REVIEW_REQUIRED
    │
    ▼
AI-помощник (Ollama) — опционально, асинхронно
    │
    ├── Предлагает категорию
    ├── Предлагает canonical_name
    ├── Объясняет причину совпадения
    └── Добавляет к confidence, НЕ принимает решение
    │
    ▼
Финальное решение по confidence_score:
    │
    ├── ≥ 0.90 → авто-merge → SupplierOffer + PriceHistory
    ├── 0.70–0.89 → REVIEW_REQUIRED (admin queue)
    └── < 0.70 → новый черновик Material (admin queue)
```

---

## 3. ПРАВИЛА ПРИНЯТИЯ РЕШЕНИЙ

| Confidence | Действие | Кто решает |
|-----------|---------|-----------|
| ≥ 0.90 | Авто-merge с существующим материалом | Система |
| 0.70–0.89 | Отправить в очередь на проверку | Администратор |
| < 0.70 | Создать черновик нового материала | Администратор |

---

## 4. УЧАСТИЕ ПОСТАВЩИКА

После обработки поставщик видит список своих позиций.

Для каждой позиции система показывает:

- Статус: `matched` / `review_required` / новый
- Найденный материал (если есть совпадение)
- Confidence score
- Предложенную категорию
- Извлечённые атрибуты

Поставщик может:
1. **Подтвердить** совпадение — если материал правильный
2. **Отклонить** совпадение — если материал неверный
3. **Создать новый материал** — всегда идёт в модерацию к администратору

```
Поставщик подтверждает совпадение
    │
    ▼
Система: processing_status → APPROVED
Rule Memory: сохранить паттерн (original_name → material_id)
Создать SupplierOffer
Создать PriceHistory
```

```
Поставщик создаёт новый материал
    │
    ▼
Material.status → DRAFT
RawProductLine.status → REVIEW_REQUIRED
Отправить в очередь модерации (admin)
```

---

## 5. AI MEMORY (RULE-MEMORY LAYER)

Это НЕ машинное обучение.
Это накопление правил из подтверждённых решений.

### Структура паттерна:
```json
{
  "original_name_pattern": "газоблок d500 600x300x200",
  "normalized_pattern": "газоблок d500",
  "material_id": "uuid",
  "category_slug": "gazoblock",
  "attributes": {"density": "500", "size": "600x300x200"},
  "confidence_boost": 0.15,
  "confirmed_count": 5,
  "source": "supplier_confirm | admin_approve",
  "created_at": "2024-01-01"
}
```

### Таблица: `rule_memory`

| Поле | Описание |
|------|---------|
| id | UUID |
| normalized_pattern | Нормализованный паттерн |
| material_id | Куда привязывать |
| category_id | Категория |
| attributes_json | Ключевые атрибуты |
| confidence_boost | Дополнительный буст confidence |
| confirmed_count | Сколько раз подтверждено |
| source | supplier_confirm / admin_approve |
| created_at | Дата создания |
| updated_at | Дата обновления |

### Как используется:

1. При нормализации новой строки:
   - Поиск совпадения с rule_memory по normalized_pattern
   - Если найдено — добавить confidence_boost
   - Если confidence_boost приводит к ≥ 0.90 → авто-merge
2. При каждом подтверждении:
   - Создать или обновить запись в rule_memory
   - Увеличить confirmed_count

---

## 6. SCORING АЛГОРИТМ

### Базовые веса:
| Совпадение | Очки |
|-----------|------|
| Название (fuzzy ≥ 90%) | +30 |
| Категория | +20 |
| Артикул (SKU) | +40 |
| Бренд | +10 |
| Производитель | +5 |

### Штрафы (разные атрибуты):
| Несовпадение | Очки |
|-------------|------|
| Толщина | -50 |
| Плотность | -50 |
| Сечение | -50 |
| Размер | -40 |
| Класс/Марка | -40 |

### Буст из Rule Memory:
- confirmed_count 1–3: +10
- confirmed_count 4–9: +15
- confirmed_count 10+: +20

### Нормализация: итоговый score / max_possible_score → 0.00 – 1.00

---

## 7. НОРМАЛИЗАЦИЯ ПО КАТЕГОРИИ

Нельзя использовать универсальные правила для всех материалов.

```
Определить категорию → загрузить MaterialCategorySchema
→ применить normalization_rules этой схемы
→ извлечь required_attributes
→ извлечь optional_attributes
→ построить attribute fingerprint для сравнения
```

### Пример: Газоблок
```json
{
  "required_attributes": ["density", "size"],
  "optional_attributes": ["strength", "manufacturer"],
  "dedup_rules": {
    "must_match": ["density", "size_volume"],
    "nice_to_match": ["manufacturer"],
    "penalties": {"density_diff": -50, "size_diff": -40}
  }
}
```

### Пример: Арматура
```json
{
  "required_attributes": ["class", "diameter"],
  "optional_attributes": ["length", "surface_type"],
  "dedup_rules": {
    "must_match": ["class", "diameter"],
    "penalties": {"diameter_diff": -50, "class_diff": -40}
  }
}
```

---

## 8. АДМИНИСТРАТОР — ФИНАЛЬНЫЙ АРБИТР

Администратор видит все позиции со статусом `REVIEW_REQUIRED`.

Для каждой позиции он может:
| Действие | Результат |
|---------|---------|
| Подтвердить (approve) | → APPROVED + SupplierOffer + PriceHistory |
| Отклонить (reject) | → REJECTED + причина |
| Объединить с материалом (merge) | → APPROVED + merge |
| Создать новый материал | → новый Material.VERIFIED + APPROVED |

После решения администратора → Rule Memory обновляется автоматически.
