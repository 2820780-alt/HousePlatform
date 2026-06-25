# Module 03 Sprint 2.1. Planned-модули будущей платформы

Дата фиксации: 25.06.2026

Статус: planned-записи добавлены без реализации бизнес-логики.

## Цель

Зарегистрировать будущие крупные модули платформы АТОМ в
`PlatformModuleRegistry` как planned/draft-записи.

Эти модули пока не реализуются.

Они нужны, чтобы:

- Dashboard не пришлось переделывать позже;
- WidgetRegistry мог ссылаться на будущие виджеты;
- RBAC был готов к будущим правам;
- UserDashboardLayout не ломался при добавлении новых модулей;
- архитектура платформы заранее понимала будущую карту модулей.

## Правило planned-модулей

Для новых planned-записей:

```text
status = PLANNED
isActive = false
isVisibleInSidebar = false
isVisibleOnDashboard = false
isVisibleOnAtomMap = false
isAvailableForWidgets = false
```

Planned-модули не доступны обычным пользователям как готовый функционал.

## Добавленные planned-коды

- `MODULE_05_ESTIMATE_ENGINE`;
- `MODULE_07_DIGITAL_HOUSE`;
- `MODULE_08_PARTNER_PORTAL`;
- `MODULE_09_PROCUREMENT`;
- `MODULE_13_PROJECT_COLLABORATION`;
- `MODULE_14_CONSTRUCTOR_LITE`;
- `MODULE_15_CONTRACTS`;
- `MODULE_16_LOGISTICS_DELIVERY`;
- `MODULE_17_FINANCE_PAYMENTS`;
- `MODULE_18_QUALITY_CONTROL`.

## Существующие активные коды

Некоторые коды из новой карты уже существуют как активные системные модули:

- `MODULE_04_WORKS_COSTS`;
- `MODULE_06_ESTIMATE_AUDIT`;
- `MODULE_10_MARKETPLACE`;
- `MODULE_12_AI_ASSISTANT`.

Они не переводятся в `PLANNED`, потому что уже зарегистрированы как системные
записи. Понижение статуса или переименование требует отдельной миграции и
решения.

## Важное правило

Номер модуля не является источником истины.

Если существующий `moduleCode` уже есть в проекте, его нельзя переименовывать
или менять без миграции.

## Ограничения

В этом спринте не выполняется:

- реализация planned-модулей;
- открытие planned-модулей в sidebar/dashboard/atom map;
- подключение planned-виджетов;
- миграция старых route;
- изменение бизнес-логики других модулей.
