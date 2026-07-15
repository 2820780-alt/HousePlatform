# АТОМ — Reference Data Correction Governance v1

**Статус:** принято как рабочее правило подготовки справочников; реализация в коде ещё не выполнена.

## Цель

Справочники Module №1 должны оставаться корректируемыми после первой интеграции, но изменения не должны разрушать канонические товары, историю цен, документы и связи модулей.

## Правила

1. `material_type_id`, `profile_id` и `field_code` после интеграции не переиспользуются для нового смысла.
2. Исправлять название, группу, profile, aliases, requirement level и единицы можно новой версией пакета.
3. Hard delete запрещён. Используются `deprecated`, `merged`, `split`, `superseded`.
4. Каждое изменение имеет change log: old/new, reason, date, approver, effective_from.
5. Merge и split содержат явные replacement mappings.
6. Канонические товары не переклассифицируются разрушительно и молча.
7. Изменение reference mapping создаёт очередь revalidation/moderation.
8. Историческая связь товара со старой revision остаётся трассируемой.
9. Корректировка справочника не создаёт материал без цены.
10. Codex интегрирует только утверждённый пакет и не придумывает содержание.
11. UI коррекции позднее размещается внутри «Модерация и качество» или внутреннего управления справочниками, без новой верхней вкладки.
12. Quick Actions, Widgets и Dashboard этой механикой не переопределяются.
13. Права на изменение определяются действующей Role Matrix; новые роли этим документом не создаются.

## Lifecycle

```text
draft
→ preliminary_approved
→ active
→ deprecated / merged / split / superseded
```

## Процесс

```text
proposal
→ reference validation
→ user approval
→ integration
→ regression tests
→ change log publish
```
