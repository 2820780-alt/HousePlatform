# Module 03 Sprint 4. AccessLevel

Дата фиксации: 26.06.2026

Статус: чистые уровни действий зафиксированы.

## Цель

Создать чистые уровни действий для RBAC.

## Уровни доступа

Поддерживаются только action levels:

```text
NO_ACCESS
VIEW
CREATE
EDIT
APPROVE
ADMIN
```

## Реализовано

Добавлен файл:

```text
app/core/access_levels.py
```

В нем есть:

- `AccessLevel`;
- `ACCESS_LEVELS`;
- `ACCESS_SCOPES_ARE_NOT_ACCESS_LEVELS`;
- `is_valid_access_level`;
- `is_access_scope`.

## Важное правило

Scope не является уровнем действия.

Не добавлять в `AccessLevel`:

- `VIEW_OWN`;
- `ADMIN_OWN`;
- `LIMITED_VIEW`;
- `VIEW_RELEVANT`.

Эти значения должны жить в отдельном scope-слое будущих спринтов.

## Ограничения

В этом спринте не выполняется:

- миграция существующих строковых `access_level` в SQL enum;
- изменение бизнес-логики проверок доступа;
- добавление access scope;
- переписывание ModuleAccess или FunctionAccess.

## Результат

Действия отделены от области доступа.
