# Module 14 — Price Dynamics Legacy Alias

Технический код совместимости: `MODULE_14_PRICE_HISTORY`.

Канонический модуль: `MODULE_11_ANALYTICS`.

Каноническая функция: `PRICE_DYNAMICS`.

Статус: `MERGED` / legacy alias.

## Назначение Документа

Этот файл оставлен как историческая справка и compatibility note. Module 14 больше не является самостоятельным актуальным модулем платформы.

Старые ссылки, права, audit-записи, widget placements и dashboard layouts могут ссылаться на `MODULE_14_PRICE_HISTORY`; такие ссылки должны нормализоваться в:

```text
MODULE_14_PRICE_HISTORY -> MODULE_11_ANALYTICS / PRICE_DYNAMICS
```

## Где Живет Функциональность

Динамика цен, срезы, графики, фильтры и аналитические показатели относятся к Module 11 Analytics.

Фактические данные остаются у модулей-источников:

- `PriceHistory`, материалы, источники и текущие цены: Module 1 Material Hub.
- Аналитические представления, графики и price dynamics widgets: Module 11 Analytics.
- Виджет `price-dynamics`: source/canonical module `MODULE_11_ANALYTICS`, legacy module code `MODULE_14_PRICE_HISTORY`.

## Правила Совместимости

- Старый `moduleCode` нельзя удалить без миграции.
- Старый route `/modules/price-history` должен работать как redirect.
- Registry entry должна оставаться `MERGED`, hidden и недоступной как активный module dashboard entry.
- Права доступа должны применяться к `MODULE_11_ANALYTICS` / `PRICE_DYNAMICS`.
- Audit history должен сохранять исходный legacy module code, если он пришел из старой записи.

## Что Не Делать

- Не развивать Module 14 как новый бизнес-модуль.
- Не добавлять отдельную навигацию, sidebar entry или atom card для Module 14.
- Не хранить бизнес-данные аналитики в legacy alias.
- Не выдавать Module 14 как active/planned модуль.

## История Изменений

- 19.06.2026: создана версия v1.0 как отдельный документ динамики цен.
- 25.06.2026: `MODULE_14_PRICE_HISTORY` объединен с `MODULE_11_ANALYTICS`.
- 05.07.2026: документ переведен в legacy alias note; смысл перенесен в Module 11 Analytics / `PRICE_DYNAMICS`.
