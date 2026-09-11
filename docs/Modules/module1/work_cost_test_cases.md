# Work Cost Test Cases — Module №1

Этот файл описывает текущие M1-WC-1…M1-WC-5 проверки. Имена полей соответствуют API schemas и persistent-модели `ProviderWorkCostOffer`.

## Work Catalog

| Сценарий | Ожидаемый результат |
|---|---|
| Seed загружается | version `1.0`, 24 группы, 209 работ, 14 единиц |
| Все `work_code` уникальны | valid |
| `default_unit` входит в `allowed_units` | valid |
| `applies_to` только `private_house`, `apartment`, `both` | valid |
| Неизвестная группа или единица | invalid |
| В seed добавлены price/provider/contact fields | invalid |
| Service импортирует ORM или создает цены | invalid |

Основной test file: `tests/test_module1_work_catalog.py`.

## Provider Work Cost persistence

| Сценарий | Вход | Ожидаемый результат |
|---|---|---|
| Fixed valid | `pricingMode=fixed`, `fixedAmount>0` | valid |
| Fixed без суммы | `fixedAmount=null` | invalid |
| Fixed с range fields | `minimumAmount`/`maximumAmount` заполнены | invalid |
| Range valid | положительные min/max, `minimumAmount <= maximumAmount` | valid |
| Range запрещен работой | `is_range_allowed=false` | invalid |
| Unknown work code | отсутствует в Work Catalog | invalid |
| Unit не разрешен | `pricingUnit` отсутствует в `allowed_units` | invalid |
| Unsupported currency | не `RUB` | invalid |
| Missing region | пустое значение | invalid |
| Invalid validity | `validUntil < validFrom` | invalid |
| Invalid status | не `draft/active/inactive` | invalid |
| Ordinary user create | нет Work Cost permission | forbidden |
| Update чужого offer | нет global permission | forbidden |
| Deactivate | owner/admin переводит offer в `inactive` | valid |
| Client подменяет owner | owner берется из server-side user | невозможно через API payload |

Основные test files:

- `tests/test_module1_work_cost_persistence.py`;
- `tests/test_module1_work_cost_service.py`;
- `tests/test_module1_work_cost_workspace.py`.

## Separation from Material Price

- `ProviderWorkCostOffer` хранится в отдельной таблице.
- Work Cost service не создает `Material`, `CatalogProduct`, `SupplierPrice`, `PriceHistory` или `MaterialMatchCandidate`.
- Work Cost widget читает material prices и work costs раздельно.
- Source adapters, analyzer и RawIngestionItem не создают Work Cost.

## Export contract

- В export попадают только eligible active records.
- Draft, inactive, expired и некорректные records получают причины исключения.
- Export не выбирает лучшее предложение.
- Export не рассчитывает estimate total.
- Export не создает сущности Module №5.
- Owner scope и RBAC сохраняются при чтении.

Основной test file: `tests/test_module1_work_cost_export_contract.py`.

## UI and widgets

- Work Cost workspace использует текущий API и Work Catalog options.
- Widget не смешивает material price с Provider Work Cost.
- Provider query ограничивается owner scope для исполнителя.
- Пользовательские widget settings не могут подменять permissions/owner.

Основной test file: `tests/test_module1_operational_widgets.py`.

## Market Sanity Signal

| Сценарий | Ожидаемый результат |
|---|---|
| Нет peer offers | INSUFFICIENT_DATA, count=0 |
| От 1 до 4 peers | INSUFFICIENT_DATA с точным count |
| 5+ normal peers | строятся median, Q1/Q3 и Tukey fences |
| Fixed target полностью ниже lower fence | LOW_OUTLIER |
| Fixed target полностью выше upper fence | HIGH_OUTLIER |
| Другой work_code | record исключен |
| Другая pricing_unit | record исключен |
| Другая currency | record исключен |
| Другой region | record исключен |
| Draft peer | record исключен |
| Inactive peer | record исключен |
| Expired peer | record исключен |
| Future peer | record исключен |
| Target присутствует в candidate set | target исключен |
| Другая запись target owner | не считается независимым peer |
| Несколько актуальных offers одного owner | один latest/effective representative |
| Fixed peer | representative = fixed_amount |
| Range peer | representative = Decimal midpoint |
| Target range полностью ниже band | LOW_OUTLIER |
| Target range полностью выше band | HIGH_OUTLIER |
| Target range пересекает band | WITHIN_COMPARABLE_RANGE |
| IQR=0 и target включает median | WITHIN_COMPARABLE_RANGE |
| IQR=0 и target отличается | REVIEW |
| Decimal fractional amounts | расчет без float rounding |
| Target после расчета | ни одно поле не изменено |
| Material Price record среди candidates | не считается Work Cost peer |
| Достаточная reference group, invalid target amount | REVIEW |
| Serialization | status, count, reason, explanation, asOf и safe reference stats |
| Несколько targets/cohorts | один batch read-query, без N+1 |
| Пустой target batch | DB query не выполняется |
| Query-only DB double | add/flush/commit не вызываются |
| Work Cost UI | показывает компактный optional signal без автоматических действий |

Основной test file: tests/test_module1_work_cost_market_sanity.py.

Полноценная рыночная аналитика, conversion, fuzzy matching, price recommendation и автоматический выбор предложения остаются вне Module №1 и относятся к Module №11 / профильным consumer-модулям.
