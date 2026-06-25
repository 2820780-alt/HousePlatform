# Module 03 Sprint 5. AccessScope

Дата фиксации: 26.06.2026

Статус: область доступа к данным зафиксирована.

## Цель

Описать область доступа к данным отдельно от действия.

## AccessScope

Поддерживаются scope:

```text
NONE
GLOBAL
OWN
RELEVANT
LIMITED
```

## Реализовано

Добавлен файл:

```text
app/core/access_scopes.py
```

В нем есть:

- `AccessScope`;
- `ACCESS_SCOPES`;
- `is_valid_access_scope`.

## Принцип

`AccessLevel` отвечает на вопрос:

```text
Что пользователь может делать?
```

`AccessScope` отвечает на вопрос:

```text
С какими данными пользователь может это делать?
```

## Примеры

Supplier:

```text
Material Hub -> VIEW + LIMITED
Supplier Prices -> ADMIN + OWN
```

Customer:

```text
Projects -> ADMIN + OWN
Estimates -> VIEW + OWN
```

Contractor:

```text
Tenders -> VIEW + RELEVANT
Works Costs -> ADMIN + OWN
```

Platform Admin:

```text
Material Hub -> ADMIN + GLOBAL
```

## Ограничения

В этом спринте не выполняется:

- миграция существующих `ModuleAccess` и `FunctionAccess`;
- добавление SQL-поля `access_scope`;
- включение реальных server-side guard;
- изменение бизнес-логики других модулей.

## Результат

Система различает действие и границы данных:

```text
AccessLevel + AccessScope
```
