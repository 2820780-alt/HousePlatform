# Sprint_02_Source_Integration_v1.0

## Цель

Подключить первые реальные источники данных и проверить Material Hub на
реальных карточках товаров, ценах и документах.

## Источники

### Лемана ПРО

Приоритет: 1.

Тип: `RETAIL`.

Базовый URL: `https://lemanapro.ru/`.

Способ получения данных:

- публичные HTML-страницы;
- без антибот-обходов;
- без приватных API;
- без поиска по закрытым или запрещенным разделам.

Данные:

- название товара;
- артикул;
- ссылка на товар;
- цена;
- единица измерения;
- регион, если известен;
- сырая категория, если извлечена со страницы;
- бренд/производитель, если уверенно извлечены.

Периодичность:

- `UPDATE_PRICES`: ежедневно или вручную;
- `FIND_NEW_PRODUCTS`: 1-2 раза в неделю;
- `INITIAL_MATERIAL_SCAN`: однократно для выбранного раздела;
- `CHECK_SOURCE_HEALTH`: ежедневно.

Поддерживаемые ACTION:

- `CHECK_SOURCE_HEALTH`
- `INITIAL_MATERIAL_SCAN`
- `UPDATE_PRICES`
- `FIND_NEW_PRODUCTS`

Тест 18.06.2026:

- прямой `httpx` запрос к `https://lemanapro.ru/` вернул `403 Forbidden`;
- `https://lemanapro.ru/robots.txt` также вернул `403 Forbidden`;
- `sitemap.xml` и `/catalogue/` через server-side запрос дали timeout;
- антибот-обходы не используем по правилам Sprint 02.

Вывод: для Лемана ПРО нужна одна из безопасных стратегий:

- официальный feed/API/выгрузка, если доступна;
- ручная CSV/XLSX загрузка для проверки Material Hub;
- тестовый HTML fixture, сохраненный из разрешенного источника вручную;
- переход ко второму источнику Bonolit для первичной проверки live-flow.

### Bonolit

Приоритет: 2.

Тип: `MANUFACTURER`.

Способ получения данных:

- публичный сайт производителя;
- страницы продукции;
- документы и сертификаты, если доступны прямыми ссылками.

Данные:

- материалы;
- производитель;
- характеристики;
- сертификаты;
- технические документы.

Поддерживаемые ACTION на первом этапе:

- `CHECK_SOURCE_HEALTH`
- `INITIAL_MATERIAL_SCAN`
- `UPDATE_SPECIFICATIONS`
- `UPDATE_CERTIFICATES`
- `UPDATE_TECH_DOCUMENTS`

### ТЕХНОНИКОЛЬ

Приоритет: 3.

Тип: `MANUFACTURER`.

Способ получения данных:

- публичный сайт производителя;
- sitemap и публичные страницы каталога;
- документы только как ссылки и файлы, без глубокого анализа.

Поддерживаемые ACTION на первом этапе:

- `CHECK_SOURCE_HEALTH`
- `INITIAL_MATERIAL_SCAN`
- `UPDATE_SPECIFICATIONS`
- `UPDATE_CERTIFICATES`
- `UPDATE_TECH_DOCUMENTS`

## Проверяемый сценарий

```text
Source
↓
SourceTask
↓
CatalogProduct
↓
поиск Material
↓
создание Material при необходимости
↓
MaterialMatchCandidate для спорных совпадений
↓
PriceHistory при изменении цены
```

## Backend-проверка

1. Создать базовые источники:

```text
POST /api/v1/admin/material-hub/sources/defaults
```

2. Создать задачу для Лемана ПРО:

```text
POST /api/v1/admin/material-hub/tasks
```

Тело:

```json
{
  "action_type": "INITIAL_MATERIAL_SCAN",
  "source_ids": ["<lemana-source-id>"],
  "all_sources": false
}
```

3. Запустить задачу:

```text
POST /api/v1/admin/material-hub/tasks/<task-id>/run
```

4. Посмотреть логи:

```text
GET /api/v1/admin/material-hub/tasks/<task-id>/logs
```

5. Посмотреть результаты:

```text
GET /api/v1/admin/material-hub/tasks/<task-id>/results
```

6. Проверить созданные данные:

- `CatalogProduct`
- `Material`
- `MaterialMatchCandidate`
- `PriceHistory`

## Не входит в Sprint 02

- Module 02 Knowledge Base;
- AI;
- маркетплейс;
- тендеры;
- антибот-обходы;
- глубокий анализ PDF;
- автоматическое принятие спорных решений.
