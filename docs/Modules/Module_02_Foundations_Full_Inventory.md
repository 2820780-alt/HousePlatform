# M2 Foundations: inventory for the next content sprint

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
  на изолированной PostgreSQL: 39 passed. Полный регресс, фактическое
  связывание ролей в рабочей БД, visual smoke, deploy и push не выполнены.
  Отдельно 16 тестов переносимости прошли в `/tmp` контейнера HousePlatform.

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
