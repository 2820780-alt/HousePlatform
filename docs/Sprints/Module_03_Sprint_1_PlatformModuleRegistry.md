# Module 03 Sprint 1. PlatformModuleRegistry

Дата фиксации: 25.06.2026

Статус: реализован инфраструктурный слой registry.

## Цель

Сделать расширяемый реестр модулей платформы АТОМ.

## Реализовано

Добавлена модель:

- `PlatformModuleRegistry`.

Добавлена таблица:

- `platform_module_registry`.

## Назначение таблицы

`PlatformModuleRegistry` является целевым источником истины о модулях.

Он хранит:

- `moduleCode`;
- `canonicalModuleCode`;
- название и описание;
- версию;
- визуальную нумерацию;
- порядок отображения;
- статус жизненного цикла;
- route и redirect route;
- настройки видимости;
- связи parent/owner/merged;
- legacy codes;
- feature codes.

## Статусы

Поддерживаются статусы:

- `PLANNED`;
- `DRAFT`;
- `ACTIVE`;
- `DISABLED`;
- `DEPRECATED`;
- `ARCHIVED`;
- `MERGED`.

## Важные ограничения

В этом спринте не выполняется:

- seed стартовых модулей;
- seed planned-модулей;
- перевод существующих `module_number` связей;
- миграция DashboardWidget, FavoriteModule, ModuleAccess или FunctionAccess;
- изменение бизнес-логики других модулей.

Существующие `module_number` поля остаются совместимым legacy-слоем до
следующих спринтов.

## Следующий шаг

Module 03 Sprint 1.1:

- `PlatformRegionRegistry`;
- пилотный регион Краснодарский край как seed-запись;
- запрет на hardcoded region в новой логике.
