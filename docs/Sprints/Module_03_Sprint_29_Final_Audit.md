# Module 03 Sprint 29. Final Audit

Дата фиксации: 28.06.2026

Статус: финальная проверка Module №3 после Sprint 16-28.

## Назначение

Этот документ фиксирует итоговую проверку Module №3 как access-ядра платформы
АТОМ.

Module №3 отвечает за:

- users / roles / workspaces;
- RBAC;
- PlatformModuleRegistry;
- WidgetRegistry;
- QuickActionRegistry;
- RoleDashboardAccessProfile;
- UserDashboardLayout;
- Permission Guard;
- AuditLog доступа, registry и layout;
- Preview Role / View as Role;
- AI access-change suggestions без самостоятельного изменения прав.

Module №3 не реализует бизнес-логику других модулей, не дублирует Module №8 и
не переписывает существующий Dashboard.

## Dashboard Boundary

Dashboard остается единой оболочкой платформы.

Module №3 отдает Dashboard только:

- что разрешено пользователю;
- какие модули доступны;
- какие виджеты можно предложить;
- какие quick actions можно показать;
- какой стартовый access/profile/layout применить;
- какой preview-role контекст использовать.

`DashboardProfile`, `RoleDashboardAccessProfile` и `UserDashboardLayout` являются
access/profile/layout слоем для существующего Dashboard. Они не являются
отдельными Dashboard по ролям.

Module №8 позже отвечает за уместность активного кабинета и presets кабинета.

## Module Registry

Проверено:

- `PlatformModuleRegistry` используется как источник истины о модулях;
- системная логика строится на `moduleCode`, `moduleId`,
  `canonicalModuleCode`, `featureCode`;
- `module_number`, `displayNumber`, `legacyNumber`, `visualNumber`
  остаются только legacy/display слоем;
- legacy / alias / merged записи нормализуются без удаления старых ссылок;
- `PLANNED`, `DRAFT`, `MERGED`, `ARCHIVED` не отображаются как active modules
  обычному пользователю.

Обязательные legacy mappings закреплены:

```text
MODULE_07_DIGITAL_OBJECT -> MODULE_07_DIGITAL_HOUSE
MODULE_14_PRICE_HISTORY -> MODULE_11_ANALYTICS / PRICE_DYNAMICS
MODULE_14_CONSTRUCTOR_LITE -> MODULE_19_CONSTRUCTOR_LITE
MODULE_15_CONSTRUCTION_GROUPS -> MODULE_01_MATERIAL_HUB / CONSTRUCTION_APPLICABILITY
MODULE_16_ADMIN_CABINET -> DASHBOARD_ADMIN_CONTEXT / MODULE_03_USERS_ROLES context
```

## RBAC

Проверено:

- `AccessLevel`;
- `AccessScope`;
- `Permission`;
- `RolePermission`;
- `UserRoleAssignment`;
- `ModuleAccess`;
- `FunctionAccess`;
- `Permission Guard`;
- server-side `can()` / `require_permission()`.

Правила доступа ссылаются на `moduleCode`, а не на номер модуля.

## Workspace / Scope

Проверено:

- `Workspace`;
- `WorkspaceMember`;
- `WorkspaceRole`;
- owner/scope filtering для `OWN`, `RELEVANT`, `LIMITED`.

Правило сохраняется:

```text
Скрыть кнопку недостаточно.
Все API/service operations должны проходить Permission Guard.
```

## Dashboard Access

Проверено:

- `RoleDashboardAccessProfile` задает стартовые access/preset-профили;
- отдельные Dashboard по ролям не создавались;
- existing Dashboard получает только access/profile/layout данные;
- Dashboard не стал источником business logic;
- Preview Role меняет визуальный контекст, но не реальные права администратора.

## Widget Registry

Проверено:

- WidgetRegistry расширяемый;
- виджеты не завязаны на номер модуля;
- Price Dynamics закреплен как
  `MODULE_11_ANALYTICS / PRICE_DYNAMICS`;
- `MODULE_14_PRICE_HISTORY` остается legacy alias;
- `Widget Permission` фильтрует отображение, добавление и API-доступ к данным
  виджета;
- planned widgets не доступны обычному пользователю как рабочие.

DashboardWidgetRegistry остается временным aggregator/mock compatibility layer.
Целевое направление: module-owned widgets.

## UserDashboardLayout

Проверено:

- layout хранит `widgetCode`, `sourceModuleCode`, `featureCode`;
- layout не позволяет добавить недоступный виджет;
- legacy layout нормализуется;
- `activeCabinetId` и `cabinetType` предусмотрены future-ready;
- Module №8 не реализован внутри Module №3.

## Quick Actions

Проверено:

- Quick Actions строятся через `quickActionCode`, `sourceModuleCode`,
  `featureCode`, `requiredActionCode`, `AccessLevel`, `AccessScope`;
- Module №3 разрешает действие;
- Module №8 позже определяет уместность действия в активном кабинете;
- Dashboard только отображает разрешенные действия.

## AuditLog

Проверено логирование:

- role changes;
- permission / scope changes;
- PlatformModuleRegistry changes;
- module lifecycle changes;
- WidgetRegistry changes;
- widget permission changes;
- UserDashboardLayout changes;
- View as Role enter/exit;
- denied access attempts;
- legacy module normalization;
- inaccessible widget add attempts;
- inactive module open attempts;
- AI access-change suggestions / admin approval required.

## Sprint 28 Extensibility Result

Проверено, что future-модуль можно добавить без переписывания Dashboard / RBAC /
WidgetRegistry:

- future module registration exports registry metadata;
- module visibility depends on registry status and permissions;
- Platform Admin needs explicit grant for new module visibility;
- Super Admin can inspect registry context;
- planned/draft/merged/archived modules do not become active modules;
- future widget can be registered as metadata;
- planned future widget cannot be viewed or added as a working widget;
- future module service/API must use `require_permission()`;
- registry/widget/layout changes are auditable.

## Residual Risks

- `DashboardWidgetRegistry` пока остается compatibility layer; module-owned
  widgets нужно выносить в модули-владельцы данных.
- Часть старых UI routes в админском кабинете использует `module_number` как
  visual/passport route. Это допустимо как legacy/display слой, но новые
  routes должны использовать `moduleCode`.
- Реальный AuthProvider еще не подключен; текущие guards поддерживают mock/dev
  пользователей и должны сохранить внешний API после подключения auth.
- Module №8 пока не подключен как реальный источник cabinet appropriateness.
- Persistence для некоторых audit/mock-preview сценариев остается MVP-ready и
  требует финальной интеграции с production storage.

## TODO

- Dashboard: продолжать читать только normalized access/profile/layout data,
  не переносить business payload в Dashboard.
- Module №8: отдать activeCabinet, cabinet presets, cabinet quick actions и
  appropriateness filtering.
- Future modules: регистрировать moduleCode, permissions, widgets, quick
  actions и lifecycle через Module №3 перед появлением UI/business logic.
- Widget owners: каждый бизнес-модуль должен формировать собственный widget
  payload.
- Auth: заменить mock/dev user context на реальный AuthProvider без изменения
  вызовов `can()` / `require_permission()`.

## Result

Module №3 готов как access-ядро для текущих и будущих модулей платформы АТОМ.
