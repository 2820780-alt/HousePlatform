# MODULE_01_SOURCE_ADAPTERS_FINAL_AUDIT_v1.7

Дата аудита: 2026-07-02.

Область аудита: Module 01 Material Hub, v1.7 SourceAdapter / SourceProfile / ExtractionProfile / Safe Automation / Batch Moderation.

## Итог

Sprint 25 подтверждает, что Module 01 подготовлен к первой волне безопасного наполнения без обязательного AI и без прямого создания `ACTIVE` canonical Material из сайта, API, файла или импорта.

Главная граница сохранена:

```text
Source / File
-> SourceAdapter / FileAdapter
-> CatalogProduct / RawSourceRecord
-> Normalization
-> MatchingCandidate
-> Safe Automation / Batch Moderation / Manual Review
-> Canonical Material только через подтвержденное правило или модерацию
```

## Проверка требований Sprint 25

| № | Проверка | Статус | Где зафиксировано |
|---|---|---|---|
| 1 | LemanaPro и VseInstrumenti не запускаются в первой волне | OK | `app/services/material_hub_first_wave.py`, `app/source_integrations/lemanapro.py`, `app/source_integrations/vseinstrumenti.py`, `tests/test_material_hub_first_wave_sources.py` |
| 2 | SourceProfile / ExtractionProfile есть или подготовлены | OK | `app/services/source_profiles.py`, `app/schemas/material_hub_contracts.py`, `tests/test_source_profiles.py` |
| 3 | Существующие adapters не сломаны | OK | совместимый слой `attach_source_profile_snapshot()`, tests для first-wave/source profiles |
| 4 | Сайт не создает ACTIVE canonical Material напрямую | OK | `app/services/material_pipeline_guard.py`, `app/services/source_task_runner.py`, `tests/test_material_hub_pipeline_guard.py` |
| 5 | Auto price update только по подтвержденным связям | OK | `app/services/safe_automation_policy.py`, `tests/test_safe_automation_policy.py` |
| 6 | Auto-link только к существующему Material и по строгим правилам | OK | `AutoLinkPolicy`, RuleMemory requirement, `tests/test_safe_automation_policy.py` |
| 7 | Новый Material только Draft/Pending или через модерацию | OK | `DraftMaterialPolicy`, `create_material_from_moderated_candidate()` guard |
| 8 | Batch moderation работает для тысяч позиций | Prepared | `app/services/batch_moderation.py`, `tests/test_batch_moderation.py` |
| 9 | RuleMemory не создает глобальные опасные правила | OK | scoped payload в `app/services/rule_memory.py`, guardrails в тестах |
| 10 | Документы собираются и не теряются | Prepared | `app/services/source_document_refs.py`, `SourceDocumentRef`, `tests/test_source_document_refs.py` |
| 11 | Сайт не считается документом | OK | `site_page_is_document = false` в parsing rules, document refs tests |
| 12 | Одинаковые документы не плодятся массово | Prepared | dedupe key / duplicate policy в `source_document_refs.py` |
| 13 | Стандарт CSV/XLSX прайса поставщика есть | OK | `app/services/supplier_price_standard.py`, `docs/Templates/ATOM_supplier_price_template.*` |
| 14 | Прайс без обязательных колонок не пишет данные в базу | OK | validation error в upload flow, `tests/test_supplier_price_standard.py` |
| 15 | История цен не затирается | OK | `PriceHistory` append в `source_task_runner.py` |
| 16 | Региональность сохраняется | OK | region fields in parser/source profiles/quality report; `region_status = needs_review` fallback |
| 17 | Auth-ready поля не удалены | OK | Module 01 contracts keep `created_by`, `updated_by`, `approved_by`, `moderator_id`, `workspace_id`, `source_user_id`, `auth_mode` |
| 18 | Module 01 не редактирует Dashboard, Module 03, Module 08 и другие бизнес-модули | OK | изменения ограничены Module 01 services/API/docs/tests |
| 19 | AI не является обязательной зависимостью Module 01 | OK | AI не используется в adapter/source pipeline |
| 20 | Связи с будущими модулями через moduleCode / adapter / TODO | OK | Module 01 contracts and boundary fields use module code/adapters, not moduleNumber |

## Измененные файлы

Ключевые изменения v1.7 Source Adapters:

```text
app/api/v1/admin_material_hub.py
app/api/v1/dev_material_hub.py
app/api/v1/material_hub_view.py
app/api/v1/supplier_upload.py
app/processing/file_parser.py
app/schemas/material_hub_contracts.py
app/services/batch_moderation.py
app/services/material_hub_first_wave.py
app/services/material_normalization_rules.py
app/services/rule_memory.py
app/services/safe_automation_policy.py
app/services/source_adapter_template.py
app/services/source_document_refs.py
app/services/source_profiles.py
app/services/source_quality_report.py
app/services/source_task_runner.py
app/services/supplier_price_standard.py
app/source_integrations/base.py
app/source_integrations/bonolit.py
app/source_integrations/lemanapro.py
app/source_integrations/vseinstrumenti.py
docs/Templates/ATOM_supplier_price_template.csv
docs/Templates/ATOM_supplier_price_template.xlsx
docs/Modules/MODULE_01_MATERIAL_HUB_AUDIT_v1.7.md
templates/material_hub_data.html
templates/material_hub_view.html
tests/test_batch_moderation.py
tests/test_material_hub_first_wave_sources.py
tests/test_material_hub_pipeline_guard.py
tests/test_material_normalization_rules.py
tests/test_safe_automation_policy.py
tests/test_source_adapter_template.py
tests/test_source_document_refs.py
tests/test_source_profiles.py
tests/test_source_quality_report.py
tests/test_supplier_price_standard.py
```

## Добавленные / подготовленные сущности

```text
SafeAutomationPolicy
AutoLinkPolicy
AutoPriceUpdatePolicy
DraftMaterialPolicy
BatchModerationPolicy
SourceTrustPolicy
AutomationDecision
SourceDocumentRef / DocumentCandidate
SourceProfile
ExtractionProfile
SourceAdapterConfig
SourceCategoryMapping
SourceNormalizationRule
SourceModerationRule
SourceQualityReport
CandidateGroup
BatchModerationQueue
BatchModerationDecision
BatchRuleSuggestion
FirstWaveSourceSeed
Supplier price standard template
```

## Что автоматизировано

```text
1. Safe automation decision layer:
   - canAutoUpdatePrice();
   - canAutoLinkToMaterial();
   - canCreateDraftMaterial();
   - shouldGoToBatchModeration();
   - shouldRequireManualReview();
   - getAutomationReason().

2. SourceProfile / ExtractionProfile snapshot:
   - создается через attach_source_profile_snapshot();
   - не ломает старые adapters;
   - содержит parsing / mapping / moderation / document rules.

3. Document candidate collection:
   - adapters могут возвращать SourceDocumentRef;
   - документы получают тип, fileType, suitability, parse_status, sourceCode;
   - сайт / каталог / карточка товара не становятся документом.

4. CSV/XLSX supplier price standard:
   - есть шаблоны;
   - обязательные колонки валидируются;
   - invalid file не пишет данные в базу.

5. Batch moderation:
   - группировка кандидатов по sourceCode, category, matchedMaterialId, brand, manufacturer, dimensions, unit, normalizationRule, reviewReason;
   - group confirm / reject / split / confirm selected / create rule / manual review;
   - RuleMemory пишется scoped, не глобально.

6. SourceQualityReport:
   - формируется для SourceTask summary;
   - содержит счетчики товаров, цен, availability, документов, сертификатов, common units и parser problems;
   - recommendedNextAction ограничивает повышение trustLevel.
```

## Что остается на модерацию

```text
- подтверждение baseUrl для части источников первой волны;
- проверка 5-20 testUrls на каждый новый сайт;
- category mapping для каждого источника;
- unit mapping / converter для нестандартных единиц;
- document dedupe в спорных случаях;
- batch confirmation групп;
- перевод источника из TEST / preview_only в create_candidates;
- любое создание нового canonical Material;
- повышение trustLevel выше TEST.
```

## Отключенные источники

```text
LemanaPro
VseInstrumenti
```

Политика:

```text
parserStatus = BLOCKED
updateMode = disabled
writeMode = preview_only
trustLevel = BLOCKED / PROBLEM
```

История и adapters не удалены. Автоматический запуск и обход блокировок запрещены.

## Источники первой волны ЮФО, готовые к preview/test

Все источники первой волны создаются как:

```text
status = PAUSED
parserStatus = TEST
writeMode = preview_only
trustLevel = TEST
```

Список:

```text
Строй-С
ТД Муравей
ВКБлок
КСМК Газобетон Краснодар
Кирпичный Двор
Кровля и Изоляция
Roof Materials
ССТ КВИК
Доска-Брус
Профи Лес
1Металлобаза Краснодар
СПК Краснодар
ЮгКабель
Промметиз
Экватор
```

Подтвержденные в коде `baseUrl`:

```text
ВКБлок -> https://vkblock.ru/
ЮгКабель -> https://yugkabel.ru/
```

Для остальных источников `baseUrl` требует ручной проверки перед реальным adapter run.

## Как собираются документы

Документы собираются через `SourceDocumentRef` / `DocumentCandidate`, если источник явно дает:

```text
сертификаты;
декларации;
технические листы;
инструкции;
паспорта;
каталоги;
альбомы решений;
руководства по применению;
узлы;
региональные прайсы;
условия доставки.
```

Запрещено и проверено:

```text
страница каталога сайта != DocumentRecord;
карточка товара сайта != DocumentRecord;
обычная HTML-страница без document markers != DocumentRecord.
```

Дедупликация подготовлена по:

```text
url;
filename/title;
document type;
manufacturer/product;
source;
checksum/hash, если доступен.
```

## Проверки, которые запускались

```text
python -m compileall app/schemas/material_hub_contracts.py app/services/batch_moderation.py app/services/rule_memory.py tests/test_batch_moderation.py

python -m pytest tests/test_batch_moderation.py tests/test_safe_automation_policy.py tests/test_material_hub_pipeline_guard.py tests/test_material_normalization_rules.py

python -m compileall app/services/material_hub_first_wave.py app/services/source_quality_report.py app/services/source_adapter_template.py app/services/source_profiles.py app/services/source_task_runner.py app/api/v1/dev_material_hub.py app/api/v1/admin_material_hub.py app/schemas/material_hub_contracts.py tests/test_material_hub_first_wave_sources.py tests/test_source_quality_report.py tests/test_source_adapter_template.py

python -m pytest tests/test_material_hub_first_wave_sources.py tests/test_source_adapter_template.py tests/test_source_quality_report.py tests/test_source_profiles.py tests/test_source_task_parameters.py tests/test_supplier_price_standard.py tests/test_batch_moderation.py tests/test_safe_automation_policy.py tests/test_material_hub_pipeline_guard.py
```

Последний результат:

```text
39 passed, 1 warning
```

Warning относится к существующему `app/config.py` / Pydantic class-based config и не связан с Module 01 v1.7.

## Риски

```text
1. Для большинства источников первой волны нужен ручной baseUrl verification.
2. SourceAdapter template готов, но конкретные selectors/testUrls по источникам еще нужно заполнять.
3. QualityReport пока агрегирует доступные данные SourceTask; для production SLA потребуются дополнительные метрики parser latency / HTTP status / retry stats.
4. Batch moderation подготовлен сервисно; полноценный UI массового подтверждения еще нужен.
5. RuleMemory хранит расширенный scope в attributes_json без новой migration. Это безопасно для текущего этапа, но позже может потребоваться отдельная структура для аналитики правил.
6. Документный dedupe подготовлен, но hash/checksum зависит от фактического получения файла.
7. Перевод trustLevel из TEST в NORMAL/TRUSTED должен оставаться ручным решением модератора после QualityReport.
```

## Что не трогалось

```text
Главный Dashboard;
Module 03 Users/Roles/Admin UI;
Module 08 Partner Portal / cabinet context;
Module 04 Works Costs;
Module 05 Estimate Engine;
Module 06 Estimate Audit;
Module 07 Digital House;
Module 09 Procurement;
Module 10 Marketplace;
Module 11 Analytics;
Module 12 AI Assistant.
```

Module 01 не редактирует registry / dashboard / cabinet logic других модулей. Будущие связи остаются через `moduleCode`, adapter, DTO или TODO.
