# Module 03 Sprint 3. Module Constants

Дата фиксации: 26.06.2026

Статус: реализован удобный слой constants для системных модулей.

## Цель

Оставить удобство для кода, но не сделать constants источником истины.

## Реализовано

Добавлен файл:

```text
app/core/platform_modules.py
```

В нем есть:

- `SystemModuleCode`;
- `SYSTEM_MODULES`;
- `SYSTEM_MODULE_CONSTANTS_ARE_NOT_SOURCE_OF_TRUTH`;
- `is_known_system_module_constant`.

## Принцип

```text
Registry в базе = источник истины.
Constants в коде = удобный слой для системных модулей.
```

## Разрешено

Использовать constants для стабильных стартовых кодов:

- `MODULE_01_MATERIAL_HUB`;
- `MODULE_02_KNOWLEDGE_BASE`;
- `MODULE_03_USERS_ROLES`;
- `MODULE_11_ANALYTICS`;
- `MODULE_14_PRICE_HISTORY`.

## Запрещено

Нельзя завязывать архитектуру только на жесткий enum.

Нельзя считать `SYSTEM_MODULES` полным списком модулей платформы.

Будущие, planned, draft, archived, deprecated и merged-модули должны жить в
`PlatformModuleRegistry`.

## Проверка

Добавлен тест:

```text
tests/test_platform_module_constants.py
```

Он фиксирует, что `MODULE_18_QUALITY_CONTROL` может существовать вне constants,
то есть constants не являются закрытым списком.
