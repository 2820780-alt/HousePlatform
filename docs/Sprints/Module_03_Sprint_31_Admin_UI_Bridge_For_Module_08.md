# Module 03 Sprint 31. Admin UI Bridge For Module 08

Дата фиксации: 28.06.2026

Статус: bridge готов без переноса бизнес-логики Module №8.

## Назначение

Sprint 31 добавляет в Admin UI Module №3 раздел:

```text
Пользователь -> Кабинеты и контекст
```

Цель раздела — дать администратору одно удобное место просмотра пользователя,
но не переносить source of truth кабинетов в Module №3.

## Реализация

Добавлен adapter/mock service:

```text
app.services.module8_cabinet_admin_preview
```

Публичные функции:

```text
get_module8_cabinet_admin_preview()
getModule8CabinetAdminPreview()
```

DTO:

```text
Module8CabinetAdminPreviewDTO
sourceModuleCode = MODULE_08_PARTNER_PORTAL
```

Admin UI карточки пользователя получает:

```text
accessContextForCabinet
module8CabinetPreview
```

## Что показывает вкладка

- mock/preview кабинеты пользователя из workspace context;
- активный preview-кабинет;
- тип кабинета;
- businessRole;
- предупреждение, что кабинеты управляются Module №8;
- empty state, если Module №8 еще не подключен;
- access context от Module №3;
- доступные модули;
- доступные виджеты и quick actions;
- список того, что редактируется именно в Module №3.

## Что не хранится в Module №3

Module №3 не создает и не хранит:

- ParticipantCabinet;
- CustomerCabinet;
- SupplierCabinet;
- ConstructionCompanyCabinet;
- SpecialistCabinet;
- ActiveCabinetContext;
- ObjectVisibilitySettings;
- ObjectOfferSettings;
- CabinetDashboardPreset;
- CabinetBlockCatalog;
- CabinetDocument;
- CabinetBranch;
- CabinetVerification.

Эти сущности остаются зоной будущего `MODULE_08_PARTNER_PORTAL`.

## Граница редактирования

В Module №3 можно редактировать:

- roles;
- permissions;
- workspace;
- module access;
- widget access;
- quick action access;
- role/dashboard access profile;
- preview role.

Редактирование кабинетов позже должно идти через Module №8 API/service.

## Проверки

- Admin UI показывает вкладку “Кабинеты и контекст”;
- `sourceModuleCode = MODULE_08_PARTNER_PORTAL`;
- без Module №8 есть корректный empty state;
- access context приходит из Module №3;
- Dashboard не изменялся;
- Module №8 сущности не создавались.

## Результат

Администратор получает единое место просмотра пользователя, но RBAC Module №3 и
кабинетный бизнес-контекст Module №8 не смешаны.
