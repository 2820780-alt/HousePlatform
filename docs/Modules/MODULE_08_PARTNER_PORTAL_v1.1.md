# MODULE_08_PARTNER_PORTAL v1.1

Пользовательское название: Кабинеты участников.

Статус документа: фиксация границ Module №8 перед реализацией.

## Назначение

Module №8 отвечает за кабинетный контекст пользователя и персонализацию рабочего
Dashboard.

Module №8 не является отдельным вторым Dashboard. Он не рисует главный экран
платформы вместо Dashboard и не создает собственный Dashboard engine.

Правильная цепочка:

```text
Module №3 / Users, Roles, Workspaces
что пользователю разрешено
↓
Module №8 / Кабинеты участников
что уместно в активном кабинете
↓
Dashboard
отображает рабочий атомный экран
```

## Зона ответственности

Module №8 определяет:

- активный кабинет пользователя;
- тип кабинета;
- бизнес-роль в кабинете;
- главный фокус рабочего сценария;
- кабинетные presets Dashboard;
- каталог уместных блоков;
- уместные быстрые действия;
- связанные объекты через ссылки / adapter;
- настройки видимости объектов и предложений;
- персонализацию рабочего Dashboard в рамках разрешений Module №3.

Dashboard отвечает только за отображение:

- верхней панели;
- атомной карты;
- виджетов;
- быстрых действий;
- уведомлений;
- layout.

Dashboard не должен становиться владельцем кабинетной бизнес-логики.

## Связь с Module №3

Module №3 отвечает за:

- пользователя;
- роли;
- workspace;
- permissions;
- allowed modules;
- allowed featureCode;
- allowed widgetCode;
- allowed quickActionCode;
- WidgetRegistry;
- UserDashboardLayout;
- Permission Guard.

Module №8 не выдает права сам. Он получает access context от Module №3 и
дополнительно решает, что уместно показывать в активном кабинете.

Module №8 не должен дублировать:

- RBAC;
- WidgetRegistry;
- QuickActionRegistry;
- UserDashboardLayout как источник прав;
- Permission Guard.

## Типы кабинетов

Базовые типы кабинетов:

```text
CUSTOMER
MATERIAL_SUPPLIER
CONSTRUCTION_COMPANY
SPECIALIST
```

Пользовательские названия:

- Заказчик;
- Поставщик материалов;
- Строительная компания;
- Специалист.

Один пользователь может иметь несколько кабинетов. Например, один аккаунт может
работать как заказчик по одному объекту и как представитель поставщика в другом
workspace.

Module №8 должен поддерживать выбор активного кабинета без изменения реальной
роли пользователя в Module №3.

## CustomerCabinet

`CustomerCabinet` — кабинет заказчика внутри Module №8.

Главный фокус:

```text
Образ объекта
```

Блоки CustomerCabinet:

- Мои объекты;
- Сметы;
- Проверка смет;
- Склад объекта;
- Закупки placeholder;
- Документы;
- База технологий;
- Настройки предложений;
- Видимость объекта;
- Аналитика стоимости placeholder.

Границы:

- объекты и склад объекта остаются в `MODULE_07_DIGITAL_HOUSE`;
- сметы остаются в `MODULE_05_ESTIMATE_ENGINE`;
- проверка смет остается в `MODULE_06_ESTIMATE_AUDIT`;
- закупки остаются в `MODULE_09_PROCUREMENT`;
- документы материалов остаются в `MODULE_01_MATERIAL_HUB`;
- база технологий остается в `MODULE_02_KNOWLEDGE_BASE`;
- аналитика стоимости остается в `MODULE_11_ANALYTICS`;
- Module №8 хранит только кабинетный контекст, видимость, настройки предложений и рекомендации рабочего экрана.

## SupplierCabinet

`SupplierCabinet` — кабинет поставщика материалов внутри Module №8.

Главный фокус:

```text
Продажи / прайсы / заявки
```

Роли MVP:

- Директор / владелец;
- Администратор;
- Менеджер продаж.

Блоки SupplierCabinet:

- Прайсы placeholder;
- Заявки placeholder;
- Филиалы;
- Контакты;
- Регионы поставки;
- Документы;
- Объекты в работе;
- Аналитика спроса placeholder;
- Marketplace placeholder.

Границы:

- прайсы и документы материалов остаются в `MODULE_01_MATERIAL_HUB`;
- заявки поставщику и закупочный процесс остаются в `MODULE_09_PROCUREMENT`;
- Marketplace / витрина остаются в `MODULE_10_MARKETPLACE`;
- аналитика спроса остается в `MODULE_11_ANALYTICS`;
- объекты в работе передаются как ссылки / visibility context, сами объекты остаются в `MODULE_07_DIGITAL_HOUSE`;
- Module №8 хранит только кабинетный контекст, роли кабинета, контакты, филиалы, регионы поставки и настройки видимости.

### Связь Supplier из Module №1

Поставщик как источник материалов, прайсов и supplier canonical context остается в:

```text
MODULE_01_MATERIAL_HUB
```

Module №8 может хранить только link между supplier из Material Hub и кабинетом:

```text
SupplierCabinetLink
```

Поля link:

- `supplier_id`;
- `cabinet_id`;
- `link_status`;
- `verification_status`;
- `sourceModuleCode = MODULE_01_MATERIAL_HUB`;
- `targetModuleCode = MODULE_08_PARTNER_PORTAL`.

Правило:

```text
Module №8 не создает Material, Price, PriceList или canonical Supplier.
```

Эти данные остаются в Module №1, а Module №8 хранит только связь с кабинетом,
статус связи и статус проверки.

## ConstructionCompanyCabinet

`ConstructionCompanyCabinet` — кабинет строительной компании внутри Module №8.

Главный фокус:

```text
Проекты / объекты компании
```

Роли:

- Директор / владелец;
- Администратор;
- Прораб;
- Инженер снабжения;
- Сметчик;
- Менеджер проекта / продаж;
- Инженер ПТО;
- Кладовщик.

Блоки ConstructionCompanyCabinet:

- Объекты;
- Сметы placeholder;
- Работы placeholder;
- Сотрудники;
- Закупки placeholder;
- Заявки placeholder;
- Документы;
- Договоры placeholder;
- Финансы placeholder;
- Контроль качества placeholder.

Границы:

- объекты остаются в `MODULE_07_DIGITAL_HOUSE`;
- сметы остаются в `MODULE_05_ESTIMATE_ENGINE`;
- работы остаются в `MODULE_04_WORKS_COSTS`;
- закупки и заявки остаются в `MODULE_09_PROCUREMENT`;
- документы материалов остаются в `MODULE_01_MATERIAL_HUB`;
- договоры остаются в `MODULE_15_CONTRACTS`;
- финансы остаются в `MODULE_17_FINANCE_PAYMENTS`;
- контроль качества остается в `MODULE_18_QUALITY_CONTROL`;
- Module №8 хранит только кабинетный контекст, роли кабинета, настройки видимости, сотрудников и рекомендации рабочего экрана.

### Связь с Works Costs / Module №4

Работы, расценки, источники расценок и утвержденные WorkRate остаются в:

```text
MODULE_04_WORKS_COSTS
```

Module №8 может хранить только link между кабинетным контекстом и ссылками
Module №4:

```text
WorksCostsCabinetLink
```

Поля link:

- `cabinet_id`;
- `work_rate_source_id` optional;
- `contractor_profile_ref` optional;
- `work_producer_ref` optional;
- `link_status`;
- `sourceModuleCode = MODULE_04_WORKS_COSTS`;
- `targetModuleCode = MODULE_08_PARTNER_PORTAL`.

Правило:

```text
Module №8 не создает WorkRate.
```

Module №8 не хранит каталог работ, наблюдения расценок, утвержденные расценки
или расчет стоимости работ. Он только связывает кабинет / подрядчика /
производителя работ с соответствующими ссылками Module №4.

## SpecialistCabinet

`SpecialistCabinet` — кабинет специалиста внутри Module №8.

Главный фокус:

```text
Специализация / рабочий контекст
```

Специализации MVP:

- Прораб;
- Инженер снабжения;
- Сметчик;
- Инженер ПТО;
- Проектировщик.

Специализации не являются отдельными активными `moduleCode`. Они задают
`businessRole`, кабинетный preset и набор уместных блоков внутри типа кабинета
`SPECIALIST`.

Пресеты по специализациям:

- Прораб → объекты / работы / склад / задачи;
- Инженер снабжения → спецификации / закупки / поставщики;
- Сметчик → сметы / проверка / материалы / работы / экспорт;
- Инженер ПТО → документы / объемы / исполнительная информация placeholder;
- Проектировщик → проектные данные / план объекта placeholder.

Границы:

- объекты и склад объекта остаются в `MODULE_07_DIGITAL_HOUSE`;
- работы остаются в `MODULE_04_WORKS_COSTS`;
- сметы и экспорт остаются в `MODULE_05_ESTIMATE_ENGINE`;
- проверка смет остается в `MODULE_06_ESTIMATE_AUDIT`;
- материалы и документы остаются в `MODULE_01_MATERIAL_HUB`;
- закупки и поставщики в закупочном контексте остаются в `MODULE_09_PROCUREMENT`;
- задачи и исполнительная информация остаются future-ready через `MODULE_13_PROJECT_COLLABORATION`;
- проектные данные и план объекта остаются future-ready через `MODULE_19_CONSTRUCTOR_LITE`;
- Module №8 хранит только кабинетный контекст, выбранную специализацию, preset и рекомендации рабочего экрана.

## Апгрейд специалиста до строительной компании

Module №8 должен поддерживать сценарий, когда специалист вырастает до
строительной компании.

Подготовленные сущности:

- `CabinetUpgradeRequest`;
- `CabinetUpgradeHistory`;
- `SpecialistToCompanyLink`.

Правила:

- `SpecialistCabinet` не удаляется и не теряет историю;
- создается новый `ConstructionCompanyCabinet`;
- специалист связывается с новым кабинетом как `FOUNDER_OWNER`;
- переход фиксируется в `CabinetUpgradeHistory`;
- заявка хранит причину и статус перехода;
- Module №8 хранит только кабинетный переход и связь кабинетов.

Module №8 не переносит в себя:

- объекты компании;
- работы;
- сметы;
- закупки;
- договоры;
- финансы;
- контроль качества.

Эти данные остаются в модулях-владельцах, а `SpecialistToCompanyLink` только
показывает, как связаны старый кабинет специалиста и новый кабинет компании.

## Модерация и верификация кабинетов

Module №8 хранит состояние проверки кабинета и историю модерационных решений.

Подготовленные сущности:

- `CabinetVerification`;
- `CabinetModerationLog`.

Статусы кабинета:

```text
DRAFT
PENDING_REVIEW
VERIFIED
NEEDS_CLARIFICATION
REJECTED
RESTRICTED
BLOCKED
ARCHIVED
```

Уровни проверки:

```text
NOT_VERIFIED
BASIC_CHECKED
DOCUMENTS_CHECKED
COMPANY_VERIFIED
TRUSTED_PARTNER
```

Назначение:

- `CabinetVerification` хранит текущий статус и уровень проверки кабинета;
- `CabinetModerationLog` хранит историю модерационных событий, причины и комментарии;
- блокировка / ограничение кабинета не является удалением данных;
- верификация кабинета не выдает права сама по себе.

Границы:

```text
MODULE_08_PARTNER_PORTAL
→ cabinet verification / moderation state

MODULE_03_USERS_ROLES
→ permissions, access level, scope, server-side guard

AuditLog
→ системный аудит изменения прав, registry и критичных действий
```

`CabinetModerationLog` не заменяет `AuditLog`, а `CabinetVerification` не
становится источником прав.

## Service / Adapter layer

Module №8 должен отдавать кабинетный контекст через сервисный adapter, а не
через Dashboard и не через Module №3.

Подготовленный слой:

```text
partner_portal_adapter
```

Методы adapter:

```text
getActiveCabinetContext(context)
switchActiveCabinet(cabinetId, context)
getAvailableCabinets(context)
getCabinetDashboardContext(cabinetId, context)
getCabinetDashboardPreset(cabinetId, context)
getCabinetBlockCatalog(cabinetId, context)
getCabinetQuickActions(cabinetId, context)
getCabinetWidgetPreferences(cabinetId, context)
updateCabinetWidgetPreferences(cabinetId, payload, context)
getCabinetObjectLinks(cabinetId, context)
getObjectVisibilityForCabinet(objectId, cabinetId, context)
updateObjectOfferSettings(objectId, payload, context)
getCabinetSummary(context)
```

Все методы принимают контекст:

```text
userId
roleCode
workspaceId
activeRegionCode
activeCabinetId
permissions optional
```

Границы adapter:

- Module №8 собирает кабинетный контекст, presets, блоки, быстрые действия и настройки видимости;
- Module №3 остается источником permissions / allowed modules / allowed widgets / allowed quick actions;
- Dashboard только отображает результат adapter;
- adapter не создает материалы, сметы, закупки, WorkRate, MarketplaceOffer или DigitalHouse.

## Dashboard-ready DTO

Для передачи кабинетного контекста в существующий Dashboard Module №8
подготавливает отдельный DTO:

```text
sourceModuleCode = MODULE_08_PARTNER_PORTAL
featureCode = CABINET_DASHBOARD_CONTEXT
```

Поля DTO:

```text
activeCabinetId
activeCabinetType
activeBusinessRole
activeRegionCode
activeObjectId
mainFocus
primaryBlocks
secondaryBlocks
quickActions
availableModuleShortcuts
widgetPreferences
hiddenBlocks
lockedBlocks
futureBlocks
premiumBlocks
```

Назначение DTO:

- передать Dashboard уже подготовленный кабинетный контекст;
- разделить основные и вторичные блоки рабочего экрана;
- передать быстрые действия и предпочтения виджетов без business payload;
- явно показать скрытые, locked, future и premium блоки;
- сохранить границу: Dashboard отображает, Module №8 определяет уместность, Module №3 фильтрует права.

Ограничения:

- DTO не является новым Dashboard;
- DTO не хранит расчеты, аналитику, сметы, закупки, материалы, цены или склад;
- DTO не выдает права и не заменяет Module №3;
- DTO не создает карточки Dashboard напрямую;
- данные виджетов должны приходить от модулей-владельцев через свои payload / adapters.

## UI Module №8

Видимый UI Module №8 должен быть поверхностью настроек кабинета, а не вторым
Dashboard.

Разрешенные экраны / разделы:

- профиль кабинета;
- создание кабинета;
- переключение кабинета;
- сотрудники;
- контакты;
- филиалы;
- регионы;
- документы;
- связанные объекты;
- настройки видимости;
- настройки предложений;
- настройки рабочего экрана.

Запрещено:

```text
создавать отдельный большой домашний экран Module №8,
который дублирует Dashboard, атомную карту, KPI или нижние виджеты.
```

Реализованный UI:

```text
/api/v1/partner-portal/settings
```

Эта страница показывает кабинетные настройки и использует общий верхний бар
платформы. Переход на главный Dashboard остается через логотип / верхнюю панель.

## Сотрудники и бизнес-роли

Module №8 хранит сотрудников кабинета и их рабочие бизнес-роли.

Подготовленные сущности:

- `CabinetEmployee`;
- `CabinetEmployeeRole`;
- `CabinetMembership`.

Назначение:

- `CabinetEmployee` хранит профиль сотрудника в контексте кабинета;
- `CabinetEmployeeRole` хранит кабинетную бизнес-роль, например `FOREMAN`,
  `ESTIMATOR`, `SALES_MANAGER`, `COMPANY_OWNER`;
- `CabinetMembership` связывает пользователя / сотрудника с кабинетом и
  бизнес-ролью.

Главное правило:

```text
Module №8 хранит бизнес-роль.
Module №3 хранит права.
```

Поэтому Module №8 не хранит и не рассчитывает:

- `permissionCode`;
- `accessLevel`;
- `accessScope`;
- role permission matrix;
- server-side permission checks.

Если бизнес-роль должна дать пользователю права, это оформляется через Module
№3: роли, permissions, workspace, Widget Permission и Permission Guard.

## Контакты, филиалы, регионы, зоны доставки и документы кабинета

Module №8 хранит профильный контекст участника:

- `CabinetContact`;
- `CabinetBranch`;
- `CabinetServiceRegion`;
- `CabinetDeliveryZone`;
- `CabinetDocument`.

Назначение:

- `CabinetContact` — контакты участника / отдела / ответственного лица;
- `CabinetBranch` — филиалы, офисы, склады или точки присутствия участника;
- `CabinetServiceRegion` — регионы работы, поставки или обслуживания;
- `CabinetDeliveryZone` — зоны доставки и покрытия;
- `CabinetDocument` — документы кабинета, компании или участника.

Важно:

```text
CabinetDocument != MaterialDocument
```

Документы материалов, сертификаты, технические листы и документы по
canonical Material остаются в:

```text
MODULE_01_MATERIAL_HUB
featureCode = DOCUMENTS
```

Документы кабинета / компании / участника хранятся в:

```text
MODULE_08_PARTNER_PORTAL
featureCode = CABINET_DOCUMENTS
```

Поэтому в кабинетных presets используется отдельный блок:

```text
CABINET_DOCUMENTS_BLOCK
```

а `DOCUMENTS_BLOCK` остается блоком документов материалов Module №1.

## Верхняя панель

Верхняя панель Dashboard должна получать от кабинетного контекста:

- кабинет;
- регион;
- объект, если он уместен для текущего кабинета и сценария.

Регион передается как `activeRegionCode` / `region_id`. Пилотный регион может
быть `KRASNODAR_KRAI`, но его нельзя использовать как бизнес-условие.

Объект не является обязательным глобальным элементом. Для поставщика,
администратора или пользователя без активного объекта верхняя панель может не
показывать объект.

## Объекты и видимость

Объект пользователя хранится в Module №7:

```text
MODULE_07_DIGITAL_HOUSE
```

Module №8 не создает DigitalHouse и не хранит состояние объекта как источник
истины.

Module №8 может хранить или получать через adapter:

- связь кабинета с объектом;
- visibility settings;
- object visibility scope;
- offer visibility settings;
- список связанных объектов;
- настройки уместности объекта в активном кабинете.

Эти данные должны быть ссылками, настройками и контекстом, а не копией
бизнес-данных Module №7.

## Видимость объекта и настройки предложений

Module №8 хранит настройки того, что можно показывать из объектного контекста,
и кому можно отправлять предложения по объекту.

Подготовленные сущности:

- `ObjectVisibilitySettings`;
- `ObjectOfferSettings`.

`ObjectVisibilitySettings` поддерживает:

- показывать объект в подборках;
- показывать регион;
- показывать точный адрес;
- показывать технологию;
- показывать смету;
- показывать закупочную потребность;
- показывать контакты заказчика;
- показывать финансовые данные;
- показывать личные данные.

`ObjectOfferSettings` поддерживает:

- получать предложения от поставщиков;
- получать предложения от строительных компаний;
- получать предложения от специалистов.

Offer-ready слой дополнительно хранит:

- `canSendOffer`;
- `canReceiveOffers`;
- `offer_visibility_enabled`;
- `offer_contact_policy`;
- `offer_source_module`;
- `target_object_id`;
- `target_cabinet_id`.

Настройки должны быть privacy-first:

```text
по умолчанию скрыты точный адрес, контакты, смета,
финансовые данные и личные данные.
```

Включение предложений является opt-in:

```text
по умолчанию объект не принимает предложения,
пока пользователь или разрешенный cabinet workflow явно не включит нужный тип.
```

Ответственность:

```text
MODULE_07_DIGITAL_HOUSE
→ хранит объект и его состояние

MODULE_03_USERS_ROLES
→ проверяет права и scope

MODULE_08_PARTNER_PORTAL
→ хранит visibility / offer settings и кабинетную уместность
```

Module №8 не раскрывает адрес, контакты, смету, закупочную потребность или
финансовые данные только потому, что кабинет связан с объектом.

Module №8 не создает:

- сделку;
- коммерческое предложение;
- закупку;
- marketplace offer;
- переговорку.

Offer-ready поля являются только настройками доступности и видимости. Реальные
бизнес-сущности должны создаваться соответствующими модулями-владельцами данных.

## Связанные объекты

Module №8 поддерживает связь кабинета / участника с объектом через:

- `CabinetObjectLink`;
- `ParticipantObjectAccess`.

Типы связи:

```text
OWNER
INVITED
SUPPLIER_REQUEST
CONTRACTOR_REQUEST
ACTIVE_SUPPLY
ACTIVE_WORK
COMPLETED_DEAL
OFFER_ALLOWED
ARCHIVED
```

Главное правило:

```text
связанный объект не равен объекту во владении;
видимость данных регулируется permissions/visibility.
```

`OWNER` означает связь владельца с объектом. Остальные типы связи описывают
контекст участия:

- приглашение;
- запрос поставщику;
- запрос подрядчику;
- активная поставка;
- активные работы;
- завершенная сделка;
- разрешение на предложение;
- архивная связь.

Module №8 не становится владельцем объекта и не копирует состояние объекта.

Ответственность:

```text
MODULE_07_DIGITAL_HOUSE
→ объект и его состояние

MODULE_03_USERS_ROLES
→ permissions, access level, scope и серверные проверки

MODULE_08_PARTNER_PORTAL
→ relationType, visibilityScope, уместность и кабинетный контекст
```

## Быстрые действия

Module №3 определяет, разрешено ли действие.

Module №8 определяет, уместно ли действие в активном кабинете.

Owning module выполняет бизнес-операцию и обязан проверять `requirePermission()`
на сервере.

Module №8 не выполняет бизнес-операции других модулей напрямую.

## Связь с виджетами

Module №3 регистрирует виджеты и права на них.

Модуль-владелец данных формирует widget payload.

Module №8 может рекомендовать виджеты для активного кабинета и кабинетного
preset, но не должен считать данные виджета сам.

Dashboard только отображает разрешенный и уместный widget payload.

## Dashboard presets

Module №8 может отдавать кабинетные Dashboard presets как рекомендации
рабочего экрана. Эти presets не являются отдельными Dashboard и не создают
новые маршруты главного экрана.

Стартовые presets:

- `CustomerDashboardPreset`;
- `SupplierDashboardPreset`;
- `ConstructionCompanyDashboardPreset`;
- `SpecialistDashboardPreset`;
- `ForemanDashboardPreset`;
- `ProcurementEngineerDashboardPreset`;
- `EstimatorDashboardPreset`;
- `PTOEngineerDashboardPreset`;
- `DesignerDashboardPreset`.

Правила:

- preset содержит только рекомендации по блокам, moduleCode, widgetCode и quickActionCode;
- WidgetRegistry остается в Module №3 / Dashboard layer;
- Module №8 не считает payload виджетов;
- Module №8 не проверяет права сам;
- итоговый preset должен фильтроваться через `AccessContextForCabinet` Module №3;
- если Module №3 не разрешил moduleCode / widgetCode / quickActionCode, Dashboard не должен получать этот элемент как доступный.

## Пользовательская настройка рабочего экрана

Module №8 может хранить кабинетные пользовательские overrides поверх preset:

- `CabinetWidgetPreference`;
- `CabinetModuleShortcut`;
- `CabinetQuickAction`.

Поддерживаемые действия:

- скрыть / показать блок;
- изменить порядок блоков;
- закрепить блок;
- добавить быстрый переход к разрешенному модулю;
- убрать виджет;
- скрыть quick action;
- сбросить настройки к шаблону роли / preset.

Ограничения:

- пользовательская настройка не должна обходить Module №3;
- быстрый переход нельзя добавить к недоступному `moduleCode`;
- виджет нельзя вернуть через preference, если Module №3 / WidgetRegistry его не разрешают;
- reset возвращает filtered preset, а не полный нефильтрованный catalog.

## Запрещено для Module №8

Module №8 не создает и не является источником истины для:

- `Material`;
- `WorkRate`;
- `Estimate`;
- `DigitalHouse`;
- `Procurement`;
- `MarketplaceOffer`.

Границы владения:

```text
Material                 -> MODULE_01_MATERIAL_HUB
WorkRate                 -> MODULE_04_WORKS_COSTS
Estimate                 -> MODULE_05_ESTIMATE_ENGINE
DigitalHouse             -> MODULE_07_DIGITAL_HOUSE
Procurement              -> MODULE_09_PROCUREMENT
MarketplaceOffer         -> MODULE_10_MARKETPLACE
Analytics / PriceDynamic -> MODULE_11_ANALYTICS
```

Module №8 может ссылаться на эти сущности только через DTO, adapter, route,
summary или visibility settings.

## Legacy / conflict note

Старый документ `Module_08_Procurement_v1.0.md` относится к прежней нумерации,
где Module №8 использовался для Procurement.

Актуальный canonical code:

```text
MODULE_08_PARTNER_PORTAL
```

Закупки должны идти через:

```text
MODULE_09_PROCUREMENT
```

Нельзя использовать `MODULE_08_PROCUREMENT` как новый источник логики кабинетов.

## Результат

Module №8 зафиксирован как системный модуль кабинетного контекста:

- определяет активный кабинет и уместность рабочего экрана;
- поддерживает персонализацию Dashboard в рамках прав;
- не заменяет Dashboard;
- не дублирует Module №3;
- не создает бизнес-данные других модулей.
