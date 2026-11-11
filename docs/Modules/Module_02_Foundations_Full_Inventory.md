# M2 Foundations: inventory for the next content sprint

## FND-FINAL: сверка на изолированной копии

Проверенный частичный выпуск применён к рабочей БД: 67 карточек M1 без цен,
15 заблокированных черновиков и 40 прямых ссылок в 13 технологиях. Исходные
действующие редакции и 40 Material Gap сохранены. Ещё 51 профиль M1 не
выпущен из-за отсутствия базовой единицы/конкретного исполнения либо потому,
что представляет общий класс или роль. Никакая технология не объявлена
полностью связанной или готовой к автоматической смете.

Результат пробной подготовки: 15 заблокированных черновиков, 40 исходных потребностей без однозначной безопасной привязки (в том числе из-за различия категорий и составных ролей) и 73 незакрытые роли. Старые потребности сохранены и требуют предметной сверки; записи ниже не подтверждают применимость материала или норму расхода.

### FND_UFF

Исходные потребности:

- CONCRETE: Не совпадают исходный селектор или категория; требуется предметная сверка.
- REBAR: Нужно выбрать класс и диаметр арматуры.
- XPS: Не совпадают исходный селектор или категория; требуется предметная сверка.
- WATERPROOFING: Нужно выбрать систему.

Новые роли:

- FOUNDATION_REBAR (Армирование): Нужно выбрать класс и диаметр арматуры.
- FLOOR_REBAR (Армирование пола): Нужен материал и схема пола.
- FLOOR_XPS (Утепление пола): Нужен выбранный состав пола.
- SEPARATION (Разделительные слои): Нужен состав пола.
- PENETRATIONS (Инженерные проходки): Нужны схема и спецификация вводов.
- WATERPROOFING (Гидроизоляция): Нужно выбрать систему.
- CONCRETE (Бетон): Требуется сверка материала, состава роли и расчётного правила.

### FND_PILE_DRIVEN_RC

Исходные потребности:

- PILE: Не совпадают исходный селектор или категория; требуется предметная сверка.

Новые роли:

- PILE_HEAD (Сопряжение): Нужна система сопряжения.
- CONNECTION_MATERIALS (Материалы соединения): Нужна спецификация соединения.

### FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE

Исходные потребности:

- MEMBRANE: Профиль M1 WPR-03 не входит в подготовленный выпуск.

Новые роли:

- BITUMEN_MEMBRANE (Наплавляемый материал): Нужны раскладка, нахлёсты и совместимость выбранной системы.
- PRIMER (Совместимый праймер): Нужен праймер выбранной системы.
- PENETRATIONS (Герметизация): Нужна совместимость системы.
- JOINTS (Комплектующие системы): Нужны материалы и схема примыканий.
- PROTECTION (Защитный материал): Нужна выбранная система.

### FND_COLUMN_CONCRETE_RC

Исходные потребности:

- CONCRETE: Не совпадают исходный селектор или категория; требуется предметная сверка.
- REBAR: Требуется согласовать составные роли: COLUMN_REBAR, STIRRUPS.

Новые роли:

- SPACERS (Фиксаторы): Нужны тип и раскладка.
- FORMWORK (Опалубочная система): Нужна выбранная система, раскрой, аренда и повторное использование.
- CONCRETE (Бетон): Требуется сверка материала, состава роли и расчётного правила.

### FND_BASEMENT_WALL_MONOLITHIC

Исходные потребности:

- CONCRETE: Не совпадают исходный селектор или категория; требуется предметная сверка.
- REBAR: Требуется согласовать составные роли: OUTER_VERTICAL, OUTER_HORIZONTAL, INNER_VERTICAL, INNER_HORIZONTAL, CORNER_REBAR, OPENING_REBAR, SLAB_JOINT.
- WATERPROOFING: Нужно выбрать систему.

Новые роли:

- CORNER_REBAR (Дополнительное армирование): Нужна деталировка углов.
- OPENING_REBAR (Дополнительное армирование): Нужна деталировка проёмов.
- SLAB_JOINT (Армирование узла): Нужна деталировка сопряжения.
- JOINTS (Материалы швов): Нужна спецификация швов.
- PENETRATIONS (Материалы проходок): Нужна схема проходок.
- SPACERS (Фиксаторы): Нужны защитный слой и раскладка.
- FORMWORK (Опалубочная система): Нужна выбранная система, раскрой, аренда и повторное использование.
- WATERPROOFING (Гидроизоляция): Нужно выбрать систему.
- CONCRETE (Бетон): Требуется сверка материала, состава роли и расчётного правила.

### FND_SUBSTRUCTURE_WATERPROOFING_COATING

Исходные потребности:

- MASTIC: Профиль M1 WPR-01 не входит в подготовленный выпуск.

Новые роли:

- PRIMER (Праймер): Расход системы не подтверждён.
- MASTIC (Мастика): Расход системы не подтверждён.
- JOINT_TAPE (Лента): Нужна геометрия примыканий.
- PROTECTION (Защитный материал): Нужна выбранная система.

### FND_SUBSTRUCTURE_INSULATION_XPS

Исходные потребности:

- XPS: Требуется согласовать составные роли: WALL_XPS, UNDER_SLAB_XPS, EDGE_XPS, NODE_XPS.

Новые роли:

- EDGE_XPS (Теплоизоляция торца): Нужны выбранный материал и геометрия.
- NODE_XPS (Теплоизоляция узлов): Нужны состав и геометрия узлов.
- ATTACHMENT (Крепление или приклеивание): Нужны совместимый способ и материал.
- PROTECTION (Защита утепления): Нужен выбранный материал.

### FND_PILE_BORED_RC

Исходные потребности:

- CONCRETE: Не совпадают исходный селектор или категория; требуется предметная сверка.
- REBAR: Требуется согласовать составные роли: PILE_LONGITUDINAL, STIRRUPS.
- CASING: Зависит от технологии изготовления.

Новые роли:

- SPACERS (Фиксаторы): Нужны тип и раскладка фиксаторов.
- CASING (Обсадные материалы): Зависит от технологии изготовления.
- CONCRETE (Бетон): Требуется сверка материала, состава роли и расчётного правила.

### FND_PILE_SCREW

Исходные потребности:

- PILE: Не совпадают исходный селектор или категория; требуется предметная сверка.

Новые роли:

- CONNECTION (Соединительные элементы): Нужны детали соединения.
- COATING (Защитный состав): Нужен выбранный состав.

### FND_PILE_GRILLAGE

Исходные потребности:

- CONCRETE: Не совпадают исходный селектор или категория; требуется предметная сверка.
- REBAR: Требуется согласовать составные роли: REBAR_TOP, REBAR_BOTTOM, STIRRUPS.

Новые роли:

- PILES (Свайная часть): Нужно выбрать отдельную технологию свай; не учитывать повторно.
- WIRE (Вязальная проволока): Расход не подтверждён.
- SPACERS (Фиксаторы): Нужна раскладка.
- FORMWORK (Опалубочная система): Нужна выбранная система, раскрой, аренда и повторное использование.
- CONCRETE (Бетон): Требуется сверка материала, состава роли и расчётного правила.

### FND_STRIP_MONOLITHIC_RC

Исходные потребности:

- CONCRETE: Не совпадают исходный селектор или категория; требуется предметная сверка.
- REBAR: Требуется согласовать составные роли: REBAR_TOP, REBAR_BOTTOM, STIRRUPS, CORNER_REBAR, JOINT_REBAR.
- FORMWORK: Профиль M1 FORM-01 не входит в подготовленный выпуск.
- WATERPROOFING: Нужно выбрать систему.
- INSULATION: Нужны выбранный материал и зоны.

Новые роли:

- CORNER_REBAR (Дополнительные стержни): Нужны материал и деталировка углов.
- JOINT_REBAR (Дополнительное армирование): Нужны материал и деталировка примыканий.
- WIRE (Вязальная проволока): Расход не подтверждён.
- SPACERS (Фиксаторы): Число и тип уточняются по схеме.
- FORMWORK (Опалубочная система): Нужна выбранная система, раскрой, аренда и повторное использование.
- PREPARATION (Подготовка): Нужен выбранный состав подготовки.
- WATERPROOFING (Гидроизоляция): Нужно выбрать систему.
- INSULATION (Теплоизоляция): Нужны выбранный материал и зоны.
- CONCRETE (Бетон): Требуется сверка материала, состава роли и расчётного правила.

### FND_SLAB_MONOLITHIC_RC

Исходные потребности:

- CONCRETE: Не совпадают исходный селектор или категория; требуется предметная сверка.
- REBAR: Требуется согласовать составные роли: LOWER_X, LOWER_Y, UPPER_X, UPPER_Y, LOCAL_REBAR.
- FORMWORK: Профиль M1 FORM-01 не входит в подготовленный выпуск.
- WATERPROOFING: Нужно выбрать систему.
- INSULATION: Нужны выбранный материал и зоны.

Новые роли:

- LOCAL_REBAR (Локальное усиление): Нужны материал и деталировка.
- SUPPORTS (Поддерживающие элементы): Нужны тип и раскладка.
- SPACERS (Фиксаторы защитного слоя): Нужны защитный слой и схема фиксаторов.
- FORMWORK (Опалубочная система): Нужна выбранная система, раскрой, аренда и повторное использование.
- PREPARATION (Подготовка): Нужен состав слоёв.
- WATERPROOFING (Гидроизоляция): Нужно выбрать систему.
- INSULATION (Теплоизоляция): Нужны выбранный материал и зоны.
- CONCRETE (Бетон): Требуется сверка материала, состава роли и расчётного правила.

### FND_STRIP_PRECAST_FBS_FL

Исходные потребности:

- FBS: Требуется согласовать составные роли: FBS_MAIN, FBS_SHORT, FBS_SHORTER.
- FL: Не совпадают исходный селектор или категория; требуется предметная сверка.
- MORTAR: Не совпадают исходный селектор или категория; требуется предметная сверка.
- WATERPROOFING: Нужно выбрать систему.

Новые роли:

- WATERPROOFING (Гидроизоляция): Нужно выбрать систему.
- FL (Фундаментная плита): Требуется сверка материала, состава роли и расчётного правила.
- MORTAR (Кладочный раствор): Нужна геометрия швов.

### FND_SLAB_RIBBED_RC

Исходные потребности:

- CONCRETE: Требуется согласовать составные роли: SLAB_CONCRETE, RIB_CONCRETE.
- REBAR: Требуется согласовать составные роли: SLAB_LOWER, SLAB_UPPER, RIB_LONGITUDINAL, STIRRUPS, RIB_JOINTS.
- FORMWORK: Нужна выбранная система, раскрой, аренда и повторное использование.

Новые роли:

- RIB_JOINTS (Дополнительное армирование): Нужна деталировка узлов.
- FORMWORK (Опалубочная система): Нужна выбранная система, раскрой, аренда и повторное использование.

### FND_SLAB_USHP

Исходные потребности:

- CONCRETE: Требуется согласовать составные роли: SLAB_CONCRETE, RIB_CONCRETE.
- REBAR: Требуется согласовать составные роли: SLAB_REBAR, RIB_REBAR.
- XPS: Требуется согласовать составные роли: UNDER_SLAB_XPS, EDGE_XPS.
- WATERPROOFING: Нужно выбрать систему.

Новые роли:

- RIB_REBAR (Армирование рёбер): Нужно выбрать класс и диаметр арматуры.
- SAND (Песчаная подготовка): Требуется сверка материала, состава роли и расчётного правила.
- GRAVEL (Щебёночная подготовка): Требуется сверка материала, состава роли и расчётного правила.
- GEOTEXTILE (Разделительный слой): Нужна раскладка и нахлёсты.
- WATERPROOFING (Гидроизоляция): Нужно выбрать систему.
- PENETRATIONS (Гильзы): Требуется сверка материала, состава роли и расчётного правила.
- HEATING (Трубы отопления): Учёт принадлежит выбранной инженерной системе.

## Продолжение: роли и минимальные изменения M1

- Для 40 кодов из прежнего снимка подготовлены предварительные смысловые
  соответствия ролям 15 профилей, включая разбиение общих потребностей на
  несколько ролей. Добавлены условные незаполненные роли утепления ленты и
  гидроизоляции УШП, чтобы не потерять существующие потребности. Сверка не
  переписывает существующие требования, Material Gap, evidence или другие
  ссылки и не является подтверждением готовых связей в рабочей БД.
- В карточке M1 подготовлено отображение имеющихся атрибутов и базовой единицы;
  для текущего серверного фильтра `needs_price` используется название
  «Без цены», отбор по всей базе и существующая таблица. На изолированной БД
  прошли 8 тестов, включая более 500 материалов. HTTP-выдача тестовой БД
  содержит все пять типов проверяемых карточек и 118 строк без цены.
- Свежая копия `backup/fnd-m1-m2-fresh-20261110-175041/buildplatform.dump`
  восстановлена в отдельную БД `houseplatform_fnd_fresh_20261110_175041`.
  Контрольный снимок материалов совпал с live. Dry-run: 118 создано, 330
  архивировано, 0 переиспользовано; второй запуск ничего не создал; 19 связанных
  таблиц не изменились. Оба прогона откатились: production не изменялась.
- Повторный комбинированный dry-run после защиты вложенных JSON-ссылок M2:
  118 созданных, 0 переиспользованных, 330 архивированных и 2 защищённых
  материала; 15 заблокированных черновых редакций, 16 однозначных связей
  исходных потребностей, 24 потребности без такой прямой замены, 51 новая и
  8 переиспользованных ролей. Созданы 96 черновых правил, 69 новых и 16
  обновлённых допущений; 46 позиций остались незакрытыми. Результаты относятся
  к откатанной транзакции, не к production; 40 Material Gap сохранены.
- В существующий M2 → M5 контракт подготовлена передача состава по стабильным
  идентификаторам; пакет явно блокируется для автоматического расчёта до
  поддержки распределения ролей. Черновики не активированы.
- После последних изменений локально: 95 passed, 4 skipped; отдельный запуск
  на изолированной PostgreSQL: 39 passed. Регресс на восстановленной копии:
  1669 passed, 28 skipped, 2 deselected; отдельно 16 тестов переносимости
  прошли в `/tmp` контейнера HousePlatform. Два исключения читают локальный
  `.env.docker` и не выполнялись из-за запрета ручного чтения секретов.
  Связывание в рабочей БД, visual smoke, deploy и push не выполнены.

## FND-M1-M2-INTEGRATION: продолжение 10.11.2026

- Подготовлены 118 технических позиций M1 и предварительные профили для всех
  15 технологий. Это предложения в коде, не новые записи рабочей базы и не
  подтверждение применимости материалов или безопасности конструкций.
- Добавлены проверяемые математические операции для заданной геометрии,
  количества элементов, арматуры, опалубки и материалов. Нахлёсты считаются
  только по явно указанным длинам стыков: нормативная длина не назначается.
  Не суммировать припуск повторно, если он уже включён в длины стержней.
- Предлагаемые связи и правила не опубликованы. Существующие обобщённые роли,
  связанные элементы, источники и Material Gap нужно согласовать с новыми
  ролями без дублирования или потери истории; готовность к M5 не объявлена.
  В восстановленной копии из 40 существующих кодов потребностей 20 совпали с
  кодами предложений, 20 не совпали; совпадение кода само по себе не доказывает
  совпадение смысла. Добавлен read-only аудит расхождений без изменения связей.
- На ранее восстановленной копии пакет проверен в транзакции с откатом,
  включая повторный запуск и сохранение связанных записей. Копия уже содержала
  результаты прежнего пробного запуска 18 позиций: это не проверка выпуска на
  новой копии актуальной рабочей БД и не применение 118 позиций в production.
- Очереди поиска и обновления цен пока представлены только чтением имеющихся
  записей; новых товаров, цен, заданий и парсинга они не создают. На прежней
  тестовой копии: 18 позиций на поиск, 0 известных цен для обновления.
- Локальные целевые проверки: 80 passed, 2 skipped до последних доработок
  и затем 60 passed по затронутой логике; на изолированной PostgreSQL:
  16 passed. Полный
  регресс после всех изменений и визуальный выпускной smoke не подтверждены.

## FND-M1-M2-INTEGRATION: промежуточная проверка 10.11.2026

Проверено сохранение составных инженерных записей и ссылок на источники при
создании черновой редакции: все 15 активных технологий из восстановленной
копии прошли проверку переноса и отката. Историческая активная редакция при
этом не изменялась. Отдельно проверяются права утверждения и доказательная база.

Тестовый M1-сбор пользователь разрешил очистить. На изолированной копии
обратимо архивированы 331 неподтверждённая карточка и созданы 18 технических
черновиков бетона и арматуры без цен и предложений. Повторный запуск не создал
дублей, 26 связанных таблиц сохранили контрольные суммы. Это не выпуск в рабочую
базу и не завершение номенклатуры: остальные типы материалов, проверенные
сопоставления 40 потребностей и очереди цен ещё не закрыты.

У технологий по-прежнему нет подтверждённых активных норм расхода. Не считать
ширину ленты единственным основанием выбора армирования, не назначать длину
нахлёста или запреты для класса бетона без проверенных источников, области
применения и проектных параметров. M5, M7 и M9 не реализовывались.

## Audit update: M2-FOUNDATIONS-FULL + M1

On 2026-11-10 the live read-only audit confirmed all 15 active technologies and
six families listed below. There are still 40 existing Material Gaps, each
linked to an existing M1 acquisition task. Applying the existing compatible
VERIFIED-material lookup to all 40 requirements found zero candidates. No
material, product, offer, price, new gap, task, technology revision, engineering
norm or business data was created or altered by this audit.

For each of the 15 technologies the counts in the table remain an inventory,
not an editorial or engineering completeness certification. Detailed articles,
verified source-to-claim review, suitable M1 materials, justified consumption
norms and estimate-ready M2-to-M5 inputs remain incomplete. Treat the whole
content package as PARTIAL / IN_PROGRESS, even where older category metadata
says CONTENT_COMPLETE. Technology-specific engineering drawings are not
established by the category illustrations.

The existing node connecting driven piles to PREPARATION describes preparation
of their worksite. It is a cross-category relationship, not membership in that
category; the public presentation identifies the source family and relation.
All 16 published roots and six foundation families were checked for own versus
related active technologies and circular public breadcrumbs.

The comparison now resolves published foundation technologies from the M2
catalog and presents selectable alternatives and scenario-prioritized criteria.
It is informational and does not imply suitability or price ranking. FEMA P-749
is background on shallow/deep foundation principles, and US Department of
Energy guidance is background on slab-edge insulation; neither is presented as
a Russian design norm. No numeric engineering norms were imported from them.

The M1 normalizer now recognizes Cyrillic concrete class designations and the
diameter symbols used for rebar. Matching still reports conflicting classes or
diameters and does not merge them automatically. The 209-item REF6 and its
existing three-item extension remain unchanged. Default resolution remains
USER_OVERRIDE > PROJECT_VALUE > M2_DEFAULT; no M5 or M7 implementation was added.

Read-only snapshot of HousePlatform on 2026-11-09. The counts below describe
stored links and records, not engineering approval or estimation readiness.
No catalogue, content, lifecycle, or production data were changed by this audit.

The root `FOUNDATIONS` and all six families are ACTIVE: `STRIP_FOUNDATIONS`,
`SLAB_FOUNDATIONS`, `PILE_FOUNDATIONS`, `PILE_GRILLAGE_FOUNDATIONS`,
`COLUMN_FOUNDATIONS`, and `BASEMENT_AND_SUBSTRUCTURE`. Each is marked
`CONTENT_COMPLETE`; this describes the agreed editorial inventory, not a
verified estimate-ready system. The 15 technologies below are ACTIVE and their
active category makes them eligible for the existing public article route.

| Technology | Layers | M1 requirements | Concrete M1 links | Open gaps | Active defaults | Work steps | Active norms | Active rules | Nodes | Evidence links |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Basement wall | 3 | 3 | 0 | 3 | 8 | 3 | 0 | 7 | 2 | 19 |
| Column | 2 | 2 | 0 | 2 | 7 | 3 | 0 | 7 | 1 | 16 |
| Bored RC piles | 3 | 3 | 0 | 3 | 8 | 3 | 0 | 7 | 2 | 19 |
| Driven RC piles | 1 | 1 | 0 | 1 | 2 | 1 | 0 | 7 | 3 | 15 |
| Pile grillage | 2 | 2 | 0 | 2 | 7 | 1 | 0 | 7 | 1 | 14 |
| Screw piles | 1 | 1 | 0 | 1 | 3 | 1 | 0 | 7 | 2 | 13 |
| Monolithic slab | 5 | 5 | 0 | 5 | 9 | 6 | 0 | 7 | 2 | 29 |
| Ribbed slab | 3 | 3 | 0 | 3 | 8 | 3 | 0 | 7 | 3 | 21 |
| Insulated Swedish slab (USHP) | 4 | 4 | 0 | 4 | 8 | 4 | 0 | 7 | 5 | 26 |
| Monolithic strip | 5 | 5 | 0 | 5 | 10 | 6 | 0 | 7 | 3 | 30 |
| FBS/FL strip | 4 | 4 | 0 | 4 | 6 | 3 | 0 | 7 | 4 | 24 |
| Underground XPS | 1 | 1 | 0 | 1 | 2 | 1 | 0 | 7 | 1 | 12 |
| Coating waterproofing | 1 | 1 | 0 | 1 | 2 | 1 | 0 | 7 | 2 | 13 |
| Membrane waterproofing | 1 | 1 | 0 | 1 | 2 | 1 | 0 | 7 | 4 | 16 |
| Insulated Finnish foundation (UFF) | 4 | 4 | 0 | 4 | 8 | 4 | 0 | 7 | 5 | 26 |

Open gaps include `OPEN`, `REVIEWING`, and `SEARCH_REQUESTED`. Evidence counts
are references, not a claim that every reference has been independently
verified. Node counts include both construction nodes and relationship nodes.
No technology-specific published images were established by this audit; the
module-home house image is not evidence of a construction detail.

Existing related-category links: driven piles to preparation; USHP to floors,
heating and water/sewer; FBS/FL to the basement family; membrane waterproofing
to site works; UFF to floors, heating, site works and water/sewer. Existing
related-technology links connect driven piles to the grillage and the ribbed
slab to USHP. Public links are resolved by the existing encyclopedia service.

The M1 work catalogue remains canonical. Its current code-level effective list
has 212 works: the 209-item REF6 baseline plus the existing approved extension.
It is file-based, not an independently maintained M2 or database catalogue.

## Next sprint checklist

- Review educational article completeness separately for each technology,
  including applicability, limitations, quality control and source clarity.
- Resolve each open material gap against a genuinely compatible M1 card; do not
  create placeholder materials or substitute a category for a selected item.
- Review each default's applicability, unit, source and version; defaults are
  preliminary platform assumptions unless separately evidence-backed.
- Establish consumption norms only where a traceable engineering source and
  scope justify them. All 15 have zero active norms in this snapshot.
- Audit work sequence, M1 work codes, dependencies and controls; do not invent
  quantities or replace missing norms with 1.0.
- Verify evidence links and their precise scope, not merely their count.
- Review construction and relationship nodes and the need for documented
  category/technology links; do not duplicate M1 work or material catalogues.
- Review article-specific illustrations separately; do not present conceptual
  house imagery as a dimensionally accurate engineering drawing.
- Re-evaluate M2-to-M5 readiness from its structured blockers after resolving
  the above. A published article or `CONTENT_COMPLETE` is not M5 readiness.
