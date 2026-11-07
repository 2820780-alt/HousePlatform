# Module 2 / Technology Catalog and Construction Encyclopedia

Status: M2 Core and Encyclopedia infrastructure COMPLETED. Residential top-level
taxonomy v1 is product-approved. FOUNDATIONS is IN_PROGRESS. M2-FOUNDATIONS-1
adds three source-scoped ACTIVE technologies and one blocked DRAFT candidate;
neither STRIP nor SLAB is marked CONTENT_COMPLETE yet.

## Purpose and ownership

One engineering knowledge source has two views: the M2 Technology Workbench for
curation and a read-only Construction Encyclopedia for HousePlatform users. The
Encyclopedia derives technology composition, work order, requirements, norms,
rules, nodes and evidence from the same versioned M2 aggregate. It must not
maintain a parallel manually copied technology article.

M1 owns materials, material categories, documents, resources and Work Catalog.
M2 stores references to those entities and owns engineering interpretation.
M5 calculations and M7 object geometry remain outside this contour. No M9
supplier or price workflow is introduced.

## Existing classification audit

- `Technology.technology_code` is the stable technology identity; `revision`
  identifies an immutable publication version. `system_code` is an optional flat
  classification hint, not a category tree.
- `MaterialCategory`, `MaterialType`, `ConstructionGroup` and
  `ClassificationRule` classify M1 materials or matching rules. Reusing them as
  an M2 technology taxonomy would mix separate ownership and dimensions.
- `TechnologyLayer`, `TechnologyMaterialRequirement`, `TechnologyWorkStep`,
  `TechnologyNode`, `ConsumptionNorm`, `CompatibilityRule`, `KnowledgeRule` and
  `TechnologyEvidenceReference` already provide the structured article source.
- `TechnologyWorkStep.position` preserves the how-to order and `work_code`
  resolves through the read-only M1 Work Catalog. Neither sequence nor a work
  directory should be duplicated in editorial content.

## Minimal canonical taxonomy

The proposed `TechnologyCategory` is M2-owned. It has an immutable uppercase
ASCII `code`, editable display `name` and `description`, optional `parent_id`,
nonnegative `sort_order`, extensible `scope_code`, lifecycle `DRAFT` / `ACTIVE` /
`ARCHIVED`, and content readiness `EMPTY` / `IN_PROGRESS` /
`CONTENT_COMPLETE`. The parent tree represents navigation only. Constructive
family, installation method, material, depth and other technical dimensions
remain Technology attributes or engineering conditions; they are not forced
into sibling categories.

`Technology.category_id` is optional for legacy drafts, copied to new revisions.
It references this M2 taxonomy, never `MaterialCategory`. A technology may be
edited without a category, but publication in the Encyclopedia requires an
ACTIVE category and ACTIVE ancestors. One public URL resolves the latest ACTIVE
revision by `technology_code`; a DRAFT revision never replaces a public ACTIVE
one. Category and technology codes are URL identities; display names may change.
The product owner approved the 16 top-level rows below for the residential scope.
The six FOUNDATIONS children are navigation families derived from its inventory.

Category lifecycle is independent of content completeness. Only an approver may
activate a category after taxonomy approval. Archiving must not strand active
child categories or published technologies. `CONTENT_COMPLETE` must be earned
through the section gate below, never seeded or inferred from a nonempty list.

## Encyclopedia projection

Proposed HousePlatform routes are `/api/v1/module2/encyclopedia`,
`/categories/{category_code}` and `/technologies/{technology_code}`. Reader
access requires an authenticated user with M2 VIEW (including LIMITED scope);
all editorial changes stay in the Workbench with existing M2 RBAC and CSRF.
The landing page shows active category hierarchy, search and a truthful empty
state. Category pages show breadcrumbs, active child categories and current
ACTIVE technologies. A Technology page presents purpose/applicability, layers,
M1 material requirements, ordered steps, norms, nodes, compatibility, warnings,
quality notes and evidence, omitting absent sections instead of inventing them.
It never exposes raw JSON or database IDs.

Page concepts map to canonical entities rather than ten new tables:

| Page concept | Canonical source / intended link |
| --- | --- |
| Category | M2 TechnologyCategory code and parent tree |
| Technology / construction system | ACTIVE Technology code and revision |
| Work / how-to | M1 work_code referenced by ordered TechnologyWorkStep |
| Node / detail | TechnologyNode.code within Technology.code |
| Material in application | TechnologyMaterialRequirement.code, resolving M1 material or class |
| Defect / common error | Evidence-backed M2 KnowledgeRule warning/prohibition, scoped to Technology |
| Glossary / instruction / comparison | Future reviewed editorial blocks referencing canonical entity codes; no independent engineering facts |

Internal links use category, technology, work, node or requirement codes. A
missing or archived target is shown as unavailable rather than linked to a raw
UUID. M1 documents remain in M1; the Encyclopedia displays verified reference
titles and source links only when the source is accessible and safe to expose.
Related technologies come from explicit M2 relations when curated, not
automatically guessed from similar names or material categories.

Search v1 can cover active category names/codes and current ACTIVE technology
names/codes. Aliases and glossary terms need a reviewed editorial model before
they are indexed. No separate search service is needed for the initial catalog.

## Content packages and completeness

The first content package starts only after the product owner approves the
complete residential taxonomy. That approval now exists for v1, and FOUNDATIONS
is IN_PROGRESS. Packages may close one category at a time:

1. Record the approved category scope and expected technology inventory.
2. Create DRAFT technologies from verified sources, preserving M1 material,
   work and evidence references. Avoid isolated examples from random sections.
3. Review applicability, layers, work order, nodes, norms, rules and common
   errors; every claim requiring evidence links to an M1 document/resource.
4. Activate only validated technologies; explain every DRAFT/BLOCKED entry.
5. Audit missing technologies, broken links, publication visibility and reader
   coverage before marking the category CONTENT_COMPLETE.

EMPTY means no approved content package. IN_PROGRESS means the approved scope
is being filled. CONTENT_COMPLETE requires all five gates above plus explicit
review of the expected inventory; a count alone is insufficient. M2 Core status
does not change when content remains incomplete.

## Approved residential taxonomy v1

Scope: private-house construction and reconstruction, apartment repair, interior
finishing, domestic engineering systems and directly related site works. Industrial,
bridge/tunnel, special high-rise, city-utility and rare deep-foundation systems are
not part of v1. The taxonomy remains extensible.

| Order | Stable code | Display name | Taxonomy | Content |
| ---: | --- | --- | --- | --- |
| 10 | `PREPARATION` | Подготовка и демонтаж | ACTIVE | EMPTY |
| 20 | `FOUNDATIONS` | Фундаменты и подземная часть | ACTIVE | IN_PROGRESS |
| 30 | `WALLS` | Стены и несущий каркас | ACTIVE | EMPTY |
| 40 | `PARTITIONS` | Перегородки | ACTIVE | EMPTY |
| 50 | `FLOORS_AND_STAIRS` | Перекрытия, полы по грунту и лестницы | ACTIVE | EMPTY |
| 60 | `ROOF` | Крыша, кровля и водосток | ACTIVE | EMPTY |
| 70 | `FACADE_AND_OPENINGS` | Фасад, окна и наружные двери | ACTIVE | EMPTY |
| 80 | `SITE_WORKS` | Работы вокруг дома | ACTIVE | EMPTY |
| 90 | `INTERIOR_ROUGH` | Черновая внутренняя отделка | ACTIVE | EMPTY |
| 100 | `INTERIOR_FINISH` | Чистовая отделка | ACTIVE | EMPTY |
| 110 | `WATER_AND_SEWER` | Водоснабжение и канализация | ACTIVE | EMPTY |
| 120 | `HEATING_AND_DHW` | Отопление и горячая вода | ACTIVE | EMPTY |
| 130 | `VENTILATION_AND_AC` | Вентиляция и кондиционирование | ACTIVE | EMPTY |
| 140 | `ELECTRICAL_AND_AUTOMATION` | Электрика, слаботочка и умный дом | ACTIVE | EMPTY |
| 150 | `GAS_AND_COMBUSTION` | Газ, дымоходы, печи и камины | ACTIVE | EMPTY |
| 160 | `FINAL_INSTALLATION` | Финальное оснащение | ACTIVE | EMPTY |

All are root categories with `parent_id = NULL`, `scope_code = RESIDENTIAL`.
Codes are uppercase ASCII URL identities. They do not change with display names.
Category answers **which part of construction** owns a Technology. Monolithic,
precast, wood, reinforced concrete, external/internal, structural/nonstructural,
waterproofing, insulation, new build, reconstruction, apartment and house are
attributes or applicability facets unless a stable system family needs navigation.
No generic facet engine is introduced in this sprint.

### FOUNDATIONS tree and boundary

`FOUNDATIONS` (Фундаменты и подземная часть) contains:

| Order | Child code | Navigation family | Content |
| ---: | --- | --- | --- |
| 10 | `STRIP_FOUNDATIONS` | Ленточные фундаменты | EMPTY |
| 20 | `SLAB_FOUNDATIONS` | Плитные фундаменты | EMPTY |
| 30 | `PILE_FOUNDATIONS` | Свайные основания | EMPTY |
| 40 | `PILE_GRILLAGE_FOUNDATIONS` | Свайно-ростверковые системы | EMPTY |
| 50 | `COLUMN_FOUNDATIONS` | Столбчатые фундаменты | EMPTY |
| 60 | `BASEMENT_AND_SUBSTRUCTURE` | Подвал, цоколь и подземные конструкции | EMPTY |

The pile-grillage family is separate navigation because the assembled system is
not the same article as a pile type; it does not imply a Technology for every
pile/grillage combination. UFF is a cross-boundary candidate under the strip
family, linked to floors on ground, not a seventh family. Basement walls and
substructure protection share one navigation family without turning every layer
into a standalone Technology. There is no third taxonomy level yet.

Earthworks belong to `PREPARATION`; site drainage, rainwater diversion and
blind areas belong to `SITE_WORKS`; standalone floors on ground belong to
`FLOORS_AND_STAIRS`. Future Technology pages should link across these codes,
not duplicate those systems under FOUNDATIONS. No M7 geometry, M5 quantity or
estimate, or M9 supplier/price data is implied.

### FOUNDATIONS inventory v1

Inventory codes below are document keys, **not** published Technology codes.
`Y` means in the proposed product scope, `N` means outside it, `?` means the
applicability needs source review. `R` = READY_FOR_RESEARCH, `B` =
NEEDS_BOUNDARY_REVIEW, `O` = OUT_OF_SCOPE as a standalone FOUNDATIONS Technology.
These are proposed inventory statuses, not database lifecycle values.

| Inventory code | Name / family | Proposed Technology boundary | Typical residential use | HOUSE / APARTMENT / NEW_BUILD / RECONSTRUCTION | Parameter or separate decision | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `FND_STRIP_MONOLITHIC_RC` | Монолитная ЖБ лента / STRIP | One system Technology candidate | House foundation | Y/N/Y/? | Separate from precast; depth/footing geometry are parameters | R |
| `FND_STRIP_PRECAST_FBS_FL` | Сборная лента ФБС/ФЛ / STRIP | One candidate only where verified applicable | House foundation or basement-wall assembly | Y/N/Y/? | Separate construction sequence; verify foundation vs wall role of blocks | B |
| `FND_STRIP_GEOMETRY_VARIANTS` | Мелко-/заглубление, уширение / STRIP | No separate Technology by default | Strip design variants | Y/N/Y/? | Parameters unless evidence proves a distinct system/work sequence | B |
| `FND_SLAB_MONOLITHIC_RC` | Монолитная плита / SLAB | One system Technology candidate | House foundation | Y/N/Y/? | Separate from ribbed/insulated assemblies | R |
| `FND_SLAB_RIBBED_RC` | Ребристая плита / SLAB | Candidate; compare work/layer sequence | House foundation | Y/N/Y/? | Separate only if distinct validated system, not merely a drawing option | B |
| `FND_SLAB_RIB_ORIENTATION` | Ребра вверх/вниз / SLAB | No separate Technology by default | Ribbed-slab variants | Y/N/Y/? | Variant/parameter pending evidence | B |
| `FND_SLAB_USHP` | УШП / SLAB | Integrated system candidate | Insulated house foundation | Y/N/Y/? | Potential separate system; link floor/heating rather than duplicate them | B |
| `FND_UFF` | УФФ / STRIP + cross-link | Composition candidate | Insulated house foundation/floor junction | Y/N/Y/? | Decide composition of linked systems vs standalone Technology | B |
| `FND_PILE_DRIVEN_RC` | Забивные ЖБ сваи / PILE | Pile-system Technology candidate | House foundation where designed | Y/N/Y/? | Separate method; dimensions/soil are parameters, not taxonomy | R |
| `FND_PILE_BORED_RC` | Буронабивные сваи / PILE | Pile-system Technology candidate | House foundation where designed | Y/N/Y/? | Separate method; execution variants need evidence | R |
| `FND_PILE_SCREW` | Винтовые сваи / PILE | Pile-system Technology candidate | House/light structures where designed | Y/N/Y/? | Separate method; coating/size are requirements or parameters | R |
| `FND_PILE_GRILLAGE` | Свайно-ростверковая система / PILE_GRILLAGE | One assembled-system candidate | House foundation | Y/N/Y/? | Pile/grillage materials are requirements/variants, not combinatorial technologies | R |
| `FND_COLUMN_CONCRETE_RC` | Бетонные/ЖБ столбы / COLUMN | One scoped candidate | Light residential or auxiliary structures | Y/N/Y/? | Material/reinforcement variant; exact structural scope needs review | B |
| `FND_BASEMENT_WALL_MONOLITHIC` | Монолитные стены подвала / SUBSTRUCTURE | Wall-system candidate | House basement | Y/N/Y/? | Separate from precast wall sequence | R |
| `FND_BASEMENT_WALL_PRECAST` | Сборные стены подвала / SUBSTRUCTURE | Wall-system candidate | House basement | Y/N/Y/? | Separate if documented; avoid duplicate FBS/FL strip facts | B |
| `FND_PLINTH_WALL` | Стена цоколя / SUBSTRUCTURE | Candidate or basement-wall variant | House plinth | Y/N/Y/? | Decide by verified work/structural boundary | B |
| `FND_FOUNDATION_BEAM` | Фундаментная балка / SUBSTRUCTURE | Element or system candidate | Residential frame where applicable | Y/N/Y/? | Separate only if residential use and sequence are evidenced | B |
| `FND_SUBSTRUCTURE_WATERPROOFING` | Гидроизоляция подземной части / SUBSTRUCTURE | Linked system/layers candidate | Foundation/basement protection | Y/N/Y/? | Separate only when own validated work system; otherwise layer | B |
| `FND_SUBSTRUCTURE_INSULATION` | Теплоизоляция подземной части / SUBSTRUCTURE | Linked system/layers candidate | Foundation/basement insulation | Y/N/Y/? | Separate only when own validated work system; otherwise layer | B |
| `FND_WATERPROOFING_PROTECTION` | Защита гидроизоляции / SUBSTRUCTURE | Layer/node, not standalone by default | Protective assembly | Y/N/Y/? | Detail or layer of linked waterproofing system | O |
| `FND_UTILITY_PENETRATION` | Вводы коммуникаций / SUBSTRUCTURE | Node/detail, not standalone | Foundation penetration | Y/N/Y/? | TechnologyNode linked to system and M2/M1 references | O |

No row asserts load capacity, footing geometry, concrete grade, reinforcement
quantity, soil parameters, material consumption or required dimension. Those
belong to later evidence-backed Technology content and project-specific design.
Future M7 may reference `TechnologyCategory.code` and
`Technology.technology_code` as stable public identifiers; no M7 schema or
object-specific geometry is introduced here.

### M1 reference and evidence readiness per item

Required material labels below are **types to resolve later** to VERIFIED M1
records/classes, not invented M1 IDs. `W` aliases resolve to exact existing M1
Work Catalog codes in the next section. No M1 evidence is considered verified
for these engineering claims at this audit point.

| Inventory code | Required M1 material types | Existing work aliases | Evidence to collect | Known gap |
| --- | --- | --- | --- | --- |
| `FND_STRIP_MONOLITHIC_RC` | Concrete, reinforcement, formwork, waterproofing | W1 W6 W8 W9 W10 | Design/sequence and applicability sources | No verified materials or direct foundation evidence |
| `FND_STRIP_PRECAST_FBS_FL` | FBS/FL, mortar, joints, waterproofing | W10 | Block/slab applicability and assembly sources | FBS/FL materials and dedicated installation work missing |
| `FND_STRIP_GEOMETRY_VARIANTS` | Parent strip requirements | W1 | Evidence distinguishing variant from system | Boundary unreviewed; no design parameters |
| `FND_SLAB_MONOLITHIC_RC` | Concrete, reinforcement, formwork, waterproofing | W2 W7 W8 W9 W10 | Slab design/sequence sources | No verified materials or direct evidence |
| `FND_SLAB_RIBBED_RC` | Concrete, reinforcement, formwork | W2 W7 W8 W9 | Ribbed-slab sequence and applicability | No distinct work code or evidence |
| `FND_SLAB_RIB_ORIENTATION` | Parent slab requirements | W2 | Variant comparison evidence | Boundary unreviewed |
| `FND_SLAB_USHP` | Concrete, reinforcement, insulation, linked service components | W2 W7 W9 W11 | Integrated-system sources | No dedicated work or source package |
| `FND_UFF` | Strip materials, insulation, floor-system materials | W1 W11 | Composition and interface sources | Cross-category Technology boundary open |
| `FND_PILE_DRIVEN_RC` | Driven RC piles, joints/protection | none | Pile design and installation sources | No dedicated installation work/material |
| `FND_PILE_BORED_RC` | Concrete, reinforcement, casing where relevant | W5 W6 W9 | Bored-pile sequence/applicability | No dedicated full pile work/evidence |
| `FND_PILE_SCREW` | Screw piles, protective systems | W4 | Pile specification and installation | No verified pile material/evidence |
| `FND_PILE_GRILLAGE` | Piles, concrete/reinforcement or reviewed grillage material | W3 W6 W8 W9 | Assembled-system and connection sources | Combination boundary/evidence missing |
| `FND_COLUMN_CONCRETE_RC` | Concrete, reinforcement, formwork | W6 W8 W9 | Light-structure applicability and sequence | No dedicated column-foundation work |
| `FND_BASEMENT_WALL_MONOLITHIC` | Concrete, reinforcement, formwork, waterproofing | W6 W8 W9 W10 | Basement-wall assembly/protection sources | No dedicated wall work/evidence |
| `FND_BASEMENT_WALL_PRECAST` | FBS blocks, mortar, joints, waterproofing | W10 | Precast basement-wall sources | No dedicated FBS installation work/evidence |
| `FND_PLINTH_WALL` | Wall material, waterproofing | W10 | Plinth-vs-basement boundary sources | Material and work mapping unresolved |
| `FND_FOUNDATION_BEAM` | Beam material, bearing/joint components | W9 | Residential applicability and connection sources | No dedicated beam work/evidence |
| `FND_SUBSTRUCTURE_WATERPROOFING` | Waterproofing materials, primers, protection | W10 | System/product instructions and constraints | M1 matching records archived/unverified |
| `FND_SUBSTRUCTURE_INSULATION` | Insulation, fixation/protection | W11 | System/product instructions and constraints | M1 matching records archived/unverified |
| `FND_WATERPROOFING_PROTECTION` | Protection materials | W10 | Detail/product evidence | Model as layer/node after source review |
| `FND_UTILITY_PENETRATION` | Sleeve, seal, waterproofing components | none | Penetration-node detail evidence | No dedicated node/work source |

### M1 Work Catalog audit

Exact existing codes (`src/modules/module1/seeds/work_catalog_seed.json`):

| Alias | Existing `work_code` | Role |
| --- | --- | --- |
| W1 | `foundations_concrete_ustroystvo_lentochnogo_fundamenta` | Strip system |
| W2 | `foundations_concrete_ustroystvo_plitnogo_fundamenta` | Slab system |
| W3 | `foundations_concrete_ustroystvo_svayno_rostverkovogo_fundamenta` | Pile-grillage system |
| W4 | `foundations_concrete_montazh_vintovyh_svay` | Screw piles |
| W5 | `foundations_concrete_burenie_pod_svai` | Boring |
| W6 | `reinforcement_armirovanie_fundamenta` | Reinforcement |
| W7 | `reinforcement_armirovanie_plity` | Slab reinforcement |
| W8 | `foundations_concrete_montazh_opalubki_fundamenta` | Foundation formwork |
| W9 | `foundations_concrete_betonirovanie_konstrukciy` | Concrete placement |
| W10 | `foundations_concrete_gidroizolyaciya_fundamenta` | Waterproofing |
| W11 | `foundations_concrete_uteplenie_fundamenta` | Insulation |

Also available: `foundations_concrete_ustroystvo_podbetonki`,
`foundations_concrete_demontazh_opalubki`,
`foundations_concrete_vibrirovanie_betona`,
`reinforcement_vyazka_armaturnogo_karkasa` and
`reinforcement_montazh_armaturnoy_setki`. Earthworks codes remain with
`PREPARATION`; `landscaping_ustroystvo_drenazha_uchastka` and
`landscaping_ustroystvo_otmostki` belong to `SITE_WORKS` despite older
foundation-named work items for blind areas. Gaps: dedicated FBS/FL assembly,
driven piles, column foundations, basement walls and integrated UFF/USHP work.
The taxonomy-only sprint did not invent M2 work codes or mutate M1.

### Read-only evidence audit and research leads

Live M1 snapshot before seed: 394 materials (1 VERIFIED, none matching the
foundation-related name search), 298 material specifications, 0 attributes,
31 ACTIVE material documents and 31 ACTIVE knowledge resources. A title search
for foundation/pile/waterproofing/reinforcement returned 0 direct documents or
resources. The 37 broad material-name matches include AUTO_CREATED gas-concrete
blocks and ARCHIVED waterproofing/insulation records; they are **not** approved
FOUNDATIONS evidence. No separate `technical_cards` table exists in the current
ORM; material specifications must be reviewed with their parent material status.

Official standards are research leads, not ingested/verified M1 evidence:
[SP 22.13330.2016](https://protect.gost.ru/sp/details/71e96332-a446-4a15-87a0-2db895479f61),
[SP 24.13330.2021](https://protect.gost.ru/sp/details/1e90a34c-6379-4236-8256-38be93e29766),
[GOST 13579-2018](https://protect.gost.ru/gost/details/590002ea-b5b0-4bf5-9e47-a772c8c16f06).
Their current text, amendments, applicability and engineering interpretation
must be reviewed during content filling before any claims enter Technology.

### M2-FOUNDATIONS-1 content package

`database/migrations/20261107_module02_foundations_content.sql` is an
idempotent, transactional content seed, not schema DDL. It adds 11 scoped M1
knowledge resources, eight M1 material classes and eight class-source links, and
four M2 Technology revisions. The approved M1 Work Catalog and REF6 artifact
remain unchanged at 209 work codes. The precast sequence uses the existing
`foundations_concrete_ustroystvo_lentochnogo_fundamenta` code for assembly;
dedicated FL/FBS montage codes remain a documented M1 gap. No M1 material
product, price, supplier, calculated quantity or object geometry is
created. M2 requirements refer to M1 classes, not cloned products.

| Inventory key | Published code / boundary | Lifecycle | Family |
| --- | --- | --- | --- |
| `FND_STRIP_MONOLITHIC_RC` | Same; one monolithic RC strip system | ACTIVE | STRIP |
| `FND_STRIP_PRECAST_FBS_FL` | Same; FBS system, FL conditional by project | ACTIVE | STRIP |
| `FND_STRIP_GEOMETRY_VARIANTS` | Depth, width and footing geometry are calculated parameters, not Technology | No record | STRIP |
| `FND_SLAB_MONOLITHIC_RC` | Same; one monolithic RC slab system | ACTIVE | SLAB |
| `FND_SLAB_RIBBED_RC` | Distinct-system candidate, not an approved Russian residential recipe | DRAFT/BLOCKED | SLAB |
| `FND_SLAB_RIB_ORIENTATION` | Orientation is a design parameter of the ribbed candidate, not Technology | No record | SLAB |

The precast boundary follows the official [GOST 13579-2018](https://protect.gost.ru/gost/details/590002ea-b5b0-4bf5-9e47-a772c8c16f06)
scope: solid basement-wall blocks may be used in foundations. The official
[GOST 13580-2021](https://protect.gost.ru/gost/details/ae76fad3-1e46-4c89-af7a-1a4c6e9617c3)
covers precast strip-footing slabs, but does not make FL a universal necessity.
Project design determines the assembly and its joints. The [ribbed-raft
research](https://eijest.journals.ekb.eg/article_153965_5030d71d83e7b78838464cc5c4a4efd3.pdf)
demonstrates a structurally distinct waffle/rib system under particular
expansive-soil assumptions; its Egyptian design parameters cannot be copied
into Russian private-house practice. The ribbed candidate remains DRAFT with
explicit applicability and work-sequence blockers. Rib orientation remains a
variant of that candidate.

Evidence in M1 is scoped rather than generically marked as a verified design
recipe. Current registry cards establish status and scope of
[SP 22.13330.2016](https://protect.gost.ru/sp/details/71e96332-a446-4a15-87a0-2db895479f61),
[SP 63.13330.2018](https://protect.gost.ru/sp/details/8b67e228-0c9f-4a62-b562-964b3a58c667),
[SP 70.13330.2012](https://protect.gost.ru/sp/details/2239acf1-711f-4f1f-aaa7-902fa06a8a60),
[SP 28.13330.2017](https://protect.gost.ru/sp/details/bd3c594c-26c7-41a9-9c76-510d0fa1ca92),
[SP 50.13330.2024](https://protect.gost.ru/sp/details/5081dae9-9ee9-455f-80e8-d093d495361c),
[GOST 26633-2015](https://protect.gost.ru/gost/details/b9da3cd9-2fb4-4473-9553-3979ad6be453)
and [GOST 34028-2016](https://protect.gost.ru/gost/details/50236208-68a9-443c-974d-4cc3dc04d15a).
The [MCHS-hosted SP 70 text](https://mchs.gov.ru/uploads/document/2025-04-18/a4fdaa23dd52e900a59f40c57124e039.pdf)
is the 30.12.2020 edition (not the 2026 consolidated text). It supports only
high-level work order, formwork, reinforcement, concrete care and precast
installation statements in this package; current amendments must be reviewed
before introducing numeric tolerances or prescriptive methods. Requirements,
layers, WorkSteps, nodes and informational rules have targeted M1 evidence
references. No consumption norm or numeric design value is asserted.

The public Encyclopedia projects applicability, exclusions, M1 material-class
requirements, ordered M1 work links, nodes, quality checkpoints, common
errors, project-dependent parameters and source links from the M2 aggregate.
Other published technologies in the same family are navigational alternatives,
not an inferred compatibility assertion. DRAFT remains hidden. No new M2
application or domain schema is introduced; M2-to-M5 contract shape is unchanged.

Both family categories remain IN_PROGRESS, and FOUNDATIONS remains IN_PROGRESS.
STRIP still needs a current-edition detailed review of assembly-joint and
waterproofing instructions before its family completion gate. SLAB additionally
needs Russian residential evidence and validated work/layer sequence for the
ribbed system; only then decide ACTIVE versus formal merge/out-of-scope.
Remaining piles, UShP/UFF, columns and basement/substructure inventory belongs
to M2-FOUNDATIONS-2 or later. Do not elevate status from the number of rows.

### M2-FOUNDATIONS-1 live closure (2026-11-07)

The transactional content package was applied to the HousePlatform live DB
after a verified backup, isolated restore, idempotency check and a clean
118-table live-versus-backup fingerprint. The deployed web image exposes the
three ACTIVE technologies listed above. `FND_SLAB_RIBBED_RC` remains DRAFT with
explicit blockers and is not published in the viewer Encyclopedia. The live
package contains 18 material requirements, 18 layers, 18 ordered M1 work steps,
8 nodes, 21 informational rules and 97 targeted evidence references. Eleven
scoped M1 knowledge resources and eight M1 material classes were added; no
existing M1/M3 business rows were changed. The approved 209-code M1 Work
Catalog/REF6 package remains untouched. Dedicated FL and FBS montage codes
remain a documented gap rather than fabricated links.

`STRIP_FOUNDATIONS`, `SLAB_FOUNDATIONS` and parent `FOUNDATIONS` all remain
`IN_PROGRESS`. A2 must resolve the remaining foundation inventory and evidence
gaps, including the ribbed-slab decision; the A1 row counts do not constitute
family or overall content completion. Live route smoke confirmed the category,
Technology, material, node and M1 work pages; DRAFT and absent work-code routes
return 404. The pre-live targeted gate passed 37 tests, and the expanded gate
passed 1529 tests with four skips. The pre-existing security test file that
reads `.env.docker` is explicitly excluded by product/security policy from
ordinary content/module regression gates. An earlier pre-live attempt ran it
inadvertently and exposed a connection string in tool diagnostics; no value is
recorded here or in the repository.

### OUT_OF_SCOPE v1 and closure gate

Barrettes, caissons, sinking wells, diaphragm walls, special deep foundations,
industrial injection systems, and bridge/industrial foundation systems are out
of residential v1. This is a content-scope decision, not a schema limitation.
Protection layers and service penetrations remain in-scope as details, but are
out of scope as standalone Technology until evidence establishes otherwise.

FOUNDATIONS becomes CONTENT_COMPLETE only after: (1) approved scope; (2) full
inventory; (3) every item resolved to ACTIVE Technology, explicit OUT_OF_SCOPE,
or formally merged with another Technology; (4) sufficient evidence per ACTIVE
Technology; (5) ordered WorkSteps linked to M1 codes; (6) requirements linked to
M1 materials/classes; (7) required norms/rules backed by evidence; (8) critical
nodes and limits represented; (9) Encyclopedia coverage matches inventory; and
(10) an audit finds no hidden omissions. This sprint meets only the scope and
inventory preparation gates. FOUNDATIONS stays IN_PROGRESS.

For the next FOUNDATIONS content-fill sprint, read this document, the M2
Technology/Knowledge models and services, the M1 Work Catalog seed, and the
specific M1 material/document/resource records collected for the chosen family.
The minimum focused gate is: approved category and code resolution, M1 material
and work-code resolution, evidence/lifecycle checks, ordered steps, unpublished
draft hiding, Encyclopedia rendering, and a live-data integrity comparison.

## Delivery and verification gate

The earlier schema migration `20261106_module02_content_catalog.sql` was additive
and seeded nothing. The approved taxonomy bootstrap is separately reproducible
as `20261107_module02_approved_residential_catalog.sql`. Its transaction inserts
only approved navigation rows, rejects structural code conflicts, and is safe
to re-run without duplicate rows or resetting later content-status progress.
Before live application: inspect disk/schema/data, make a HousePlatform-only
backup without pruning old copies, restore an isolated DB, run the bootstrap
twice there, verify M1/M2/M3 counters and normal startup without `create_all`.
Then apply only the reviewed bootstrap and rebuild/recreate only web if needed.
No global Docker prune or volume deletion is allowed.

For future content packages, the focused gate is category tree/code validation,
M1 reference resolution, evidence and publication checks, and Encyclopedia
rendering for the touched category. Re-run platform-wide regression only when
shared runtime contracts or production code change; content-only, reviewed
packages can use the focused gate plus read-only audits.

## Implemented contour (M2-CONTENT-ENC-1)

- The additive migration `20261106_module02_content_catalog.sql` creates the
  M2-owned category tree and nullable `Technology.category_id`; it seeds no data.
- The Workbench manages category DRAFT creation/editing, approval, archive and
  starting a content package. It assigns categories to technology drafts and
  preserves the reference in new revisions.
- The authenticated, read-only Encyclopedia exposes category, latest ACTIVE
  technology, material-in-application, node and M1 work pages by stable codes.
  Its source is the existing M2 Technology aggregate plus read-only M1 links.
- Reader search is limited to ACTIVE category/technology names and codes.
  DRAFT and ARCHIVED categories and technologies are not published. M1 document
  and knowledge-resource links are shown only for approved sources and safe
  HTTP(S) URLs.
- `CONTENT_COMPLETE` has no automatic transition. A separate product-approved
  inventory and evidence review is required before a completeness action is
  introduced. Inventory candidates are not Technology or engineering content.
