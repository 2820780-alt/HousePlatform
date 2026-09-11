# NEW CHAT HANDOFF — АТОМ / Module №1 current state

> Состояние синхронизировано 11.09.2026 по итогам M1-WC-6 / final QA.
> Этот файл является текущей рабочей картой Module №1. Исторические readiness/release
> отчеты сохраняют смысл своих исходных срезов и не заменяют эту карту.

## Главное

Проект АТОМ — модульная строительная платформа для строительства частного дома и ремонта квартиры.

Основная цепочка:

```text
Module №7 / объект
→ Module №2 / технологии и количество
→ Module №1 / материалы, цены, документы, стоимость работ
→ Module №5 / смета
```

## Конституция проекта

Файлы-источники истины:

- `docs/Master_Prompt_v1.1.md`
- `docs/Master_Prompt_v1.0.md`
- `docs/Decisions.md`
- `docs/Modules/ATOM_USER_QUICK_ACTIONS_v1.0.md`
- `docs/Access/ATOM_Role_Matrix_v1.3.md`

Не создавать новые lock-документы, если правка должна быть решением в `docs/Decisions.md`.

## Быстрые действия

Quick Actions уже реализованы.

Нельзя:
- переопределять Quick Actions;
- называть их просто безопасной навигацией;
- заменять быстрыми переходами;
- смешивать с Widgets;
- создавать второй механизм.

Перед изменением читать `docs/Modules/ATOM_USER_QUICK_ACTIONS_v1.0.md`.

## Module №1 — актуальная логика

Module №1 отвечает за:

- материалы / товары;
- цены материалов;
- где купить;
- характеристики;
- расход;
- упаковку;
- документы и техданные;
- источники и анализатор;
- нормализованный справочник работ;
- стоимость работ от исполнителей;
- качество и модерацию;
- export packages для Module №2/№5/№11.

Материалы = товары.

Материал без цены не интересен как готовая единица и не готов к смете. Исключение: уточнение характеристик существующего материала.

## Анализатор

Источники анализатора:

1. сайт;
2. ручной ввод из файла.

Анализатор не ищет источники сам.

Анализатор извлекает:
- материалы;
- цену материала;
- характеристики;
- расход;
- упаковку;
- где купить;
- поставщика;
- производителя;
- документы;
- инструкции;
- технические листы;
- типовые узлы;
- альбомы решений;
- технические ограничения.

Анализатор не работает со стоимостью работ.

## Стоимость работ

Стоимость работ — отдельный раздел Module №1.

Стоимость работ:
- не ищется на сайтах;
- не парсится;
- не собирается анализатором.

Источник данных — ручной ввод исполнителя / подрядчика через текущий `ProviderWorkCostOffer` API/workspace. Отдельный личный кабинет исполнителя остается будущим UI-контуром.

Исполнитель выбирает работу из нормализованного справочника и вводит цену.

Цена может быть:
- fixed;
- range.

Таблица:
- Вид работ
- Наименование работы
- Стоимость
- Единица измерения
- Исполнитель
- Контакты
- Регион
- Статус проверки
- Дата обновления

Market Sanity Signal реализован как derived advisory check:

- LOW_OUTLIER;
- HIGH_OUTLIER;
- WITHIN_COMPARABLE_RANGE;
- INSUFFICIENT_DATA;
- REVIEW.

Сигнал использует exact cohort work_code + pricing_unit + currency + region,
минимум пять независимых peer-провайдеров и median + Tukey/IQR. Он не
сохраняется, не меняет offer и не является аналитикой Module №11.

## Module №1 tabs

Актуальные верхние вкладки:

1. Обзор
2. Материалы
3. Документы и техданные
4. Стоимость работ
5. Источники и анализатор
6. Модерация и качество

Не делать верхними вкладками:
- Эталонные материалы
- Экспортные пакеты
- Лаборатория извлечения
- Поставщики
- Производители работ
- Участники
- Наблюдения цен

## Что уже сделано технически

Выполнены M1-1 … M1-24 service/backend foundations:

- legacy compatibility skeleton
- material seed registry
- characteristic schema registry
- unit conversion registry
- extraction blueprint registry
- source profile registry
- raw ingestion pipeline
- material normalizer
- matching/dedup
- moderation core
- canonical material store compatibility
- technical profile packaging
- material roles
- alternatives/analogs
- compatibility matrix
- documents/evidence
- participants directory
- price/work observations
- data quality dashboard
- extraction workbench
- export packages
- golden materials
- UI preview
- final regression

Work Cost foundation и entry/export layers:

- M1-WC-0 — Work Cost Architecture Lock выполнен
- M1-WC-1 — Normalized Work Catalog Seed выполнен
- M1-WC-2 — Provider Work Cost Entry Layer выполнен
- M1-WC-3 — Split Material Prices and Work Costs выполнен структурно
- M1-WC-4 — Work Cost Export Hints for Module №5 выполнен
- M1-WC-5 — Provider Work Cost Market Sanity Signal выполнен

Текущий final QA gate Module №1: COMPLETED.

Финальный прогон выполнен на штатном HousePlatform Docker Compose контуре:

- `web`, `db` и `redis` healthy;
- два DB-dependent production-readiness теста: 2 passed;
- `tests/test_module1_final_regression.py`: 11 passed;
- `tests/test_module1_work_cost_market_sanity.py`: 39 passed;
- полный regression: 1425 passed, 2 deselected, 30 warnings;
- UI smoke: все вкладки Material Hub вернули HTTP 200;
- live UI evidence: 31 документ, 209 работ Work Catalog, 0 work cost offers;
- пустой `ProviderWorkCostOffer` не ломает UI и отображается штатным empty state.

Полный regression классифицирован как `FULL_REGRESSION_WITH_POLICY_EXCLUSIONS`.
Исключены только два теста, которые по политике требуют чтения локальных
credential/config values:

- `tests/test_platform_security_gate.py::test_safe_docker_example_contains_placeholders_not_local_secrets`;
- `tests/test_platform_security_gate.py::test_packaged_config_uses_noncredential_development_placeholders`.

Контрольные live DB counts до и после regression совпали: materials 394,
catalog_products 441, material_documents 31, price_history 188,
supplier_prices 1, material_quality_issues 26, sources 28, source_tasks 55,
provider_work_cost_offers 0. Миграции, seeds, import и parsing не запускались.

Final regression boundary различает:

- READ_ONLY;
- PERSISTENCE;
- EXPORT_PACKAGE;
- INGESTION_CANONICAL.

Разрешенные persistence-сервисы ограничены явными model/session/mutation
allowlists; cross-module writes и смешение Material Price / Work Cost запрещены.

Финальные локальные commits:

- `b40b470` — `chore(docker): harden HousePlatform test image`;
- `8f1d797` — `fix(module1): keep fastener consumption out of material data`;
- `796a63d` — `test(module1): enforce final module boundaries`;
- `b1d73cc` — `feat(module1): add provider work cost market sanity`.

Не добавлять в staging все рабочее дерево одной командой.

## Следующие плановые работы

1. Считать Module №1 завершенным и не расширять его contract без отдельного
   архитектурного решения.
2. Начинать Module №2 отдельным прогоном с чтения этого handoff и
   `work_catalog_module_links.md`.
3. Использовать только зафиксированный ниже read-only M1 → M2 contract; не
   дублировать ownership данных Module №1.

## FINAL MODULE 1 → MODULE 2 CONTRACT

1. **Что гарантирует Module №1.** Canonical material identity, classification,
   normalized characteristics, technical profile, units/conversion hints,
   provenance, quality/readiness and evidence remain owned by Module №1.

2. **Что доступно Module №2.** Существующий Module2TechnologyInputPackage
   содержит clean_material, technical_profile, material-role, compatibility,
   alternative and unit conversion hints, а также missing_fields и blockers.
   Документы и evidence доступны через Module №1 document package; Module №2
   хранит ссылки, а не дубликаты первичных документов.

3. **Blockers.** Contract может вернуть missing_identity,
   missing_technical_fields, pending_moderation, low_quality, а также
   конкретные missing required fields technical profile.

4. **Incomplete material.** Материал incomplete, если identity, обязательные
   technical fields, положительная price observation, moderation или quality
   gate не позволяют downstream readiness. Он остается canonical/evidence data,
   но не должен молча использоваться для инженерного расчета.

5. **Что рассчитывает Module №2.** Technology, ConstructionSystem,
   ConstructionNode, Layer, технологические нормы расхода, WorkStep sequence,
   количества и инженерную применимость к параметрам объекта.

6. **Что Module №2 не дублирует.** Canonical materials, aliases,
   manufacturers/suppliers, primary documents, source provenance, material
   prices, ProviderWorkCostOffer, Work Catalog и Module №1 quality signals.

7. **Готовые contracts.** build_module2_technology_input_package, technical
   profile packaging, compatibility/alternatives/material-role/unit hints,
   document/evidence package и read-only export validation.

8. **Foundation boundary.** Эти contracts подготавливают входные данные и
   blockers, но no_calculation_result=true: полноценный Module №2 engine еще
   не реализован и в этом прогоне не начинался.

## Запреты

Не трогать без отдельного решения:
- Quick Actions
- Dashboard
- Module №2
- Module №3
- Module №5
- Module №11
- ORM/migrations
- source adapters
- парсинг стоимости работ
- анализатор стоимости работ
