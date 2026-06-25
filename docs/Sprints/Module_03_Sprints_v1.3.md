# Module 03 Sprints v1.3

Дата фиксации: 25.06.2026

Статус: правила будущих спринтов зафиксированы.

## Область работы

Работать строго в рамках:

```text
Module №3 — Users / Roles / Workspaces / RBAC / Dashboard Access / Widget Access / Module Registry
```

Module №3 управляет доступом:

```text
User
↓
Role
↓
Permissions
↓
Workspace
↓
Dashboard
↓
Widgets
↓
Modules
```

## Региональное правило

Платформа АТОМ должна быть multi-region-ready.

Первый MVP запускается в пилотном регионе:

- Краснодарский край.

Запрещено хардкодить Краснодарский край в бизнес-логике.

Неправильно:

```text
region = "Краснодарский край"
```

Правильно использовать идентификаторы:

- `region_id`;
- `city_id`;
- `delivery_zone_id`;
- `price_region_id`;
- `source_region_id`;
- `supplier_region_id`;
- `work_region_id`.

Краснодарский край должен быть стартовой записью в справочнике регионов, а не
условием в коде.

## Главное правило модулей

Номер модуля — только для человека.

Для системы используются:

- `moduleCode`;
- `moduleId`;
- `canonicalModuleCode`;
- `PlatformModuleRegistry`;
- `WidgetRegistry`;
- `Permission`;
- `UserDashboardLayout`.

Номер модуля может использоваться как:

- `displayNumber`;
- `legacyNumber`;
- `visualNumber`;
- `displayOrder`.

## Запрещено в Module №3

- редактировать Module №1 Material Hub;
- редактировать Module №2 Technology Knowledge Hub;
- редактировать Module №11 Analytics;
- переписывать главный Dashboard;
- переписывать бизнес-логику других модулей;
- создавать функциональность других модулей внутри Module №3;
- делать Dashboard источником истины о модулях;
- делать Widget Registry зависимым от визуального номера модуля;
- делать RBAC зависимым от визуального номера модуля;
- считать список `MODULE_01` ... `MODULE_15` окончательным;
- реализовывать будущие модули раньше времени;
- создавать бизнес-логику будущих модулей внутри Module №3;
- делать planned/draft-модули доступными обычным пользователям.

## Безопасность

```text
Скрыть кнопку недостаточно.
Все API должны проверять Permission на сервере.
```

Прямые проверки вида `role === "admin"` запрещаются для новой логики после
auth-ready sprint. Проверка должна идти через adapter/guard.

## PlatformModuleRegistry

Было неправильно:

```text
PlatformModule enum = закрытый список модулей
```

Целевая архитектура:

```text
PlatformModuleRegistry = источник истины
PlatformModule constants = удобство для стартовых системных модулей
```

Стартовые системные модули не являются закрытым списком.

Будущие модули должны добавляться без переработки RBAC.

## Planned-модули

Будущие модули сначала появляются как записи в `PlatformModuleRegistry` со
статусом:

- `PLANNED`;
- `DRAFT`.

Module №3 не реализует бизнес-логику будущих модулей. Он готовит:

- `moduleCode`;
- статус модуля;
- видимость;
- доступность;
- связи с permissions;
- будущие `featureCode`;
- возможность подключения виджетов через `WidgetRegistry`.

Обязательные planned-модули:

- `MODULE_04_WORKS_COSTS`;
- `MODULE_16_QUALITY_CONTROL`;
- `MODULE_17_SITE_SUPERVISION`;
- `MODULE_18_WARRANTY_SERVICE`;
- `MODULE_19_EQUIPMENT_RENTAL`;
- `MODULE_20_FINANCE_ACCOUNTING`.

## Module 14 как alias Analytics

Module №14 "История / динамика цен" в целевой архитектуре объединяется с:

```text
MODULE_11_ANALYTICS
```

Как legacy/alias/merged-запись:

```text
MODULE_14_PRICE_HISTORY -> MODULE_11_ANALYTICS / PRICE_DYNAMICS
```

Правила миграции:

- старый `moduleCode` нельзя просто удалить;
- старые ссылки не должны ломаться;
- старые виджеты не должны исчезать без миграции;
- пользовательские dashboard layouts не должны ломаться;
- права доступа должны быть переназначены на `canonicalModuleCode`;
- `AuditLog` должен сохранить историю объединения.

## Порядок спринтов Module №3

### Sprint 1. PlatformModuleRegistry

Создать registry модулей как источник истины для Module №3.

### Sprint 1.1. PlatformRegionRegistry и пилотный регион

Создать registry регионов и seed пилотного региона Краснодарский край.

### Sprint 1.2. Auth-ready режим без реальной авторизации

Подготовить mock/current user adapter и guard-слой без включения полноценной
авторизации.

### Sprint 2. Seed стартовых модулей

Добавить стартовые системные модули как записи registry.

### Sprint 2.1. Planned-модули будущей платформы

Добавить planned/draft-модули, включая `MODULE_04_WORKS_COSTS`.

### Sprint 3. Module constants

Добавить constants для удобства стартовых модулей без превращения их в закрытый
enum.

## Dashboard-зависимости

В Dashboard правило начнет полноценно действовать после:

- Dashboard Sprint 8: `currentUserProfileMock`;
- Dashboard Sprint 8.1: auth-ready adapter Dashboard;
- Dashboard Sprint 9: гибкая нумерация модулей;
- Dashboard Sprint 9.1: planned-модули будущей платформы.

После этих спринтов нельзя писать новую логику через `moduleNumber`,
hardcoded region или прямой `role === "admin"` без adapter/guard.
