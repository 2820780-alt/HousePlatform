# Sprint_02_Source_Integration_v1.0

## Цель

Подключить первые реальные источники данных и проверить Material Hub на
реальных карточках товаров, ценах и документах.

Целевая модель Sprint 02 — не собрать несколько тестовых карточек, а
подготовить управляемый механизм полного сбора всех релевантных категорий у
поставщиков, retail-источников и производителей для частного домостроения.
Тестовые лимиты используются только для проверки адаптера и не считаются
целевым объемом базы.

## Режимы сканирования

`SourceTask.parameters` управляет объемом сбора.

Поддерживаемые параметры:

- `scan_mode`: `TEST`, `CATEGORY`, `FULL`;
- `max_pages`: максимальное число успешно разобранных товарных карточек;
- `max_attempts`: максимальное число проверенных URL;
- `max_documents`: максимальное число сохраненных документов;
- `category_url_contains`: строка или список строк для отбора URL категории.

Правила:

- `TEST` используется для проверки адаптера;
- `CATEGORY` используется для поэтапного сбора отдельных категорий;
- `FULL` используется для полного сбора источника и запускается только явно;
- полный сбор должен идти через очередь задач, логи и результаты, а не как
  ручной разовый скрипт;
- все найденные позиции проходят через `CatalogProduct`, `Material`,
  `MaterialMatchCandidate` и модерацию.

## Административный сценарий запуска

Администратор всегда выбирает сбор в три шага:

1. Источники:
   - один источник;
   - несколько источников;
   - все активные источники.

2. Действие:
   - `INITIAL_MATERIAL_SCAN`;
   - `UPDATE_PRICES`;
   - `FIND_NEW_PRODUCTS`;
   - `UPDATE_SPECIFICATIONS`;
   - `UPDATE_CERTIFICATES`;
   - `UPDATE_TECH_DOCUMENTS`;
   - `SCAN_TECHNOLOGIES`;
   - `FULL_INITIAL_SCAN`;
   - `CHECK_SOURCE_HEALTH`;
   - `UPLOAD_SUPPLIER_FILE`.

3. Параметры объема:
   - `TEST`;
   - `CATEGORY`;
   - `FULL`;
   - лимиты страниц/документов;
   - фильтры категорий.

Главное правило:

- `UPDATE_PRICES` обновляет только цены;
- `UPDATE_CERTIFICATES` проверяет только сертификаты;
- `UPDATE_TECH_DOCUMENTS` сохраняет только технические документы;
- `INITIAL_MATERIAL_SCAN` формирует `CatalogProduct` и связывает их с
  `Material`;
- полный охват базы достигается серией управляемых задач, а не запуском всех
  процессов сразу.

## Источники

## Правило источников одного бренда

Если у производителя есть основной сайт и отдельный интернет-магазин, они
создаются как разные `Source`.

Пример:

- `ТЕХНОНИКОЛЬ` — `MANUFACTURER`, технологии, документы, системы, сертификаты;
- `ТЕХНОНИКОЛЬ Shop` — `RETAIL`, карточки товаров, цены, наличие;
- `Гранд Лайн` — `MANUFACTURER`, документы, решения, рекомендации;
- `Гранд Лайн Shop` — `RETAIL`, каталог, цены, наличие.

Оба источника могут ссылаться на один `Material`, но действия, логи, ошибки и
история обновлений хранятся отдельно.

### Бауцентр

Приоритет: 1.

Тип: `RETAIL`.

Базовый URL: `https://baucenter.ru/`.

Способ получения данных:

- публичные HTML-страницы;
- публичный `sitemap.xml`;
- товарные страницы `/product/...`;
- `__NEXT_DATA__` на товарной странице;
- без антибот-обходов;
- без приватных API.

Данные:

- название товара;
- артикул;
- ссылка на товар;
- категория;
- бренд;
- цена, если публично доступна и не равна `0`;
- валюта;
- единица измерения, если указана;
- наличие/тип доступности.

Цены:

- SSR/HTML может отдавать `0`;
- реальная цена берется из публичного API `https://baucenter.ru/api/v2/product/article/{article}`;
- цена приходит в минимальных денежных единицах и нормализуется в рубли;
- наличие берется из `availabilityCount`;
- `0` не сохраняется как реальная цена.

Периодичность:

- `UPDATE_PRICES`: ежедневно или вручную;
- `FIND_NEW_PRODUCTS`: 1-2 раза в неделю;
- `INITIAL_MATERIAL_SCAN`: сначала по категориям, затем полный сбор через
  `scan_mode: FULL`;
- `CHECK_SOURCE_HEALTH`: ежедневно.

Поддерживаемые ACTION:

- `CHECK_SOURCE_HEALTH`
- `INITIAL_MATERIAL_SCAN`
- `UPDATE_PRICES`
- `FIND_NEW_PRODUCTS`

Тест 18.06.2026:

- `https://baucenter.ru/` возвращает `200 OK`;
- `https://baucenter.ru/robots.txt` возвращает `200 OK`;
- `https://baucenter.ru/sitemap.xml` возвращает `200 OK`;
- sitemap содержит товарные URL `/product/...`;
- карточки товаров возвращают `h1`, артикул, бренд, категорию, availability и структуру `__NEXT_DATA__`;
- SSR-цена в проверенных карточках вернулась как `0`, поэтому фиктивные цены не сохраняются;
- публичный API `/api/v2/product/article/{article}` возвращает реальные цены и наличие;
- live smoke-test после подключения API вернул реальные цены, например:
  - OSB 2440x1220x12 мм — `1050 RUB / лст`;
  - OSB 2440x1220x15 мм — `1460 RUB / лст`;
  - OSB 2440x1220x22 мм — `2190 RUB / л.`.

### Лемана ПРО

Статус: fallback/backlog до появления безопасного способа получения данных.

Приоритет: снят с текущего retail-MVP.

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
- замена текущего retail-MVP на Бауцентр.

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

Тест 18.06.2026:

- `https://bonolit.ru/` доступен и возвращает `200 OK`;
- `https://bonolit.ru/sitemap.xml` доступен и содержит `sitemap-iblock-2.xml`;
- `sitemap-iblock-2.xml` содержит товарные URL в `/products/...`;
- часть товарных URL устарела и возвращает `404` или временно `503`, поэтому адаптер пропускает отдельные ошибочные карточки и не валит всю задачу;
- live smoke-test собрал 6 товарных карточек, 32 сертификата и 44 технических документа/файла-ссылки;
- PDF и BIM-файлы пока сохраняются только как ссылки в `MaterialDocument`, без скачивания и анализа содержимого.
- добавлен фильтр мусорных документов: СОУТ, сводные ведомости и документы по
  оценке условий труда не сохраняются как техническая документация Material Hub.
- после фильтра live smoke-test оставил 11 релевантных технических документов.

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

Тест 18.06.2026:

- `https://www.tn.ru/` возвращает `200 OK`;
- `https://www.tn.ru/robots.txt` возвращает `200 OK`;
- `https://www.tn.ru/sitemap.xml` возвращает `200 OK`;
- `https://www.tn.ru/sitemap-main.xml` содержит релевантные разделы продуктов,
  систем и документов;
- `https://shop.tn.ru/` возвращает `403`, поэтому интернет-магазин
  ТЕХНОНИКОЛЬ пока не используется для server-side retail-сбора без
  официального feed/API/выгрузки.

### Гранд Лайн

Приоритет: 4.

Тип: `MANUFACTURER` + отдельный будущий `RETAIL` source для магазина.

Основной URL: `https://www.grandline.ru/`.

Интернет-магазин:

- `https://shop.grandline.ru/` редиректит на `https://www.grandline.ru/katalog/`;
- `https://www.grandline.ru/katalog/` возвращает `200 OK`.

Поддерживаемые ACTION после отдельного адаптера:

- `CHECK_SOURCE_HEALTH`
- `INITIAL_MATERIAL_SCAN`
- `UPDATE_PRICES` для shop-source, если цены доступны публично;
- `FIND_NEW_PRODUCTS` для shop-source;
- `UPDATE_CERTIFICATES` для manufacturer-source;
- `UPDATE_TECH_DOCUMENTS` для manufacturer-source.

Тест 18.06.2026:

- `https://www.grandline.ru/` возвращает `200 OK`;
- `https://shop.grandline.ru/` возвращает `200 OK` после редиректа на каталог;
- сайт подходит как кандидат на следующий live-source после Бауцентра и Bonolit.

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

2. Создать задачу для Бауцентра:

```text
POST /api/v1/admin/material-hub/tasks
```

Тело:

```json
{
  "action_type": "INITIAL_MATERIAL_SCAN",
  "source_ids": ["<baucenter-source-id>"],
  "all_sources": false,
  "parameters": {
    "scan_mode": "CATEGORY",
    "category_url_contains": ["stroymaterialy", "vodosnabzhenie", "elektrotovary"],
    "max_pages": 500,
    "max_attempts": 1500
  }
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

## Read-only просмотр данных

Для контроля результата добавлен read-only viewer:

```text
GET /api/v1/admin/material-hub/view
```

Экран показывает:

- источники;
- последние `SourceTask`;
- `CatalogProduct -> Material`;
- `Material`;
- `MaterialMatchCandidate`;
- `PriceHistory`;
- `MaterialDocument`;
- последние логи и результаты задач.

Viewer не запускает сбор и не изменяет данные. Запуск задач остается через
защищенный API администратора.

## Не входит в Sprint 02

- Module 02 Knowledge Base;
- AI;
- маркетплейс;
- тендеры;
- антибот-обходы;
- глубокий анализ PDF;
- автоматическое принятие спорных решений.
