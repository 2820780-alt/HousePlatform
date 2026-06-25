# Module 03 Sprint 7. Базовые сущности RBAC

Дата фиксации: 26.06.2026

Статус: базовые RBAC-сущности расширены под moduleCode/actionCode.

## Цель

Создать основу пользователей, ролей и прав так, чтобы права работали не только
для текущих, но и для будущих модулей.

## Существующие сущности

В проекте уже были:

- `User`;
- `Role`;
- `Permission`;
- `RolePermission`;
- `UserRoleAssignment`;
- `Workspace`;
- `WorkspaceMember`;
- `AuditLog`.

`UserRoleAssignment` остается текущей сущностью назначения роли пользователю.
Отдельная сущность `UserRole` не создается, чтобы не дублировать смысл.

## Добавлено

Добавлена сущность:

- `WorkspaceRole`.

Она связывает workspace и role независимо от конкретного пользователя.

## Permission

`Permission` расширен целевой структурой:

```text
id
moduleCode
actionCode
accessLevel
accessScope
conditions
isActive
```

Legacy-поле `module_number` сохраняется временно для совместимости.

## Главное правило

```text
permission.moduleCode -> PlatformModuleRegistry.moduleCode
```

Права не должны опираться на визуальный номер модуля.

## Миграция

Добавлена миграция:

```text
database/migrations/20260626_module03_rbac_base_entities.sql
```

Она:

- добавляет `module_code`;
- добавляет `action_code`;
- добавляет `access_level`;
- добавляет `access_scope`;
- добавляет `conditions`;
- добавляет `is_active`;
- переносит известные `module_number` в `module_code` через `PlatformModuleRegistry`;
- определяет базовый `action_code` по `permission_key`;
- создает `workspace_roles`;
- добавляет nullable FK `permissions.module_code` на `platform_module_registry.module_code`.

## Ограничения

В этом спринте не выполняется:

- удаление `module_number`;
- перевод `ModuleAccess` и `FunctionAccess` на `moduleCode`;
- внедрение server-side PermissionGuard;
- изменение бизнес-логики модулей;
- изменение Dashboard.

## Проверка

Добавлены тесты:

```text
tests/test_rbac_base_entities.py
```

## Результат

RBAC-основа готова к правам вида:

```text
moduleCode + actionCode + accessLevel + accessScope + conditions
```
