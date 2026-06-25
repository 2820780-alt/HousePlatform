# Module 03 Sprint 6. ModuleActionRegistry

Дата фиксации: 26.06.2026

Статус: registry действий модулей добавлен.

## Цель

Разрешить каждому модулю иметь свой набор действий без переписывания ядра RBAC.

## Реализовано

Добавлена модель:

- `ModuleActionRegistry`.

Добавлена таблица:

- `module_action_registry`.

## Модель

```text
id
moduleCode
actionCode
title
description
isSystem
isActive
```

## Базовые действия

Для активных системных модулей добавляются:

- `VIEW`;
- `CREATE`;
- `EDIT`;
- `APPROVE`;
- `ADMIN`.

## Будущие действия

Будущие модули смогут добавлять собственные actions:

- `PUBLISH`;
- `IMPORT`;
- `EXPORT`;
- `ASSIGN`;
- `CANCEL`;
- `ARCHIVE`;
- `RUN_ANALYSIS`;
- `MANAGE_OWN`;
- `INVITE`;
- `MODERATE`;
- `CONFIGURE`.

Эти действия не добавляются всем модулям автоматически. Их должен объявлять
конкретный модуль через `ModuleActionRegistry`.

## Важное правило

Действия привязываются к:

```text
moduleCode
```

а не к визуальному номеру модуля.

## Ограничения

В этом спринте не выполняется:

- подключение действий к реальным server-side guards;
- миграция `FunctionAccess`;
- UI управления действиями;
- реализация будущих actions в бизнес-модулях.

## Результат

Новые модули смогут добавлять свои действия без переписывания RBAC-ядра.
