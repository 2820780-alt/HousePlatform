# ATOM_USER_QUICK_ACTIONS v1.0

## Назначение

Документ фиксирует единое правило быстрых действий для всех текущих и будущих
модулей платформы АТОМ.

Он нужен, чтобы каждый модуль одинаково понимал:

- что такое быстрое действие;
- как пользователь добавляет действие;
- где действие отображается;
- как действие убрать;
- как закрепить действие на карточке модуля на атомной карте;
- какие ограничения по количеству действуют;
- как не смешать быстрые действия с виджетами, Dashboard, Module №3 и Module №8.

## Главное определение

```text
Быстрое действие = личный shortcut пользователя
к уже доступному действию внутри конкретного модуля.
```

Быстрое действие не является:

- виджетом;
- widget payload;
- аналитикой;
- правом доступа;
- RBAC-настройкой;
- элементом WidgetRegistry;
- отдельным модулем;
- бизнес-операцией Dashboard;
- настройкой Module №8.

Пользователь может добавить в быстрые действия только то действие, которое уже
видит и может выполнить в обычном интерфейсе модуля.

## Граница доступа

Быстрое действие не создает отдельную систему прав и не выдает новый доступ.

Если пользователь видит кнопку в модуле, значит действие уже прошло обычную
логику доступности этого модуля. Но при фактическом запуске модуль-владелец
все равно обязан выполнить свои backend/service проверки.

Если права пользователя изменились, сохраненное быстрое действие должно перейти
в disabled/no-permission state или стать недоступным для запуска.

## Зоны ответственности

### Модуль-владелец действия

Модуль-владелец определяет:

- какие действия можно добавить в быстрые действия;
- какое действие безопасно для shortcut;
- какие настройки можно сохранить;
- какой `actionKey` использовать;
- какой `route` или `deepLink` открыть;
- какой `savedConfigRef` или `configSnapshot` сохранить;
- какой текст, иконку и state показать;
- как валидировать сохраненную конфигурацию перед запуском;
- как выполнить действие через собственные guards.

### Экран модуля

Экран модуля отвечает за:

- контекстное меню действия;
- пункт `Добавить в быстрые действия`;
- пункт `Убрать из быстрых действий`;
- пункт `Добавить на карточку модуля`;
- пункт `Снять с карточки модуля`;
- строку быстрых действий внутри модуля;
- сортировку и порядок действий;
- отображение до 9 быстрых действий в модуле;
- закрепление 0-3 действий на карточке модуля.

### Карточка модуля на атомной карте

Карточка модуля может показывать 0-3 закрепленных быстрых действия:

- короткая иконка или мини-кнопка;
- цветовой accent;
- hover tooltip;
- disabled/no-permission/broken-config state.

Карточка модуля не выполняет бизнес-логику сама. Она только открывает
`route`/`deepLink` или передает управление action handler модуля-владельца.

### Dashboard

Dashboard может отображать закрепленные быстрые действия на карточке модуля.

Dashboard не должен:

- придумывать быстрые действия;
- создавать бизнес-операции;
- хранить business result payload;
- обходить логику модуля-владельца;
- быть source of truth для пользовательских quick actions.

### Module №3

Module №3 не является обязательным маршрутом для пользовательских быстрых
действий всех модулей.

Module №3 может иметь собственные быстрые действия внутри своего интерфейса:

- добавить пользователя;
- создать роль;
- открыть реестр модулей;
- открыть виджеты и доступ;
- открыть журнал изменений;
- открыть предпросмотр роли.

Но Module №3 не должен превращать быстрые действия всех модулей в отдельную
централизованную систему прав. Проверки доступа остаются в обычных permission
и service guards модулей.

### Module №8

Module №8 не является обязательным маршрутом для пользовательских быстрых
действий.

Module №8 может позже определять уместность действий для активного кабинета,
но не становится центром управления quick actions.

## Ограничения по количеству

На один модуль для одного пользователя:

```text
максимум 9 быстрых действий
```

Если пользователь пытается добавить десятое действие, показать:

```text
В этом модуле уже добавлено 9 быстрых действий.
Уберите одно действие, чтобы добавить новое.
```

На карточку модуля на атомной карте:

```text
0-3 закрепленных быстрых действия
```

`0` является допустимым значением. Не каждый модуль обязан иметь быстрые
действия на карточке.

Если пользователь пытается закрепить четвертое действие, показать:

```text
На карточке модуля можно закрепить не более 3 быстрых действий.
```

## Добавление действия

Пользователь добавляет быстрое действие из места, где это действие уже
существует:

- правая кнопка мыши по кнопке действия;
- меню `...` рядом с действием;
- контекстное меню строки или карточки;
- иконка pin/shortcut;
- пункт `Добавить в быстрые действия`.

Если действие имеет настройки, сохраняется конфигурация, а не результат.

Сохранять допустимо:

- `sourceModuleCode`;
- `featureCode`;
- `actionKey`;
- `title`;
- `description`;
- `icon`;
- `route`;
- `deepLink`;
- `savedConfigRef` или `configSnapshot`;
- `createdAt`;
- `updatedAt`.

Не сохранять:

- результат выполнения;
- сырые данные;
- business payload;
- чужие данные;
- права доступа.

## Удаление действия

Пользователь должен иметь возможность:

- убрать действие из строки быстрых действий внутри модуля;
- снять действие с карточки модуля;
- удалить shortcut из списка быстрых действий модуля;
- сбросить быстрые действия модуля.

Правила:

- снятие с карточки модуля не удаляет действие из быстрых действий модуля;
- удаление из быстрых действий модуля автоматически снимает действие с
  карточки.

## Рекомендуемые модели

Если в проекте уже есть близкий тип, его нужно расширять, а не создавать дубль.

Минимальная целевая сущность:

```ts
type UserModuleQuickAction = {
  id: string;
  userId: string;
  workspaceId?: string;
  activeRegionCode?: string;
  sourceModuleCode: string;
  featureCode?: string;
  actionKey: string;
  title: string;
  description?: string;
  icon?: string;
  route?: string;
  deepLink?: string;
  savedConfigRef?: string;
  configSnapshot?: Record<string, unknown>;
  order: number;
  isVisibleInModuleBar: boolean;
  isPinnedToAtomCard: boolean;
  atomCardOrder?: number;
  atomCardAccent?: "blue" | "cyan" | "green" | "orange" | "red" | "purple";
  status:
    | "ACTIVE"
    | "DISABLED"
    | "BROKEN_CONFIG"
    | "MODULE_DISABLED"
    | "NO_LONGER_AVAILABLE"
    | "LOADING"
    | "ERROR";
  createdAt: string;
  updatedAt: string;
};
```

Минимальный candidate из модуля-владельца:

```ts
type QuickActionCandidate = {
  sourceModuleCode: string;
  featureCode?: string;
  actionKey: string;
  title: string;
  description?: string;
  icon?: string;
  route?: string;
  deepLink?: string;
  canSaveAsQuickAction: boolean;
  canPinToAtomCard?: boolean;
  configMode?: "NO_CONFIG" | "SAVED_CONFIG_REF" | "CONFIG_SNAPSHOT";
  currentConfigRef?: string;
  currentConfigSnapshot?: Record<string, unknown>;
};
```

## UI states

Обязательные states:

- empty state;
- max limit state;
- pinned max limit state;
- disabled action state;
- broken config state;
- module disabled state;
- action no longer available state;
- loading state;
- error state.

Каноничные тексты:

```text
В этом модуле еще нет быстрых действий.
Откройте действие в модуле и выберите “Добавить в быстрые действия”.
```

```text
В этом модуле уже добавлено 9 быстрых действий.
Удалите одно действие, чтобы добавить новое.
```

```text
На карточке модуля можно закрепить не более 3 быстрых действий.
Снимите одно действие с карточки, чтобы закрепить новое.
```

```text
Настройки этого быстрого действия устарели.
Откройте модуль и настройте действие заново.
```

```text
Это действие больше недоступно в модуле.
Вы можете убрать его из быстрых действий.
```

## Правило для будущих модулей

Каждый новый модуль, который хочет поддерживать быстрые действия, должен:

1. объявить свои `QuickActionCandidate`;
2. использовать `sourceModuleCode`, `featureCode` и `actionKey`;
3. сохранять только shortcut/config reference, а не результат операции;
4. показывать строку быстрых действий внутри модуля;
5. поддерживать лимит 9 действий на модуль;
6. поддерживать закрепление 0-3 действий на атомной карточке;
7. валидировать shortcut перед запуском;
8. выполнять действие только через свой backend/service guard.

## Общий UI-pattern контекстного меню

Переиспользуемый UI-pattern находится в:

```text
templates/_atom_quick_action_menu.html
```

Модуль подключает partial и помечает реальную кнопку действия:

```html
<button
  id="quick-action-run-source-analysis"
  data-quick-action-candidate
  data-quick-action-source-module-code="MODULE_01_MATERIAL_HUB"
  data-quick-action-feature-code="SOURCE_ANALYSIS"
  data-quick-action-key="RUN_SOURCE_ANALYSIS"
  data-quick-action-title="Запустить анализ источника"
  data-quick-action-route="/modules/material-hub"
  data-quick-action-config-provider="materialHubSourceAnalysisQuickActionConfig"
>
  Запустить
</button>
```

Открыть меню можно через:

```text
правую кнопку по действию;
кнопку “...” рядом с действием;
контекстное меню строки;
контекстное меню карточки;
иконку pin / shortcut.
```

Пункты меню:

```text
Добавить в быстрые действия;
Убрать из быстрых действий;
Закрепить на карточке модуля;
Снять с карточки модуля;
Переименовать shortcut.
```

Если действие имеет настройки, модуль может указать:

```text
data-quick-action-config-provider="functionName"
```

Функция должна вернуть только безопасную конфигурацию запуска. Нельзя возвращать:

```text
businessPayload;
resultPayload;
rawData;
sourceRows;
password;
token;
сырые строки данных;
результаты выполнения.
```

Pattern генерирует события:

```text
atom:quick-action:add;
atom:quick-action:remove;
atom:quick-action:pin;
atom:quick-action:unpin;
atom:quick-action:rename.
```

До подключения API события и localStorage являются UI/fallback слоем. Source of truth для выполнения действия остается у модуля-владельца.

## Строка быстрых действий внутри модуля

Переиспользуемая строка быстрых действий реализована в том же partial:

```text
templates/_atom_quick_action_menu.html
```

Модуль размещает контейнер сразу под основной шапкой / верхним меню и над содержимым текущего блока:

```html
<div
  class="atom-module-quick-actions"
  data-quick-action-module-bar="MODULE_01_MATERIAL_HUB"
  aria-label="Быстрые действия модуля База материалов"
></div>
```

Правила строки:

```text
показывать до 9 действий;
учитывать order;
поддерживать удаление shortcut;
показывать disabled / broken config / module disabled / no longer available states;
если действий нет — показывать empty hint.
```

Каноничный empty hint:

```text
В этом модуле еще нет быстрых действий. Откройте действие в модуле и выберите “Добавить в быстрые действия”.
```

Клик по active shortcut открывает `deepLink` или `route`. Business logic не выполняется в строке: фактический запуск должен пройти через модуль-владелец и его backend/service guard.

## Закрепленные действия на карточке АТОМа

Backend/service contract:

```text
getAtomCardPinnedActions(userId, sourceModuleCode, context)
getAtomCardPinnedActionPayloads(userId, sourceModuleCode, context)
```

Контракт payload:

```ts
type AtomCardPinnedQuickActionPayload = {
  quickActionId: string;
  sourceModuleCode: string;
  featureCode?: string;
  actionKey: string;
  title: string;
  icon?: string;
  route?: string;
  deepLink?: string;
  atomCardOrder?: number;
  atomCardAccent?: "blue" | "cyan" | "green" | "orange" | "red" | "purple";
  status: "ACTIVE" | "DISABLED" | "BROKEN_CONFIG" | "MODULE_DISABLED" | "NO_LONGER_AVAILABLE" | "LOADING" | "ERROR";
  isDisabled: boolean;
  placement: "ATOM_CARD";
  tooltip: string;
};
```

UI container contract:

```html
<div
  class="atom-card-pinned-actions"
  data-quick-action-atom-card="MODULE_01_MATERIAL_HUB"
></div>
```

Правила:

```text
0 pinned actions допустимо;
1-3 pinned actions отображаются на карточке;
больше 3 нельзя;
закрепленные действия подсвечиваются через atomCardAccent;
hover/focus показывает tooltip;
если действие disabled/broken/module disabled/no longer available — показывать muted disabled state;
снятие с карточки не удаляет action из модуля;
удаление action из модуля снимает его с карточки.
```

Важно:

```text
Dashboard не придумывает эти действия.
Dashboard только отображает pinned actions, которые принадлежат модулю-владельцу.
Карточка АТОМа не выполняет business logic.
```

## Эталонный пример Module №1

Module №1 / `MODULE_01_MATERIAL_HUB` является первым рабочим примером для будущих модулей.

Подготовленные сценарии:

```text
Запустить анализ источника
Загрузить прайс
Открыть модерацию
Проверить карточки источников
```

Каноничный пример для запуска анализа:

```text
sourceModuleCode = MODULE_01_MATERIAL_HUB
featureCode = SOURCE_ANALYSIS
actionKey = RUN_SOURCE_ANALYSIS
title = Запустить анализ источника
route = /api/v1/admin/material-hub/view
configSnapshot = безопасная конфигурация выбранных источников / сценария / лимитов
```

Важно:

```text
configSnapshot хранит только конфигурацию запуска.
Результат анализа, сырые строки источника и business payload не сохраняются в quick action.
```

Пример `Загрузить прайс`:

```text
sourceModuleCode = MODULE_01_MATERIAL_HUB
featureCode = SUPPLIER_PRICE_UPLOAD
actionKey = UPLOAD_SUPPLIER_PRICE
route = /api/v1/admin/material-hub/view
configSnapshot = supplierName / regionLabel / cityLabel / requiresFileSelection
```

Пример переходов:

```text
featureCode = MATERIAL_MODERATION
actionKey = OPEN_MATERIAL_MODERATION
route = /api/v1/admin/material-hub/view/moderation

featureCode = SOURCE_PRODUCTS
actionKey = CHECK_SOURCE_CARDS
route = /api/v1/admin/material-hub/view/products?status=NEEDS_REVIEW
```

Будущие модули должны повторять этот pattern: quick action добавляется из места, где действие уже существует, а выполнение остается у модуля-владельца.

## Sprint 8: единый pattern для активных модулей

Для активных модулей подготовлен общий catalog/readiness слой:

```text
app/services/active_module_quick_action_patterns.py
```

Этот слой не является RBAC, WidgetRegistry, Dashboard engine или источником
business payload. Он нужен только как documentation/adapter metadata для
модулей-владельцев: какие `sourceModuleCode`, `featureCode`, `actionKey`,
`route`, `configMode` и accent использовать при подключении своих quick action
candidates.

Важно: catalog/readiness слой не создает пользователю shortcut. Быстрое действие
создает только пользователь из существующего candidate в интерфейсе модуля.

Активные модули, где есть реальные UI candidates:

```text
MODULE_01_MATERIAL_HUB
MODULE_03_USERS_ROLES
MODULE_11_ANALYTICS
```

Статусы подключения:

```text
UI_READY:
MODULE_01_MATERIAL_HUB
MODULE_03_USERS_ROLES
MODULE_11_ANALYTICS

PATTERN_READY_NO_UI:
используется только для будущего подключения реального UI модуля-владельца.
```

Module №3 имеет право объявлять собственные candidates, но не управляет быстрыми
действиями других модулей и не создает shortcut сам.

Реальные candidates Module №3 безопасны и открывают существующие экраны:

```text
MODULE_03_USERS_ROLES:
featureCode = USERS_DIRECTORY
actionKey = VIEW
route = /api/v1/admin/users-roles/view#users

featureCode = ACCESS_MATRIX
actionKey = VIEW
route = /api/v1/admin/users-roles/view#access-matrix

featureCode = AUDIT_LOG
actionKey = VIEW
route = /api/v1/admin/users-roles/view/history
```

Опасные решения Module №3 не становятся quick action candidates:

```text
Принять / Отклонить / Отложить заявку;
массово применить доступы;
сохранить / сбросить матрицу;
заблокировать / разблокировать пользователя;
удалить данные.
```

Для Module №1 остаются эталонные candidates:

```text
featureCode = SOURCE_ANALYSIS
actionKey = RUN_SOURCE_ANALYSIS

featureCode = SUPPLIER_PRICE_UPLOAD
actionKey = UPLOAD_SUPPLIER_PRICE

featureCode = MATERIAL_MODERATION
actionKey = OPEN_MATERIAL_MODERATION

featureCode = SOURCE_PRODUCTS
actionKey = CHECK_SOURCE_CARDS
```

Module №11 использует общий UI-pattern:

```text
MODULE_11_ANALYTICS / PRICE_DYNAMICS:
OPEN_PRICE_DYNAMICS
OPEN_CURRENT_PRICE_DYNAMICS_SLICE
```

Для `OPEN_CURRENT_PRICE_DYNAMICS_SLICE` сохраняется только безопасная
конфигурация фильтров текущего среза. Данные графика, результаты расчета,
сырые строки цен и business payload не сохраняются в quick action.

## Sprint 9: planned / future modules compatibility

Для будущих модулей quick actions можно описывать заранее только как
documentation-only compatibility placeholders.

Правило:

```text
planned module не показывает реальные quick actions;
future quick action можно описать в документации / compatibility catalog;
обычным пользователям planned actions не показывать как активные;
planned actions нельзя закреплять на карточке АТОМа;
planned actions нельзя запускать;
planned actions не должны попадать в module bar как рабочие shortcuts.
```

Каталог совместимости находится в:

```text
app/services/active_module_quick_action_patterns.py
```

Будущие модули, для которых зафиксирован planned pattern:

```text
MODULE_12_AI_ASSISTANT
MODULE_13_PROJECT_COLLABORATION
MODULE_15_CONTRACTS
MODULE_16_LOGISTICS_DELIVERY
MODULE_17_FINANCE_PAYMENTS
MODULE_18_QUALITY_CONTROL
MODULE_19_CONSTRUCTOR_LITE
MODULE_20_SITE_SUPERVISION
MODULE_21_WARRANTY_SERVICE
```

Для этих модулей используется статус:

```text
PLANNED_DOCUMENTATION_ONLY
```

и UI-ready state:

```text
PLANNED_NO_ACTIVE_ACTIONS
```

Обязательные признаки planned candidates:

```text
isVisibleToOrdinaryUsers = false
isExecutable = false
canPinToAtomCard = false
metadata.mustNotRenderAsActive = true
```

Стандарт для будущего модуля:

```text
moduleCode / sourceModuleCode;
sourceActionId / actionKey;
permissionKey;
captureContext;
route / deepLink;
savedParams;
savedFilters;
savedSearchQuery;
isSafeToRun;
requiresConfirmation.
```

UI-правило будущего модуля:

```html
<button
  data-quick-action-candidate
  data-quick-action-source-module-code="MODULE_XX_EXAMPLE"
  data-quick-action-feature-code="EXAMPLE_FEATURE"
  data-quick-action-key="OPEN_EXAMPLE"
  data-quick-action-permission-key="VIEW"
  data-quick-action-route="/api/v1/admin/example/view"
  data-quick-action-title="Открыть пример">
  Открыть пример
</button>
```

Каждый будущий модуль обязан соблюдать правила:

```text
не создавать fixed quick actions;
не создавать default quick actions;
не seed-ить quick actions;
помечать только реальные кнопки как candidate;
сохранять только безопасный контекст действия;
проверять RBAC перед отображением и запуском;
поддерживать pin внутри модуля;
поддерживать pin на карточке Dashboard;
не смешивать Quick Actions с Widgets.
```

Когда будущий модуль становится рабочим, его owner-module должен заменить
planned documentation-only candidate на реальный `QuickActionCandidate` внутри
своего UI и сохранить все базовые правила:

```text
sourceModuleCode обязателен;
featureCode желателен;
actionKey обязателен;
business payload не сохранять;
запуск только через guard модуля-владельца.
```
## Sprint 10: удаление, сброс и восстановление порядка

Пользователь должен управлять своими быстрыми действиями без обращения к
администратору.

Поддерживаемые операции:

```text
убрать одно действие из строки быстрых действий;
снять одно действие с карточки модуля;
удалить shortcut из модуля;
изменить порядок быстрых действий;
сбросить все быстрые действия текущего модуля;
сбросить все закрепленные действия на карточке модуля.
```

Правила:

```text
удаление shortcut из модуля автоматически снимает его с карточки;
снятие с карточки не удаляет shortcut из модуля;
сброс закрепленных действий не удаляет быстрые действия из строки модуля;
сброс быстрых действий модуля удаляет shortcuts только для этого sourceModuleCode;
после удаления или сброса порядок должен быть нормализован;
подтверждение удаления желательно для массовых операций.
```

UI-pattern в `templates/_atom_quick_action_menu.html` поддерживает:

```text
moveStoredQuickAction();
resetModuleQuickActions();
resetAtomCardPinnedQuickActions();
```

и события:

```text
atom:quick-action:reorder;
atom:quick-action:reset-module;
atom:quick-action:reset-pinned.
```

Backend/service слой поддерживает:

```text
removeUserModuleQuickAction();
reorderUserModuleQuickActions();
unpinQuickActionFromAtomCard();
resetUserModuleQuickActions();
resetAtomCardPinnedQuickActions();
```

Эти операции управляют только пользовательскими shortcut/config references.
Они не удаляют бизнес-данные модуля-владельца и не меняют permissions.

## Sprint 11: states и защита от устаревших действий

Поддерживаемые состояния:

```text
ACTIVE
DISABLED
BROKEN_CONFIG
MODULE_DISABLED
NO_LONGER_AVAILABLE
LOADING
ERROR
```

Правило:

```text
если действие устарело, модуль изменился или конфигурация сломалась,
интерфейс не должен падать;
нужно показать понятный state;
пользователь должен иметь возможность удалить shortcut или открыть модуль
и настроить действие заново.
```

Значения:

```text
ACTIVE — действие можно передать модулю-владельцу.
DISABLED — действие временно отключено.
BROKEN_CONFIG — сохраненная конфигурация устарела.
MODULE_DISABLED — модуль-владелец отключен.
NO_LONGER_AVAILABLE — actionKey больше не доступен в модуле.
LOADING — действие обновляется / проверяется.
ERROR — действие не удалось подготовить, нужен повторный заход в модуль.
```

`LOADING` и `ERROR` не являются бизнес-результатами. Они нужны только для
безопасного отображения состояния shortcut и не дают права выполнить действие
в обход модуля-владельца.
