# Module 03 Sprint 2. Seed стартовых системных модулей

Дата фиксации: 25.06.2026

Статус: seed-миграция подготовлена и применена.

## Цель

Зарегистрировать стартовые системные модули в `PlatformModuleRegistry`.

## Зарегистрированные модули

- `MODULE_01_MATERIAL_HUB`;
- `MODULE_02_KNOWLEDGE_BASE`;
- `MODULE_03_USERS_ROLES`;
- `MODULE_04_WORKS_COSTS`;
- `MODULE_05_ESTIMATES`;
- `MODULE_06_ESTIMATE_AUDIT`;
- `MODULE_07_DIGITAL_OBJECT`;
- `MODULE_08_PROCUREMENT`;
- `MODULE_09_TENDERS`;
- `MODULE_10_MARKETPLACE`;
- `MODULE_11_ANALYTICS`;
- `MODULE_12_AI_ASSISTANT`;
- `MODULE_13_AUDIT`;
- `MODULE_14_PRICE_HISTORY`;
- `MODULE_15_CONSTRUCTION_GROUPS`.

## Правило для активных системных модулей

Для большинства стартовых модулей:

```text
isSystem = true
isActive = true
status = ACTIVE
```

## MODULE_14_PRICE_HISTORY

`MODULE_14_PRICE_HISTORY` зарегистрирован как legacy/merged-запись:

```text
moduleCode = MODULE_14_PRICE_HISTORY
canonicalModuleCode = MODULE_11_ANALYTICS
mergedIntoModuleCode = MODULE_11_ANALYTICS
featureCodes = PRICE_DYNAMICS
status = MERGED
isActive = false
```

Модуль не показывается как отдельный активный модуль, но остается в registry
для совместимости:

- старых ссылок;
- старых dashboard layouts;
- старых widget placements;
- permission migration;
- audit history.

## Ограничения

В этом спринте не выполняется:

- переписывание Dashboard на чтение registry;
- миграция `module_number` связей;
- создание UI управления модулями;
- реализация planned-модулей будущей платформы.

## Результат

Текущие модули существуют как данные в `PlatformModuleRegistry`, а не как
закрытый enum.
