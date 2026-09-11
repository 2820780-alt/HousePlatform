# Module №1 — Work Catalog Reference Pack

Статус: M1-WC-1 реализован; пакет используется как документационная карта для реализованных M1-WC-1…M1-WC-4.

## Runtime source of truth

Рабочий каталог загружается из:

`src/modules/module1/seeds/work_catalog_seed.json`

Его runtime-контракт и валидация находятся в:

`app/services/module1_work_catalog.py`

## Документы пакета

- `work_catalog_reference.md` — человекочитаемое представление каталога.
- `work_catalog_schema.json` — reference JSON Schema для seed.
- `work_catalog_module_links.md` — точное представление Module №2/№5 hints.
- `provider_work_cost_contract.md` — текущий persistent/API/export contract стоимости работ.
- `work_cost_test_cases.md` — карта специализированных проверок.
- `M1_WC_1_Codex_Prompt.md` — исторический prompt реализации, не source of truth.

## Проверенная статистика

- Групп работ: 24.
- Работ: 209.
- Единиц: 14.
- Все 209 строк `work_catalog_reference.md` совпадают с seed по коду, имени, unit, range, applies_to и Module №2/№5 hints.
- Все 209 строк `work_catalog_module_links.md` совпадают с seed по обоим hints.

## Границы

- В seed нет цен, исполнителей и контактов.
- Work Catalog не является DB-таблицей и не содержит Provider Work Cost Offers.
- Стоимость работ не парсится и не ищется на сайтах.
- Исполнитель вводит стоимость отдельно через `ProviderWorkCostOffer`.
- Module №1 формирует export preview для Module №5, но не считает смету и не выбирает предложение.
- Market sanity signal остается отдельным этапом M1-WC-5.
