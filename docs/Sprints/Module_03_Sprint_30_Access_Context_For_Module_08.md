# Module 03 Sprint 30. Access Context For Module 08

Дата фиксации: 28.06.2026

Статус: контракт передачи данных в будущий Module №8.

## Назначение

Sprint 30 не реализует Module №8.

Он фиксирует минимальный контракт, по которому Module №3 сможет передать
будущему Module №8 информацию о правах и ограничениях пользователя.

## Правильная цепочка

```text
Module №3
AccessContextForCabinet
↓
Module №8
ActiveCabinetContext + CabinetDashboardPreset + CabinetBlockCatalog
↓
Dashboard
отображение рабочего экрана
```

## DTO

Сервис:

```text
app.services.access_context_for_cabinet
```

Основной тип:

```text
AccessContextForCabinet
```

Публичные функции:

```text
build_access_context_for_cabinet(user, active_region_code optional)
get_access_context_for_cabinet(user, active_region_code optional)
```

DTO отдает:

```text
userId
workspaceId
roleCodes
activeRegionCode
permissions
allowedModuleCodes
allowedFeatureCodes
allowedActionCodes
allowedWidgetCodes
allowedQuickActionCodes
scopes
sourceModuleCode = MODULE_03_USERS_ROLES
canViewModule()
canViewWidget()
canRunQuickAction()
```

## Важная граница

Module №3 не отдает в этом контракте:

```text
activeCabinetId
activeCabinetType
cabinet business role
cabinet primary goal
cabinet block catalog
cabinet dashboard preset
object visibility settings
offer settings
participant profile
```

Эти данные должен формировать Module №8.

## Quick Actions

`canRunQuickAction()` в этом контракте проверяет только Module №3-level
доступ:

- quickActionCode существует в QuickActionRegistry;
- action status = ACTIVE;
- role allowed;
- sourceModuleCode / requiredActionCode / requiredScope проходят Permission
  Guard;
- activeRegionCode присутствует;
- widgetCode, если указан, доступен через Widget Permission.

`activeCabinetType` намеренно не используется.

Module №8 позже должен дополнительно решить, уместно ли действие в активном
кабинете.

## Запрещено

- реализовывать CustomerCabinet внутри Module №3;
- реализовывать SupplierCabinet внутри Module №3;
- реализовывать ActiveCabinetContext внутри Module №3;
- создавать Module №8 UI;
- создавать второй Dashboard;
- переносить cabinet visibility settings в Module №3.

## Результат

Module №3 готов отдать права и ограничения в Module №8, но не смешивается с
кабинетным контекстом.
