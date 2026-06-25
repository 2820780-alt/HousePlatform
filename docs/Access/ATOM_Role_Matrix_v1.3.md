# ATOM Role Matrix v1.3

Дата фиксации: 25.06.2026

Статус: конституция доступа Module №3 принята для дальнейших спринтов.

## Назначение

Этот документ фиксирует границы Module №3:

```text
Users / Roles / Workspaces / RBAC / Dashboard Access / Widget Access / Module Registry
```

Module №3 является источником правил доступа платформы АТОМ. Он не реализует
бизнес-логику других модулей.

## Граница работ

В рамках Module №3 работаем только с:

- пользователями;
- ролями;
- правами;
- рабочими пространствами;
- доступом к dashboard;
- доступом к виджетам;
- доступом к модулям;
- доступом к действиям;
- registry модулей;
- registry виджетов;
- аудитом доступа и действий.

Другие модули не редактируются без отдельного согласования.

Запрещено создавать функциональность других модулей внутри Module №3.

## Цепочка доступа

Module №3 управляет доступом по цепочке:

```text
User
↓
Role
↓
Permission
↓
Workspace
↓
Dashboard
↓
Widget
↓
Module
↓
Action
```

## PlatformModuleRegistry

`PlatformModuleRegistry` является целевым источником истины о модулях.

Текущие `MODULE_01` ... `MODULE_15` являются стартовыми системными записями, а
не закрытым списком.

Будущие модули добавляются через `PlatformModuleRegistry`.

Module №3 хранит для модуля:

- `moduleId`;
- `moduleCode`;
- `canonicalModuleCode`;
- статус;
- видимость;
- доступность;
- связи с permissions;
- связи с workspaces;
- будущие `featureCode`;
- связи с widget registry.

## WidgetRegistry

Виджеты добавляются через `WidgetRegistry`.

Widget Registry не должен зависеть от визуального номера модуля.

Виджет должен ссылаться на системный идентификатор:

- `moduleId`;
- `moduleCode`;
- `canonicalModuleCode`;
- `featureCode`, если виджет относится к функции внутри модуля.

## Номер модуля

Номер модуля не является источником истины.

Номер модуля используется только для отображения:

- `displayNumber`;
- `legacyNumber`;
- `visualNumber`;
- `displayOrder`.

Системная логика использует:

- `moduleCode`;
- `moduleId`;
- `canonicalModuleCode`.

Правило:

```text
Номер модуля — для человека.
moduleCode / moduleId — для системы.
```

## Жизненный цикл модуля

Модуль может иметь статусы:

- `ACTIVE`;
- `PLANNED`;
- `DRAFT`;
- `MERGED`;
- `ARCHIVED`;
- `DEPRECATED`;
- `DISABLED`.

Модуль может быть merged, archived или deprecated без физического удаления.

Удаление moduleCode без миграции запрещено.

## Alias и merged-модули

Старые `moduleCode` и route должны поддерживаться через:

- alias;
- redirect;
- migration;
- audit record.

Это нужно, чтобы не ломались:

- старые ссылки;
- dashboard layouts;
- widget placements;
- permissions;
- audit history;
- внешние интеграции.

## MODULE_14_PRICE_HISTORY

`MODULE_14_PRICE_HISTORY` должен быть legacy/merged-записью, объединенной с:

```text
MODULE_11_ANALYTICS
```

Целевая связь:

```text
MODULE_14_PRICE_HISTORY -> MODULE_11_ANALYTICS / PRICE_DYNAMICS
```

Правила:

- старый `moduleCode` нельзя удалить;
- старый route должен поддерживаться через alias или redirect;
- старые виджеты должны мигрировать без потери пользовательских настроек;
- права доступа должны быть переназначены на `canonicalModuleCode`;
- `AuditLog` должен сохранить историю объединения.

## Planned-модули

Будущие модули сначала создаются только как записи в `PlatformModuleRegistry`
со статусом `PLANNED` или `DRAFT`.

Planned/draft-модули не должны быть доступны обычным пользователям как готовый
функционал.

Module №3 не реализует их бизнес-логику.

## Региональное правило

Платформа должна быть multi-region-ready.

Первый MVP использует пилотный регион:

- Краснодарский край.

Краснодарский край должен быть стартовой записью в справочнике регионов, а не
условием в коде.

Запрещено:

```text
region = "Краснодарский край"
```

Правильно использовать:

- `region_id`;
- `city_id`;
- `delivery_zone_id`;
- `price_region_id`;
- `source_region_id`;
- `supplier_region_id`;
- `work_region_id`.

## Auth-ready правило

Авторизация может отсутствовать в текущем тестовом режиме.

При этом все новые экраны, API и модули должны быть auth-ready.

Запрещено писать новую логику через прямую проверку:

```text
role === "admin"
```

Нужны adapter/guard-слои для:

- пользователя;
- роли;
- permissions;
- workspace;
- региона;
- доступных модулей;
- доступных виджетов;
- доступных действий.

## Главное правило безопасности

```text
Скрыть кнопку недостаточно.
Все API должны проверять Permission на сервере.
```

UI может скрывать недоступные действия, но не является механизмом безопасности.

## Что нельзя делать

- редактировать Module №1 Material Hub в рамках Module №3;
- редактировать Module №2 Technology Knowledge Hub в рамках Module №3;
- редактировать Module №11 Analytics в рамках Module №3;
- переписывать главный Dashboard из Module №3;
- переписывать бизнес-логику других модулей;
- делать Dashboard источником истины о модулях;
- делать Widget Registry зависимым от визуального номера модуля;
- делать RBAC зависимым от визуального номера модуля;
- считать список `MODULE_01` ... `MODULE_15` окончательным;
- реализовывать будущие модули раньше времени;
- делать planned/draft-модули доступными обычным пользователям.

## Результат

Этот документ является конституцией доступа Module №3.

Все дальнейшие спринты Module №3, Dashboard и новых модулей должны учитывать:

- `PlatformModuleRegistry`;
- `WidgetRegistry`;
- `moduleCode` / `moduleId`;
- `canonicalModuleCode`;
- alias / merged / archived / deprecated жизненный цикл;
- multi-region-ready подход;
- auth-ready adapter/guard;
- серверную проверку `Permission`.
