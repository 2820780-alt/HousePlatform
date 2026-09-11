# Provider Work Cost Offer Contract — Module №1

Статус: persistent offer реализован в M1-WC-2; export preview для Module №5 — в M1-WC-4; derived Market Sanity Signal — в M1-WC-5.

## Назначение

`ProviderWorkCostOffer` — отдельное редактируемое предложение стоимости работы от исполнителя. Оно принадлежит Module №1 и связано со стабильным `work_code` из нормализованного Work Catalog.

Стоимость работ:

- не является ценой материала;
- не хранится в `Material`, `CatalogProduct`, `SupplierPrice` или `PriceHistory`;
- не создается анализатором, parser, source adapter или ingestion pipeline;
- не является строкой сметы;
- не запускает Module №2 или Module №5;
- не выбирает лучшего исполнителя и не рассчитывает итоговую стоимость.

Принятые продуктовые и архитектурные границы закреплены в решениях №032 и №033 файла `docs/Decisions.md`.

## Persistent model

Таблица: `provider_work_cost_offers`.

Основные поля:

- `id`;
- `work_code`;
- `owner_user_id`;
- `region`;
- `pricing_mode`;
- `fixed_amount` или `minimum_amount` / `maximum_amount`;
- `currency`;
- `pricing_unit`;
- `valid_from` / `valid_until`;
- `status`;
- `comment`;
- `created_by` / `updated_by`;
- `created_at` / `updated_at`.

Владелец определяется сервером по текущему пользователю. Контакты и отображаемое имя не дублируются внутри предложения: `owner_user_id` связан с `User`, а `ownerDisplayName` формируется при чтении.

Поля `provider`, `contacts`, `city`, `verification_status`, `included` и `excluded` не входят в текущую persistent-модель.

## API payload

```json
{
  "workCode": "wall_finishing_shtukaturka_sten_gipsovaya",
  "region": "Краснодарский край",
  "pricingMode": "range",
  "pricingUnit": "m2",
  "currency": "RUB",
  "fixedAmount": null,
  "minimumAmount": 450,
  "maximumAmount": 650,
  "validFrom": "2026-09-01",
  "validUntil": "2026-12-31",
  "status": "draft",
  "comment": "Цена зависит от толщины слоя и геометрии стен."
}
```

`ownerUserId`, timestamps, display labels и права редактирования являются server-side/read-model полями и не принимаются из create/update payload.

## Pricing modes

### fixed

- `pricingMode = fixed`;
- `fixedAmount > 0`;
- `minimumAmount` и `maximumAmount` пусты.

### range

- `pricingMode = range`;
- выбранная работа разрешает диапазон;
- `minimumAmount > 0`;
- `maximumAmount > 0`;
- `maximumAmount >= minimumAmount`;
- `fixedAmount` пуст.

`pricingUnit` должен входить в `allowed_units` выбранной работы. Текущая поддерживаемая валюта — `RUB`. Если заданы обе даты, `validUntil >= validFrom`.

## Statuses

Текущая persistent-модель поддерживает:

- `draft`;
- `active`;
- `inactive`.

Деактивация переводит предложение в `inactive`; физическое удаление API не предоставляет. Статусы `pending`, `verified`, `rejected` и `archived` в текущую модель не входят.

## Market Sanity Signal

marketSanity — производный advisory-сигнал о сопоставимости предложения с уже известными Module №1 предложениями. Это не утверждение о «правильной рыночной цене», не автоматическая модерация и не аналитика Module №11.

Сигнал рассчитывается при чтении списка и не сохраняется в provider_work_cost_offers. Расчет не меняет сумму, диапазон, статус, сроки или другие поля предложения и не выполняет DB write.

Точная сопоставимая группа требует совпадения:

- work_code;
- канонического pricing_unit;
- currency;
- region.

Конвертация валют и единиц, fuzzy region matching и Material Price records не используются. Peer-предложение должно иметь status=active и быть действительно на asOf: future, expired, draft и inactive records исключаются.

Минимум — MIN_COMPARABLE_OFFERS = 5 независимых peer-провайдеров. Target offer и остальные предложения его владельца не входят в reference set. Если у другого владельца несколько актуальных записей в одной группе, используется одна: наиболее поздняя по updated_at, затем created_at, valid_from и id.

Для fixed offer representative value равно fixed_amount; для range — Decimal midpoint (minimum_amount + maximum_amount) / 2. Reference band строится по медиане, Tukey Q1/Q3 и fences Q1 - 1.5*IQR / Q3 + 1.5*IQR.

Статусы:

- INSUFFICIENT_DATA — меньше пяти независимых peer-предложений;
- WITHIN_COMPARABLE_RANGE — fixed value или target range пересекает reference band;
- LOW_OUTLIER — target value/range полностью ниже lower fence;
- HIGH_OUTLIER — target value/range полностью выше upper fence;
- REVIEW — объективная неоднозначность, включая отклонение при IQR=0, или некорректная target amount structure.

При IQR=0 target, включающий единственное устойчивое значение, получает WITHIN_COMPARABLE_RANGE; любое иное значение получает REVIEW, а не ложную outlier-точность.

Read-model поля:

- status / statusLabel;
- comparableOfferCount;
- reason / explanation;
- asOf;
- referenceStats: median, q1, q3, lowerBound, upperBound, когда выборка достаточна.

Список API и Work Cost workspace получают результаты пакетно: один дополнительный cohort query на набор target offers, без N+1. Single-offer create/get/update/deactivate responses сохраняют marketSanity optional и не запускают скрытый расчет.

## RBAC and ownership

- Module №1 `ADMIN/GLOBAL` или `APPROVE/GLOBAL` может работать с предложениями глобально.
- Пользователь с Module №4 `CREATE/OWN` или `EDIT/OWN` работает только со своими предложениями.
- Клиент не может подменить `owner_user_id`.
- List/get/update/deactivate применяют server-side permission и ownership checks.

## API

Базовый маршрут: `/api/v1/admin/material-hub/work-cost-offers`.

- `POST /` — создать;
- `GET /` — список с owner/region/status/pricing filters;
- `GET /work-catalog` — варианты из нормализованного каталога;
- `GET /export-preview` — read-only export preview;
- `GET /{offer_id}` — получить;
- `PUT /{offer_id}` — обновить;
- `POST /{offer_id}/deactivate` — деактивировать.

## Module №5 export

Export contract: `module1.work_cost_offer_export.v1`.

Module №1 передает только eligible records и явно фиксирует:

- `source_module = MODULE_01_MATERIAL_HUB`;
- `consumer = MODULE_05_ESTIMATES_PREVIEW`;
- `no_estimate_total = true`;
- `no_selected_offer = true`.

Module №1 не создает сметные сущности Module №5. Market Sanity Signal не входит в export contract, не выбирает предложение и не рассчитывает смету.

## Source of truth

При расхождениях приоритет имеют:

1. `docs/Decisions.md`, решения №032 и №033;
2. ORM model и migration `20260717_module01_provider_work_cost_offers.sql`;
3. API schemas и `app/services/module1_provider_work_cost_offers.py`;
4. `app/services/module1_work_cost_export_contract.py`;
5. специализированные tests.
