# Module №1 — Legacy Compatibility Map

Статус: M1-0, inventory + compatibility map.

Цель документа — зафиксировать, как текущий legacy/partial слой Module №1 соотносится с целевой архитектурой Material Data Hub v2.0, до любых миграций, переписывания API или изменения UI.

Опорные файлы:

- `docs/modules/module1_material_data_hub_codex_rewrite_v2.md`
- `src/modules/module1/seeds/material_knowledge_seed.json`
- `docs/modules/module2_technology_engine_codex_plan.md`

## 1. Нерушимое правило совместимости

Нельзя создавать параллельные новые таблицы, модели или независимые сущности под новую архитектуру, если в legacy-слое уже есть подходящая сущность. Сначала нужен compatibility adapter: явная карта полей, статусов, источников данных и ограничений.

Raw/import данные не считаются canonical data. Они могут питать matching, moderation и нормализацию, но не должны напрямую становиться каноническим материалом без проверки.

## 2. Текущие legacy / partial сущности Module №1

### Модели данных

- `app/models/material.py` — текущая основа справочника материалов.
- `app/models/catalog_product.py` — raw/normalized карточки товаров источников.
- `app/models/supplier_price.py` — цены поставщиков по материалам.
- `app/models/price_history.py` — история цен.
- `app/models/source.py` — источник данных.
- `app/models/source_task.py` — задача сбора/обработки источника.
- `app/models/source_task_result.py` — результат задачи источника.
- `app/models/supplier.py` — поставщик.
- `app/models/supplier_upload.py` — загрузка файла поставщика.
- `app/models/supplier_upload_row.py` — raw строки загрузки поставщика.
- `app/models/material_document.py` — документы материала.
- `app/models/material_match_candidate.py` — кандидат matching/moderation.
- `app/models/material_quality_issue.py` — проблема качества данных.
- `app/models/material_attribute.py` — атрибуты материала.
- `app/models/material_specification.py` — спецификации материала.
- `app/models/material_category.py` — категории материалов.
- `app/models/material_category_schema.py` — схемы категории.
- `app/models/material_type.py` — типы материалов.
- `app/models/material_alias.py` — алиасы материала.
- `app/models/material_analog.py` — аналоги материала.
- `app/models/knowledge_resource.py` и `app/models/knowledge_resource_link.py` — ресурсная/доказательная база, если используется как evidence layer.

### Сервисы и обработка

- `app/services/material_taxonomy.py`
- `app/services/material_normalization_rules.py`
- `app/services/material_classification.py`
- `app/services/material_pipeline_guard.py`
- `app/services/material_construction_usage.py`
- `app/services/source_task_runner.py`
- `app/services/source_profiles.py`
- `app/services/source_document_refs.py`
- `app/services/source_quality_report.py`
- `app/services/supplier_price_standard.py`
- `app/services/batch_moderation.py`
- `app/processing/file_parser.py`
- `app/processing/file_validator.py`

### Source adapters

- `app/source_integrations/base.py`
- `app/source_integrations/baucenter.py`
- `app/source_integrations/bonolit.py`
- `app/source_integrations/grandline.py`
- `app/source_integrations/html_catalog.py`
- `app/source_integrations/lemanapro.py`
- `app/source_integrations/sitemap_catalog.py`
- `app/source_integrations/technonikol.py`
- `app/source_integrations/vseinstrumenti.py`
- `app/source_integrations/registry.py`

### API и UI

- `app/api/v1/admin_material_hub.py`
- `app/api/v1/admin_materials.py`
- `app/api/v1/admin_moderation.py`
- `app/api/v1/admin_suppliers.py`
- `app/api/v1/dev_material_hub.py`
- `app/api/v1/material_hub_view.py`
- `app/api/v1/supplier_upload.py`
- `templates/material_hub_view.html`
- `templates/material_hub_data.html`
- `templates/material_hub_documents.html`
- `templates/material_hub_moderation.html`
- `templates/supplier.html`

## 3. Compatibility mapping

| Новая сущность | Текущая сущность | Статус | Что оставить | Что адаптировать | Риск |
| --- | --- | --- | --- | --- | --- |
| `CanonicalMaterial` | `Material`, `MaterialAlias`, `MaterialAttribute`, `MaterialSpecification`, `MaterialCategory`, `MaterialType` | Reuse as base | Существующий справочник материалов, связи с категориями, алиасами, атрибутами и спецификациями | Read/write adapter под target contract: canonical name, category, type, status, aliases, technical profile references | Дубли канонических материалов при создании новой таблицы без adapter |
| `RawIngestionItem` | `CatalogProduct`, `SupplierUploadRow`, `SourceTaskResult` | Compatibility layer | Raw поля `raw_name`, `raw_category`, `raw_brand`, `raw_unit`, `raw_price`, `normalized_name`, связь с upload/source/task | Единый adapter, который не повышает raw запись до canonical без moderation/matching | Смешивание raw data и canonical data |
| `PriceObservation` | `SupplierPrice`, `PriceHistory`, частично `CatalogProduct.price` | Compatibility layer | `SupplierPrice` как текущую цену поставщика, `PriceHistory` как историю | Adapter с сохранением supplier/source/time/region/unit и без перезаписи истории | Потеря или затирание истории цен |
| `WorkRateObservation` | Подходящей устойчивой сущности в аудите не найдено | Gap | Ничего не создавать в M1-0 | В M1-1 описать границу: это не Module №2 и не Module №5; добавлять только после отдельного контракта | Риск смешать материалы, технологии и сметы |
| `Document` / `DocumentEvidence` | `MaterialDocument`, `KnowledgeResource`, `KnowledgeResourceLink`, `source_document_refs.py` | Partial reuse | Документы материалов и существующие knowledge links | Evidence adapter: источник, тип документа, привязка к материалу/сырой записи, доверенность evidence | Потеря связи “документ → факт/характеристика” |
| `SourceProfile` | `Source`, `source_profiles.py`, snapshots в source flow | Reuse with adapter | Таблицу источников и profile snapshots | Нормализовать profile contract: тип источника, владелец, регион, надежность, правила сбора | Дубли источников и разные имена одного поставщика |
| `ExtractionProfile` | `source_profiles.py`, `SourceTask.parameters`, source adapters | Partial reuse | Существующие адаптеры и параметры задач | Выделить стабильный extraction config adapter без hardcode в UI/API | SourceAdapter начнет создавать бизнес-сущности напрямую |
| `MaterialTechnicalProfile` | `MaterialAttribute`, `MaterialSpecification`, `MaterialCategorySchema`, seed `characteristicSchemas` | Compatibility layer | Атрибуты, спецификации, схемы категорий, seed knowledge | Read model для Module №2: характеристики, единицы, ограничения, доказательства | Module №2 получит нестабильный или неполный профиль |
| `CharacteristicSchema` | `MaterialCategorySchema`, seed `characteristicSchemas`, `material_taxonomy.py` | Reuse with seed alignment | Текущие схемы категорий и seed | Loader/validator, который сравнивает seed schema с legacy schema | Расхождение seed и таблиц |
| `MaterialRole` | seed `roleMappings`, `material_construction_usage.py`, `MaterialAttribute`/`MaterialSpecification` | Partial reuse | Существующие правила применимости материалов | Adapter для ролей материала без внедрения расчетов Module №2 | Смешивание роли материала с технологическим расчетом |
| `CompatibilityRule` | seed `compatibilityRules`, возможные правила в normalization/taxonomy services | Seed-first | Seed как исходный контракт правил | Сервис чтения правил, без записи в существующие materials напрямую | Непроверенные правила начнут влиять на canonical data |
| `AlternativeRule` | `MaterialAnalog`, seed `alternativeRules` | Reuse with adapter | Существующие аналоги и seed альтернатив | Adapter для причины альтернативы, ограничений и evidence | Потеря контекста “почему это альтернатива” |
| `UnitConversionRule` | seed `unitConversions`, `material_normalization_rules.py`, `supplier_price_standard.py` | Seed/service reuse | Текущие правила нормализации и seed conversion | Единый conversion service contract для импорта и Module №2 read-only профиля | Разные пересчеты в разных частях системы |
| `QualityScore` | `MaterialQualityIssue`, `source_quality_report.py`, `material_pipeline_guard.py` | Partial reuse | Проблемы качества, отчеты источников, pipeline guard | Read model score без автоматического изменения canonical status | Скрытое изменение статуса материалов из-за score |
| `TechnologyInputPackage` | `MaterialTechnicalProfile` adapter + seed schemas/rules | Boundary contract | Только read-only пакет для Module №2 | Сформировать DTO для Module №2 после стабилизации profile adapter | Module №1 начнет считать технологии Module №2 |

## 4. Правила поведения слоев

- `SourceAdapter` не создает `CanonicalMaterial` напрямую.
- Raw/import data не считается canonical data.
- `CatalogProduct`, `SupplierUploadRow` и поля `raw_*` могут использоваться как источник `RawIngestionItem` compatibility layer.
- `Material` может быть текущей основой для `CanonicalMaterial`, если его поля и связи покрывают target contract.
- `SupplierPrice` и `PriceHistory` могут быть основой для `PriceObservation`, но нельзя затирать историю цен.
- `MaterialDocument` может быть основой для `Document` / `DocumentEvidence` layer.
- `MaterialMatchCandidate` должен остаться частью matching/moderation flow.
- `MaterialQualityIssue` и `source_quality_report.py` должны влиять на диагностику качества, но не должны неявно переписывать canonical material.
- `material_knowledge_seed.json` является knowledge seed/contract, а не случайным demo seed.
- Module №1 не должен забирать аналитику Module №11.
- Module №1 не должен считать технологии Module №2.
- Module №1 не должен считать сметы Module №5.
- Module №1 не должен создавать Quick Actions за пользователя; существующие quick-action candidates можно сохранять только как candidates.
- Dashboard widgets Module №1 нельзя ломать при переписывании внутренних слоев.

## 5. Риски перед реализацией Module №1

- Риск дублей моделей: новая архитектура может случайно создать параллельные `CanonicalMaterial`, `RawIngestionItem` или `PriceObservation` рядом с уже существующими `Material`, `CatalogProduct`, `SupplierUploadRow`, `SupplierPrice`, `PriceHistory`.
- Риск миграций поверх существующих таблиц без совместимости.
- Риск сломать Dashboard widgets Module №1: `materials-kpi`, `classification-queue`, `source-health`.
- Риск сломать Quick Action candidates в `templates/material_hub_view.html`.
- Риск смешать Module №1 и Module №11, особенно вокруг `PriceHistory` и `price_dynamics_view.py`.
- Риск смешать raw data и canonical data.
- Риск дать SourceAdapter слишком много ответственности.
- Риск отдать Module №2 нестабильный technical profile.
- Риск начать считать сметные/технологические результаты внутри Module №1.

## 6. Безопасный следующий спринт M1-1

### Что можно делать

- Добавить contract tests на compatibility mapping.
- Добавить read-only adapter interfaces / DTO tests без миграций.
- Проверить, какие поля `Material` покрывают `CanonicalMaterial`.
- Проверить, какие поля `CatalogProduct`, `SupplierUploadRow`, `SourceTaskResult` покрывают `RawIngestionItem`.
- Проверить, какие поля `SupplierPrice` и `PriceHistory` покрывают `PriceObservation`.
- Проверить seed `material_knowledge_seed.json` против текущих taxonomy/schema services.
- Добавить тест, что raw/import слой не создает canonical material напрямую.
- Добавить тест, что SourceAdapter возвращает raw extraction result, а не business entity.

### Какие файлы можно менять в M1-1

- `tests/test_module1_legacy_compatibility_map.py` или близкий новый test-файл.
- `tests/test_material_hub_pipeline_guard.py`
- `tests/test_material_normalization_rules.py`
- `tests/test_material_taxonomy.py`
- Документацию Module №1 в `docs/modules/`.
- Read-only helper/adapter файл только после отдельного подтверждения спринта.

### Какие файлы нельзя менять в M1-1 без отдельного спринта

- `app/models/*.py`
- `database/migrations/*`
- `templates/*`
- `app/api/v1/*`
- `app/services/dashboard_widget_registry.py`
- `app/services/dashboard_module_registry.py`
- `templates/_atom_quick_action_menu.html`
- `templates/material_hub_view.html`, если изменение касается quick actions или UI.
- Любые файлы Module №2, Module №3, Module №5.

### Минимальные тесты для M1-1

- `Material` mapped as candidate base for `CanonicalMaterial`.
- `CatalogProduct` / `SupplierUploadRow` mapped as raw ingestion sources, not canonical materials.
- `SupplierPrice` / `PriceHistory` mapped as price observations without history overwrite.
- `MaterialDocument` mapped as document/evidence source.
- `MaterialMatchCandidate` remains moderation/matching flow.
- Source adapters do not create canonical materials directly.
- Quick Action candidates remain candidates, not fixed/default actions.
- Dashboard widget registry still contains Module №1 widgets.
- Module №1 does not expose Module №2 technology calculation responsibilities.
- Module №1 does not expose Module №5 estimate calculation responsibilities.

## 7. M1-0 acceptance status

- Код не изменяется.
- Миграции не создаются.
- UI не изменяется.
- API не изменяется.
- Module №2 не изменяется.
- Module №3 не изменяется.
- Module №5 не изменяется.
- Dashboard не изменяется.
- Quick Actions не изменяются.
- Единственный ожидаемый файл спринта: `docs/modules/module1_legacy_compatibility_map.md`.
