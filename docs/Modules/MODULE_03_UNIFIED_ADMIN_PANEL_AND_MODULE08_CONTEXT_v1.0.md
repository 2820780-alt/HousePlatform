# MODULE_03_UNIFIED_ADMIN_PANEL_AND_MODULE08_CONTEXT v1.0

## Назначение

Документ фиксирует границу единой административной панели АТОМ после
подключения bridge-слоя к Module №8.

Единая панель управления реализуется на базе:

```text
MODULE_03_USERS_ROLES
```

Пользовательское назначение панели:

```text
единый командный мост / центр управления доступами,
пользователями, ролями, workspace, registry, layout
и кабинетным контекстом пользователя.
```

## Главное правило

```text
Module №3 Admin UI = единая панель управления.
Module №8 остается source of truth для кабинетного контекста.
Dashboard не редактируется.
```

Module №3 может показывать и настраивать административную часть данных,
связанных с кабинетами, только через:

```text
adapter
DTO
mock preview
future Module №8 API/service
```

Module №3 не создает бизнес-сущности Module №8 и не становится владельцем
кабинетов.

## Зона ответственности Module №3 Admin UI

Module №3 Admin UI отвечает за:

- пользователей;
- системные роли;
- workspace;
- permissions;
- module access;
- feature access;
- widget access;
- quick action access;
- PlatformModuleRegistry;
- WidgetRegistry;
- QuickActionRegistry;
- UserDashboardLayout;
- RoleDashboardAccessProfile;
- Preview Role / View as Role;
- AuditLog доступа, registry и layout;
- bridge-раздел “Кабинеты и контекст”.

## Раздел “Кабинеты и контекст”

Раздел в Module №3 Admin UI нужен, чтобы администратор видел пользователя
комплексно:

```text
Пользователь
↓
Роли / workspace / permissions
↓
Доступные модули / widgets / quick actions
↓
Кабинеты и контекст через Module №8 adapter
```

Раздел может показывать:

- список кабинетов пользователя;
- активный кабинет;
- тип кабинета;
- бизнес-роль в кабинете;
- workspace;
- activeRegionCode;
- доступные модули;
- доступные виджеты;
- доступные быстрые действия;
- связанные объекты как preview / placeholder;
- настройки видимости как preview / placeholder;
- Dashboard context preview;
- предупреждение, что кабинеты управляются Module №8.

## Что Module №3 может настраивать

В единой панели Module №3 можно настраивать:

- роль пользователя;
- workspace пользователя;
- permissions;
- module access;
- feature access;
- widget access;
- quick action access;
- role/dashboard access profile;
- UserDashboardLayout в рамках прав;
- Preview Role;
- preview cabinet placeholder, если используется mock/adapter.

Эти настройки относятся к доступу и отображению, а не к бизнес-сущностям
кабинета.

## Source of truth Module №8

Source of truth для кабинетного контекста остается:

```text
MODULE_08_PARTNER_PORTAL
```

Module №8 владеет:

- ParticipantCabinet;
- CustomerCabinet;
- SupplierCabinet;
- ConstructionCompanyCabinet;
- SpecialistCabinet;
- ActiveCabinetContext;
- CabinetDashboardPreset;
- CabinetBlockCatalog;
- CabinetQuickAction recommendations;
- CabinetWidgetPreference recommendations;
- CabinetModuleShortcut;
- CabinetObjectLink;
- ObjectVisibilitySettings;
- ObjectOfferSettings;
- CabinetContact;
- CabinetBranch;
- CabinetDocument;
- CabinetVerification;
- CabinetModerationLog.

Module №3 может отображать эти данные только как preview/DTO или через future
Module №8 API. Module №3 не должен хранить их как собственные сущности.

## Adapter / DTO boundary

Для связи Module №3 и Module №8 используются:

```text
AccessContextForCabinet
Module8CabinetAdminPreviewDTO
DashboardReadyCabinetContextDTO
```

Правильная цепочка:

```text
Module №3
AccessContextForCabinet
↓
Module №8 adapter / DTO
Cabinet preview / ActiveCabinetContext / Dashboard-ready context
↓
Module №3 Admin UI
отображает bridge-раздел
```

Module №3 отдает Module №8:

- userId;
- workspaceId;
- roleCodes;
- permissions;
- allowedModuleCodes;
- allowedFeatureCodes;
- allowedWidgetCodes;
- allowedQuickActionCodes;
- scopes;
- activeRegionCode;
- проверки `canViewModule()`, `canViewWidget()`, `canRunQuickAction()`.

Module №3 не отдает и не формирует как source of truth:

- activeCabinetId;
- activeCabinetType;
- cabinet business role;
- cabinet primary goal;
- CabinetBlockCatalog;
- CabinetDashboardPreset;
- object visibility settings;
- offer settings;
- participant profile.

Эти данные формирует Module №8.

## Dashboard boundary

Dashboard не редактируется в рамках единой панели Module №3.

Dashboard отвечает только за:

- layout;
- визуальное отображение;
- атомную карту;
- рендер разрешенных модулей;
- рендер widget payload;
- рендер quick actions;
- уважение UserDashboardLayout;
- уважение WidgetRegistry;
- уважение Module №3 permissions;
- уважение Module №8 cabinet context.

Module №3 Admin UI не должен:

- создавать второй Dashboard;
- копировать layout Dashboard;
- редактировать атомную карту;
- считать KPI;
- считать аналитику;
- создавать business payload виджета;
- становиться владельцем Dashboard UI.

## Module №8 UI на текущем этапе

На текущем этапе Module №8 не имеет отдельного кабинета управления как
самостоятельного административного центра.

Допустим только ограниченный UI настроек Module №8, если он не дублирует
Dashboard и не заменяет Module №3 Admin UI:

- профиль кабинета;
- создание / переключение кабинета;
- сотрудники;
- контакты;
- филиалы;
- регионы;
- документы;
- связанные объекты;
- настройки видимости;
- настройки предложений;
- настройки рабочего экрана.

Административная работа с пользователем должна идти через единую панель
Module №3.

## Запрещено

В рамках единой панели Module №3 запрещено:

- создавать `ParticipantCabinet` внутри Module №3;
- создавать `CustomerCabinet` внутри Module №3;
- создавать `SupplierCabinet` внутри Module №3;
- создавать `ConstructionCompanyCabinet` внутри Module №3;
- создавать `SpecialistCabinet` внутри Module №3;
- хранить `ActiveCabinetContext` как бизнес-сущность Module №3;
- хранить `ObjectVisibilitySettings` как source of truth Module №3;
- хранить `ObjectOfferSettings` как source of truth Module №3;
- редактировать Dashboard;
- создавать второй Dashboard;
- переносить бизнес-логику Module №8 в Module №3;
- использовать `moduleNumber` как системный идентификатор;
- хардкодить регион как бизнес-условие.

## Разрешено

В рамках единой панели Module №3 разрешено:

- показывать Module №8 preview через adapter;
- показывать empty state, если Module №8 еще не подключен;
- показывать предупреждение “Кабинеты управляются Module №8”;
- редактировать роли, permissions, workspace, module/widget/action access;
- показывать allowed modules/widgets/actions для пользователя;
- показывать Dashboard access profile;
- запускать Preview Role без изменения реальной роли;
- логировать изменения доступа и registry в AuditLog;
- подготавливать bridge к будущему Module №8 API.

## UI-идея

Дизайн Module №3:

```text
командный мост / центр управления доступами и кабинетным контекстом
```

Интерфейс должен быть утилитарным:

- список пользователей;
- карточка пользователя;
- роли и workspace;
- активные права;
- registry-секции;
- bridge-раздел “Кабинеты и контекст”;
- AuditLog;
- предупреждения о source of truth.

Не нужен второй домашний экран, маркетинговый layout или атомная карта внутри
Module №3 Admin UI.

## Контрольные правила для Codex

Перед изменениями в этой зоне Codex должен проверить:

1. задача относится к Module №3 Admin UI или к Module №8;
2. не создается ли новая сущность Module №8 внутри Module №3;
3. не редактируется ли Dashboard без отдельной задачи;
4. не используется ли `moduleNumber` для логики;
5. не превращается ли preview в source of truth;
6. проходит ли действие через PermissionGuard / server-side guard;
7. логируется ли значимое изменение в AuditLog.

## Результат

Единая панель Module №3 зафиксирована как административный центр управления
доступами и кабинетным контекстом, но архитектура не смешивает:

```text
RBAC / registry / permissions  -> MODULE_03_USERS_ROLES
cabinet context / participant settings -> MODULE_08_PARTNER_PORTAL
visual platform Dashboard -> Dashboard shell
```
