# MODULE_01_MATERIAL_HUB — Audit v1.7

Дата фиксации: 2026-07-01

Статус: зафиксировано текущее состояние Module №1 после Sprint 0–11 и перед дополнительными спринтами v1.7.

## Границы

Module №1 отвечает за первичный и канонический слой данных Material Hub:

- материалы;
- категории, типы, характеристики и алиасы;
- карточки товаров источников;
- источники, задачи анализа и результаты задач;
- документы и ссылки на документы;
- поставщиков, филиалы, загрузки и цены поставщиков;
- историю цен;
- правила классификации, конвертации единиц и rule memory;
- безопасную подготовку данных для будущих модулей через `moduleCode` / adapter / TODO.

Module №1 не должен:

- создавать или менять Module №2, Module №4, Module №8, Module №11, Module №12;
- редактировать Dashboard;
- редактировать Module Registry или Widget Registry;
- использовать `moduleNumber` как системный идентификатор;
- считать сайт, страницу сайта или карточку товара документом;
- создавать `ACTIVE` canonical `Material` напрямую из сайта, API, файла или парсинга;
- затирать историю цен.

## Найденные сущности

В проекте реально есть ORM / contracts / services для:

- `Material`, `MaterialCategory`, `MaterialType`, `MaterialAttribute`, `MaterialAlias`;
- `MaterialSpecification`, `MaterialDocument`, `MaterialMatchCandidate`, `MaterialQualityIssue`;
- `CatalogProduct`;
- `Source`, `SourceTask`, `SourceTaskLog`, `SourceTaskResult`;
- `Supplier`, `SupplierBranch`, `SupplierPrice`, `SupplierUpload`, `SupplierUploadRow`;
- `PriceHistory`;
- `Unit`, `UnitAlias`, `UnitConversion`, `UnitConversionRule`;
- `ClassificationRule`, `RuleMemory`;
- `KnowledgeResource`, `KnowledgeResourceLink`;
- `SourceProfile`, `ExtractionProfile`, `SourceAdapter`, `SourceParsingRules`, `SourceMappingProfile` as Module №1 contracts/snapshots;
- `RawIngestionItem / IngestionRecord / RawSourceRecord` as DTO contracts;
- `WorkRateObservation` as future-ready observation contract for work rates;
- `MaterialConstructionUsage` and candidates for future Module №2 knowledge enrichment.

## Что реально работает

### Block 0 / запуск сбора

Файлы:

- `templates/material_hub_view.html`;
- `app/api/v1/material_hub_view.py`;
- `app/api/v1/dev_material_hub.py`;
- `app/api/v1/supplier_upload.py`;

Работает:

- выбор источника данных;
- выбор объекта сбора;
- выбор сценария обработки;
- выбор режима запуска;
- режим записи результата: preview / create candidates / write confirmed;
- `CSV/XLSX` как источник данных `FILE`, а не отдельная бизнес-кнопка;
- передача `activeRegionCode`, `source_region_id`, `source_city_id`, `delivery_zone_id`;
- `SourceProfile` snapshot в параметрах задач;
- `PREVIEW` для анализа и upload flow.

Важно сохранить:

- текущий запуск анализа сайтов;
- загрузку CSV/XLSX;
- bounded-параметры `scan_mode`, `max_pages`, `max_attempts`, `max_documents`;
- правило: нормы расхода извлекаются внутри характеристик, а не как отдельный объект сбора.

### Source adapters

Файлы:

- `app/source_integrations/base.py`;
- `app/source_integrations/registry.py`;
- `app/source_integrations/baucenter.py`;
- `app/source_integrations/bonolit.py`;
- `app/source_integrations/grandline.py`;
- `app/source_integrations/technonikol.py`;
- `app/source_integrations/sitemap_catalog.py`;
- `app/source_integrations/lemanapro.py`;
- `app/source_integrations/vseinstrumenti.py`;

Работает:

- registry выбирает adapter по имени/URL источника;
- site adapters возвращают `SourceProduct` / `SourceDocument`;
- runner вызывает `fetch_products()` / `fetch_documents()`;
- блокирующие источники можно оставить в истории и переводить в безопасный режим.

Ограничение:

- registry пока содержит hardcoded routing по имени/URL;
- v1.7 требует постепенно перевести это на обязательный `SourceProfile / ExtractionProfile`.

### File upload

Файлы:

- `app/processing/file_validator.py`;
- `app/processing/file_parser.py`;
- `app/api/v1/dev_material_hub.py`;
- `app/api/v1/supplier_upload.py`;
- `app/services/source_task_runner.py`;

Работает:

- проверка типов файлов;
- парсинг CSV/XLSX;
- `SupplierUpload`;
- `SupplierUploadRow`;
- preview без записи;
- обработка upload через `SourceTask`;
- запись `SupplierPrice` и `PriceHistory` при подтвержденном match.

Ограничение:

- стандарт платформенного прайса еще не выделен как отдельная строгая schema;
- неполные/нестандартные колонки пока требуют дальнейшего `needs_review` workflow.

### Materials / characteristics / documents

Файлы:

- `templates/material_hub_data.html`;
- `templates/material_hub_documents.html`;
- `app/api/v1/material_hub_view.py`;
- `app/models/material_specification.py`;
- `app/models/material_document.py`;
- `app/schemas/material_hub_contracts.py`;

Работает:

- основная таблица материалов;
- характеристики внутри карточки материала;
- отображение source, confidence, verified status и update history;
- нормы расхода как частная характеристика;
- карточка документа с file type, MIME, origin, extraction suitability и parse status;
- предупреждение, что страница сайта сама по себе не является документом.

Ограничение:

- часть document fields пока DTO/helper/UI-level, не все поля persisted в таблице;
- OCR и полноценный parser документов не реализованы.

### Matching / moderation

Файлы:

- `app/services/source_task_runner.py`;
- `app/services/material_pipeline_guard.py`;
- `app/api/v1/admin_moderation.py`;
- `app/api/v1/dev_material_hub.py`;
- `templates/material_hub_moderation.html`;

Работает:

- `CatalogProduct` создается из источника;
- matching пытается найти существующий `Material`;
- спорные случаи попадают в `MaterialMatchCandidate`;
- создание canonical `Material` вынесено в `create_material_from_moderated_candidate()`;
- alias создается только внутри подтвержденного create-from-candidate flow;
- runner не содержит прямого `Material(...)` из анализа источника.

Что можно сохранить:

- `RuleMemory` для подтвержденных похожих случаев;
- текущую модерацию кандидатов;
- `PriceHistory` append-only подход.

## Что является mock / заготовкой

Заготовки без полной persisted-модели:

- `SourceProfile / ExtractionProfile` как snapshot/contract layer;
- `RawIngestionItem / IngestionRecord / RawSourceRecord` как DTO, не отдельная таблица;
- `MaterialConstructionUsage` и `MaterialConstructionUsageCandidate`;
- `SupplierCard` extended contract, future Module №8 link metadata;
- `WorkRateObservation` and `WorkProducerProfile` for future Module №4;
- часть document metadata: checksum, page count, language, parse status, regional restrictions;
- auth-ready placeholders: `created_by`, `updated_by`, `workspace_id`, `source_user_id`, `auth_mode`;
- region-ready placeholders: `region_status`, `source_region_id`, `source_city_id`, `delivery_zone_id`.

Важно:

- эти заготовки не должны становиться бизнес-логикой других модулей;
- Module №1 может хранить/готовить данные, но не реализует кабинеты, сметы, закупки, аналитику или AI.

## Где есть прямое создание Material

Разрешенные места:

- `app/api/v1/admin_materials.py` — ручное создание администратором через admin API. Это не импорт и не парсинг.
- `app/services/material_pipeline_guard.py` — создание из `MaterialMatchCandidate` после модерации.

Нужно контролировать:

- `app/api/v1/admin_moderation.py` использует guard-helper;
- `app/api/v1/dev_material_hub.py` использует guard-helper для dev create-material from candidate;
- `app/services/source_task_runner.py` не должен создавать canonical `Material` напрямую.

Правило:

```text
Source / File
↓
CatalogProduct / RawSourceRecord
↓
Normalization / Field mapping
↓
Matching
↓
MaterialMatchCandidate / DocumentCandidate
↓
Moderation / approved rule
↓
Canonical Material / DocumentRecord
```

## Где есть hardcoded source adapters

Hardcoded adapter routing сейчас в:

- `app/source_integrations/registry.py`;
- site-specific files in `app/source_integrations/`.

Это сохранить для текущей работоспособности, но v1.7 требует:

- каждый источник описывать через `SourceProfile`;
- каждый parser layer описывать через `ExtractionProfile`;
- hardcoded adapter оставить как implementation detail, а не source of truth.

Особые источники:

- LemanaPro и VseInstrumenti есть в коде;
- первая волна v1.7 должна исключить их из автоматического запуска;
- историю не удалять;
- переводить в safe status: `parserStatus = BLOCKED`, `updateMode = disabled`, `writeMode = preview_only`, `trustLevel = PROBLEM/BLOCKED`.

## Что нельзя ломать

Нельзя ломать:

- текущий запуск анализа сайтов;
- текущую загрузку CSV/XLSX;
- `SupplierUpload` / `SupplierUploadRow`;
- matching и moderation;
- append-only `PriceHistory`;
- `SupplierPrice`;
- карточку материала;
- карточку документа;
- source task logs/results;
- `SourceProfile` snapshot в задачах;
- dashboard/module registry/widget registry границы.

## Текущие проверки

Автоматические тесты, которые уже покрывают Module №1:

- `tests/test_file_validator.py`;
- `tests/test_material_quality_gate.py`;
- `tests/test_source_task_parameters.py`;
- `tests/test_source_profiles.py`;
- `tests/test_material_hub_pipeline_guard.py`;
- `tests/test_material_construction_usage.py`;
- `tests/test_material_hub_supplier_work_rates.py`;
- `tests/test_material_taxonomy.py`;
- `tests/test_unit_conversion_rules.py`.

Рекомендуемый quick check после изменений Module №1:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\test_material_hub_pipeline_guard.py `
  tests\test_source_profiles.py `
  tests\test_source_task_parameters.py `
  tests\test_file_validator.py `
  tests\test_material_quality_gate.py `
  tests\test_material_construction_usage.py `
  tests\test_material_hub_supplier_work_rates.py
```

Рекомендуемый UI smoke:

```text
/api/v1/admin/material-hub/view
/api/v1/admin/material-hub/view/materials
/api/v1/admin/material-hub/view/moderation
/api/v1/admin/material-hub/view/documents
```

## TODO v1.7

Следующие безопасные шаги:

- ввести automation statuses: `PREVIEW_ONLY`, `AUTO_PRICE_UPDATED`, `AUTO_LINKED_TO_MATERIAL`, `BATCH_READY`, `NEEDS_UNIT_REVIEW`, `NEEDS_REGION_REVIEW`, `DRAFT_MATERIAL_CREATED`, `SOURCE_STRUCTURE_ERROR`;
- сделать `SourceProfile / ExtractionProfile` обязательным слоем для первой волны источников ЮФО;
- исключить LemanaPro и VseInstrumenti из первой волны без удаления истории;
- формализовать `SourceDocumentRef`;
- добавить document deduplication;
- формализовать стандарт прайса поставщика CSV/XLSX;
- добавить batch moderation groups;
- добавить safe auto-link к существующему `Material` по строгим правилам;
- добавить Draft/Pending Material flow, но не `ACTIVE` auto-create;
- вынести нормализацию в правила: общие и по направлениям;
- добавить автопроверки газобетона, пиломатериалов, арматуры, сухих смесей, кабеля и крепежа;
- добавить persisted raw ingestion layer, если нужен более строгий audit trail.

## Итог

Module №1 уже имеет рабочий Material Hub MVP:

- источники;
- adapters;
- file upload;
- catalog products;
- matching candidates;
- moderation;
- materials;
- characteristics;
- documents;
- suppliers;
- prices;
- price history.

Главные риски сейчас:

- hardcoded adapter routing;
- неполный persisted raw ingestion layer;
- неполная document deduplication;
- отсутствие batch moderation;
- часть v1.7 contracts пока DTO/UI-only;
- первая волна ЮФО еще не зафиксирована в SourceProfile registry.

Главное правило для дальнейшего развития:

```text
Автоматизируем рутину.
Модерируем спорное.
Canonical Material защищаем от мусора.
Документы не теряем.
Историю цен не затираем.
```
