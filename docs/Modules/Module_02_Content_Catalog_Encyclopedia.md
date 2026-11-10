# Module 2 / Technology Catalog and Construction Encyclopedia

Status (2026-11-08): M2 Core and Encyclopedia infrastructure COMPLETED.
Residential top-level taxonomy v1 is product-approved. FOUNDATIONS and all six
child families are CONTENT_COMPLETE for the approved residential v1 editorial
inventory. The A1/A2 checkpoints below preserve the earlier IN_PROGRESS state;
the current outcome is in the M2-FOUNDATIONS-2 continuation section.

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

### M2-FOUNDATIONS-2: scoped A2 content, not closure

`database/migrations/20261107_module02_foundations_a2_content.sql` is a
transactional, idempotent data package. It adds seven ACTIVE revisions: bored
RC piles, steel screw piles, a monolithic RC pile grillage, concrete/RC column
footings, a monolithic RC basement wall, coating waterproofing and XPS
below-grade insulation. These are M2 technologies, not a second app. Each has
M1 material-class requirements, ordered existing M1 work codes, layers, nodes,
seven editorial/quality rules and target-specific evidence. The package adds
six scoped official M1 resource records and four M1 material classes; it does
not create a product, price, quantity or universal design value. The categories
`PILE_FOUNDATIONS`, `PILE_GRILLAGE_FOUNDATIONS`, `COLUMN_FOUNDATIONS` and
`BASEMENT_AND_SUBSTRUCTURE` move only from EMPTY to IN_PROGRESS.

The following is the *reviewed inventory*, not a fabricated completion claim.
"Blocked" identifies a mandatory item that is **not** a public ACTIVE card.

| Inventory key | A2 decision | Public record / remaining gap |
| --- | --- | --- |
| `FND_STRIP_MONOLITHIC_RC` | ACTIVE system (A1) | Same code; current-edition detail review remains |
| `FND_STRIP_PRECAST_FBS_FL` | ACTIVE system (A1) | Same code; dedicated FL/FBS work semantics remain unresolved |
| `FND_STRIP_GEOMETRY_VARIANTS` | Design parameters | No separate Technology |
| `FND_SLAB_MONOLITHIC_RC` | ACTIVE system (A1) | Same code |
| `FND_SLAB_RIBBED_RC` | **Blocked** distinct-system/variant decision | A1 DRAFT remains hidden; no verified Russian residential sequence |
| `FND_SLAB_RIB_ORIENTATION` | Geometry parameter | Not a Technology |
| `FND_SLAB_USHP` | **Blocked** integrated-system boundary | No approved non-marketing technical system source and no M2-to-floor/heating interface |
| `FND_UFF` | **Blocked** cross-system composition | Strip and floor-on-ground boundary needs reviewed technical package |
| `FND_PILE_DRIVEN_RC` | **Blocked** mandatory pile method | ГОСТ 19804 confirms product class; approved M1 catalog has no driven-pile work code |
| `FND_PILE_BORED_RC` | ACTIVE pile method | Same code; casing is conditional, not a universal layer |
| `FND_PILE_SCREW` | ACTIVE pile method | Same code; steel and corrosion specification are project-dependent |
| `FND_PILE_GRILLAGE` | ACTIVE monolithic RC system | Same code; pile type is separate, combinations are not duplicated |
| `FND_COLUMN_CONCRETE_RC` | ACTIVE scoped system | Same code; reinforcement conditional for RC variant |
| `FND_BASEMENT_WALL_MONOLITHIC` | ACTIVE wall system | Same code; separate from foundation and water-protection systems |
| `FND_BASEMENT_WALL_PRECAST` | **Blocked** wall system | FBS block standard exists; dedicated assembly work and wall/strip reuse need review |
| `FND_PLINTH_WALL` | Construction element | Reuse wall/foundation system, no term-only Technology |
| `FND_FOUNDATION_BEAM` | OUT_OF_SCOPE residential v1 | No generally applicable house-foundation system established |
| `FND_SUBSTRUCTURE_WATERPROOFING` | Partly covered | ACTIVE coating system; membrane/roll system still needs technical review |
| `FND_SUBSTRUCTURE_INSULATION` | ACTIVE XPS method | XPS system; project must verify properties and below-grade use |
| `FND_WATERPROOFING_PROTECTION` | Node of coating system | `PROTECTIVE_LAYER`, not a Technology |
| `FND_UTILITY_PENETRATION` | Linkable node | Wall and coating nodes; engineering network design stays outside M2 |

The official [SP 24 pile design record](https://protect.gost.ru/sp/details/1e90a34c-6379-4236-8256-38be93e29766),
[SP 45 foundation execution record](https://protect.gost.ru/sp/details/6b8a4ce8-2c63-46f8-8c16-6efec70cede8),
[GOST R 59106 steel screw-pile record](https://protect.gost.ru/gost/details/a9b16798-7882-4820-b838-c23c3d680e2e),
[SP 250 underground-water protection record](https://protect.gost.ru/sp/details/990885bc-664d-4329-b54c-5aa3d581c20d),
[GOST 30693 mastic record](https://protect.gost.ru/gost/details/8bea94a2-17da-452d-8965-915ba60168a4),
and [GOST 32310 XPS record](https://protect.gost.ru/gost/details/e81b18f6-742d-417b-83c7-c361be521951)
support source scope, not a universally approved construction recipe. The
[GOST 19804 factory-made RC pile record](https://protect.gost.ru/gost/details/1dd4f62d-2f16-4ee8-bdff-41dc947d9167)
supports the driven-pile product class only; no driven-pile card is published.
Current amendments must be checked for an actual project. No fixed pile count,
spacing, length, capacity, footing size, reinforcement, concrete grade,
water pressure or insulation thickness is stored.

The M1 Work Catalog remains the approved immutable 24-group/209-work baseline:
see `docs/Modules/module1/reference_data/ATOM_REF6_Approval_Record_v1.md`.
The seven new Technologies use only existing semantically applicable codes.
There is no new M1 work code. Missing dedicated driven-pile, FL/FBS assembly,
and precast-wall work items require a separately governed M1 catalog version;
silently changing the approved seed would invalidate REF6 provenance. This is
the smallest cross-module blocker for A2 closure, alongside the USHP/UFF and
ribbed-slab evidence decisions. The coating card does not claim to cover a
membrane system. Earthworks, drainage, blind area and floors on ground remain
owned by PREPARATION, SITE_WORKS and FLOORS_AND_STAIRS respectively; linked
cross-category navigation is still a gap in the current M2 aggregate/UI.

All six FOUNDATIONS families and the parent remain IN_PROGRESS. A3 must not
be presented as the next content-fill sprint until the remaining A2 blockers
are explicitly resolved. For a resumed A2, provide this inventory, the M1 REF6
approval record, the two foundation content SQL packages, M2 Technology and
Knowledge models, the Encyclopedia service/template, and current official
source links. Review new M1 work-catalog versioning and cross-category links
before any attempt to mark the category CONTENT_COMPLETE.

A2 live checkpoint (2026-11-07): a new 979,723-byte custom PostgreSQL dump was
stored at `backup/m2-foundations-2/houseplatform-20261107-201843.dump` and
SHA-256 checked against the container copy. `pg_restore -l` listed 1,462 TOC
entries. The archive restored successfully into the isolated
`houseplatform_m2_foundations_dryrun_20261107_201843` database. SQL applied
twice there; the second run inserted zero rows. A1 Technologies and M1/M3
materials, specifications, documents, users, roles and workspaces had equal
counts and row hashes between live and the restored copy. The SQL then applied
once to live; afterwards those pre-existing row hashes still matched.
The live counts equal the dry-run counts: 11 M2 technologies, 31 requirements,
31 layers, 31 work steps, 19 nodes, 70 knowledge rules and 203 evidence refs.
Focused A1+A2 content gate: 6 passed. M1/REF6/M2/M2-to-M5 contract gate:
115 passed, 3 skipped with the test's expected legacy REF6 mode (the first
unadjusted invocation had one environment-mode assertion failure). Read-only
live Encyclopedia route/template smoke: 1 passed. The excluded security-gate
file was not run. No full regression was needed because no shared runtime code
or schema changed. No web image was rebuilt: live content is served by the
existing web, and web/db/redis remained healthy; `/api/v1/health` returned 200.

### M2-FOUNDATIONS-2 continuation: approved closure package (2026-11-08)

This section supersedes the *current-state* conclusions in the historical A1/A2
checkpoints above; those records remain as evidence of the earlier state. The
approved REF6 seed remains byte-for-byte unchanged at 209 works. The separate
`foundations-a2-v1` M1 extension (`version=1.1`) adds exactly three governed
codes: FL assembly, FBS assembly, and driven factory-made RC piles. The
effective Work Catalog has 212 works. M2 stores the stable M1 codes and ordered
steps, not a duplicate Work Catalog. REF6 material hints for these new works
remain `review_required`; neither prices nor quantities are inferred.

The transactional package
`database/migrations/20261107_module02_foundations_a2_closure.sql` is additive
and idempotent. It creates six M2 Technology revisions (including revision 2
for FBS and ribbed slab), 17 material requirements, 17 layers, 16 ordered M1
work steps, 24 nodes, 42 informational rules, and 128 target-specific evidence
references. It adds eight scoped M1 knowledge resources, two M1 material
classes, and four resource links. Superseded FBS revision 1 (formerly ACTIVE)
and ribbed revision 1 (formerly DRAFT) become ARCHIVED; revision history is
retained. No schema, prices, quantities, universal dimensions, or fabricated
product records are introduced. The current public catalog has 15 distinct
ACTIVE FOUNDATIONS technologies; rows including history total 17.

| Approved inventory key | Final treatment | Current public source |
| --- | --- | --- |
| `FND_STRIP_MONOLITHIC_RC` | ACTIVE | Same code, A1 |
| `FND_STRIP_PRECAST_FBS_FL` | ACTIVE revision 2 | Separate FL and FBS work steps; FL conditional |
| `FND_STRIP_GEOMETRY_VARIANTS` | PARAMETER | Strip design, not a Technology |
| `FND_SLAB_MONOLITHIC_RC` | ACTIVE | Same code, A1 |
| `FND_SLAB_RIBBED_RC` | ACTIVE revision 2 | Distinct ribbed slab; orientation is a parameter |
| `FND_SLAB_RIB_ORIENTATION` | PARAMETER | Ribbed-slab design |
| `FND_SLAB_USHP` | ACTIVE | Composite slab foundation; floor/heating/networks linked |
| `FND_UFF` | ACTIVE | Composite strip foundation; floor/heating/networks/site linked |
| `FND_PILE_DRIVEN_RC` | ACTIVE | Factory-made RC pile and dedicated M1 work |
| `FND_PILE_BORED_RC` | ACTIVE | Same code, A2 |
| `FND_PILE_SCREW` | ACTIVE | Same code, A2 |
| `FND_PILE_GRILLAGE` | ACTIVE | Same code, A2 |
| `FND_COLUMN_CONCRETE_RC` | ACTIVE | Same code, A2 |
| `FND_BASEMENT_WALL_MONOLITHIC` | ACTIVE | Same code, A2 |
| `FND_BASEMENT_WALL_PRECAST` | REUSED | FBS revision 2, with a basement-wall application link |
| `FND_PLINTH_WALL` | COMPONENT | FBS or relevant wall/foundation detail, no standalone card |
| `FND_FOUNDATION_BEAM` | OUT_OF_SCOPE | Residential v1 |
| `FND_SUBSTRUCTURE_WATERPROOFING` | ACTIVE | Separate coating (A2) and membrane (A2 closure) systems |
| `FND_SUBSTRUCTURE_INSULATION` | ACTIVE | XPS method, A2 |
| `FND_WATERPROOFING_PROTECTION` | NODE | Membrane/coating protection detail |
| `FND_UTILITY_PENETRATION` | NODE | Wall and waterproofing interface |

USHP and UFF link to the existing `FLOORS_AND_STAIRS`, `HEATING_AND_DHW`, and
`WATER_AND_SEWER` categories. FBS appears as a related Technology on the
`BASEMENT_AND_SUBSTRUCTURE` page without manufacturing a second wall card.
Related links are projections of structured Technology nodes and only resolve
public ACTIVE targets. The membrane system is separate from coating mastics.
Manufacturer technical systems are evidence of possible composition, not
universal engineering prescriptions; project-specific geology, loading,
waterproofing, thermal and interface design remain mandatory.

The isolated backup restore passed two SQL runs (second run inserted zero
rows), startup without implicit `create_all`, focused M1/M2/API checks, and a
full 118-table row-hash comparison: all 4,135 original rows persisted; 264
new row hashes appeared only in the ten allowlisted M1/M2 tables. Full platform
regression with explicit test-only legacy REF modes passed 1,536 tests with
five skips. The security test reading `.env.docker` was excluded. Numeric
consumption norms remain absent because a universal value would be unsafe;
M2-to-M5 packages preserve work codes but correctly report not ready for
calculation. `CONTENT_COMPLETE` denotes this approved editorial inventory and
evidence coverage, not a ready-to-price estimate or an approved project design.

Live closure: backup `backup/m2-foundations-2-continuation/houseplatform-20261107-215930.dump`
is a 998,504-byte PostgreSQL custom archive with SHA-256
`25f9768b558c70635c6607ba401681d2cab882eebf40bcb61e0b45ff01069b4f`.
It restored into `houseplatform_m2_foundations_dryrun_20261107_215930`; the
live fingerprint still matched the backup before migration. The reviewed SQL
SHA-256 was `ff7b4fc79b2695ddd04aa8db735aeded12a9f9a91bd6b1722eee2697e4ce1a12`.
One live transaction committed successfully. The post-migration audit found
zero missing original row hashes and exactly 264 new row hashes in the expected
ten M1/M2 tables. A controlled build and recreate changed only
`houseplatform-web-1`; db and redis retained their container IDs and remained
healthy. `/api/v1/health` returned 200, and both read-only live Encyclopedia
smoke tests passed. No volume, network, unrelated project, backup, or secret
file was removed or read manually.

Remaining product decisions before quantitative content fill are project- and
system-specific consumption norms with verifiable scope, the separately
reviewed REF6 material hints for the three new work codes, and any future
residential inventory extension. These are not hidden A2 omissions and do not
authorize M5 calculation, provider costs, or a universal design recipe.

### OUT_OF_SCOPE v1 and pre-continuation gate (historical)

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
(10) an audit finds no hidden omissions. At this earlier A2 checkpoint, only
the scope and inventory preparation gates were met; FOUNDATIONS was IN_PROGRESS.

The pre-continuation handoff advised the next FOUNDATIONS content-fill sprint
to read this document, the M2
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

## A2.1: versioned default assumptions and Russian Workbench

`module2_technology_default_assumptions` is M2-owned. Its stable key is
`(technology_id, assumption_code)`, with an immutable integer revision and one
ACTIVE revision per key and parameter. It records parameter code, Russian name,
typed value (`NUMBER`, `MATERIAL`, `MATERIAL_CLASS`, `ENUM`, `BOOLEAN`, `TEXT`),
unit, source kind, applicability, auto-fallback flag, warning, bounded allowed
values, optional M1-backed material requirement/evidence reference, and actor/time.
Admin edits supersede the prior default, create a new revision, and write an
`AuditEvent` with old/new values. Editing a Technology revision does not rewrite
any earlier assumption or a previously produced estimate snapshot.

The read-only M2 resolver accepts optional project values and user overrides.
For each parameter it selects `USER_OVERRIDE > PROJECT_VALUE > M2_DEFAULT`;
when auto-fallback is disabled it returns `UNRESOLVED`. Every result includes
assumption code/revision, Technology code/revision, resolved value, source,
warning and allowed alternatives. Future M5 persistence must snapshot those
fields at calculation time; this sprint does not create M5/M7 project data or
retroactively change calculations.

The first A2.1 package provides 90 ACTIVE defaults across all 15 public
FOUNDATIONS technologies: 40 M1 requirement-scoped material classes, 18
preliminary concrete/reinforcement classes, 9 reinforcement diameters, and 23
geometry/insulation/protection dimensions. All 90 are explicitly
`PLATFORM_ASSUMPTION`; **none is an evidence-backed typical value, consumption
norm, structural design, or building instruction**. Numeric fallback carries a
critical preliminary warning and requires project/design review. The input
range rejects obvious invalid values; it is not an engineering approval range.
The linked SP/GOST evidence defines product classes and design scope, not a
universal default size. No fabricated evidence link was attached to a number.

Material-class values point to the category already selected by the M2
requirement from M1. A different category fails validation. Concrete and
reinforcement class alternatives are bounded within their corresponding
requirement; a change to the structural Technology itself requires explicit
Technology selection. There are currently no VERIFIED M1 product records in
the foundation-specific classes, so the Workbench does not offer a fake product
alternative list. Compatibility and project-specific suitability remain design
decisions. The three recent REF6 work hints retain their pre-existing
`review_required` status; A2.1 does not approve them without source review.

The Workbench shows Russian primary labels and secondary codes for the existing
layer/material records, plus a table of defaults with headings, unit,
obligation, warnings, and a pencil editor for admin-editable values. It does
not show or store project values. Editors use existing RBAC and CSRF handling.
New production Technology content in A3-A11 must provide Russian human-readable
labels, typed parameters, bounded/scoped defaults or explicit unresolved state,
appropriate evidence and warnings, and a checked read-only resolver projection
before being marked content-complete. This is a content gate, not automatic
approval of new universal engineering values.

## A2.2: reader-first encyclopedia and canonical M1 material resolution

The Encyclopedia is a standalone explanation for a reader without an object or
project. Each Technology first explains what it does, where it is used, when it
does not fit, the typical composition, materials, ordered M1 Work Catalog steps,
preliminary platform assumptions, checks and common errors. Project-specific
design decisions come later in a separate section. The 15 public FOUNDATIONS
descriptions are revised by `20261108_module02_foundations_a22_editorial.sql`;
it introduces no universal dimensions or unreviewed construction norms. The
existing 90 A2.1 defaults remain `PLATFORM_ASSUMPTION`, explicitly labelled
"preliminary assumption" in the reader UI. Workbench and Encyclopedia link in
both directions using a stable Technology code on the public side. The module
passport is a service-menu item, not primary navigation.

M2 owns a Material Requirement, never a Material Card. Candidate resolution
reads VERIFIED canonical M1 `materials` by the requirement's exact category or
subcategory and optional material type, then checks declared characteristics
and active M2 compatibility rules. A requirement without a scoped M1 selector
does not search the whole catalog. A rejected or unverified product is never a
candidate. The default material class is shown as an assumption, not as a
fictitious product. Every candidate links to the read-only, addressable M1
Material Card (`/api/v1/module1/materials/{material_id}`), which reads M1
characteristics, documents, prices, suppliers and active source offers. No M2
material copy is stored or rendered.

`module2_material_gaps` records an unresolved Technology requirement and
revision, corrected search phrase, category, constraints, evidence context,
status, optional canonical resolution ID and M1 SourceTask ID. The additive
`20261108_module02_material_gaps.sql` seeds gaps only for the current active
FOUNDATIONS requirements without a VERIFIED matching M1 card; publication of
later Technologies creates the same gap when needed. OPEN creates an actual M1
`FIND_NEW_PRODUCTS` task in `NEEDS_REVIEW`, so M1 can choose an appropriate
source; it does not launch an unscoped crawler. M2 admin can auditably edit the
query, choose a compatible VERIFIED M1 card, request M1 search, or dismiss
with a rationale. Statuses are OPEN, REVIEWING, SEARCH_REQUESTED,
RESOLVED_EXISTING, RESOLVED_NEW_MATERIAL and DISMISSED. The material resolver
passes linked M2 evidence reference IDs into the M1 task; the additive
`20261108_module02_material_gap_evidence.sql` backfills the initial 40 gaps.
The existing M1 task table displays these requests in readable form and keeps
the current 100 most recent tasks visible instead of truncating this batch.
The material resolver
and gap state are separate from the A2.1 value priority
`USER_OVERRIDE > PROJECT_VALUE > M2_DEFAULT`; this sprint creates no M5
estimate or M7 object override.

For A3-A11, publication is incomplete unless each new Technology has a Russian
reader-first article; ordered, readable M1-linked work steps; scoped M1
material requirements with compatible candidate cards or an explicit Material
Gap; typed preliminary defaults and alternatives; understandable nodes,
quality checks, common errors, project-dependent boundaries, visible evidence
and cross-links. Technical codes stay stable and secondary in the UI. A
content-complete claim additionally requires targeted reader, material
identity/filtering, gap lifecycle, RBAC and navigation tests. This gate applies
to each new section on its first content pass, not a later corrective pass.

## A2.3: final M2 encyclopedia and Workbench UX standard

The reader hierarchy is category overview -> family overview -> Technology
article. A category overview explains the principle of its systems, links to
families, and compares them without choosing a design for an unexamined site.
Each family article provides a short introduction, mechanism, use cases,
advantages, limitations, comparison with neighboring families, typical material
classes, an overall work sequence, project-dependent checks, and links to its
published Technologies. The six FOUNDATIONS families use the lightweight,
code-keyed editorial projection in `module2_encyclopedia_editorial.py`; their
claims summarize existing approved Technology descriptions and evidence. This
is presentation content, not a second taxonomy, material catalog, or CMS.
Unpublished categories still use the normal empty state. New categories must
add their own reviewed editorial projection before being declared complete.

A Technology article is standalone for a reader without a project: explanation,
applicability and exclusions, preliminary defaults, construction composition,
materials, ordered M1-linked work steps, quality checks, common errors,
project-dependent decisions, nodes, related articles, and numbered sources.
"According to the project" belongs after an explanation or in the dedicated
project-dependent section; it never substitutes for an explanation. The current
FOUNDATIONS audit found such wording only in contexts with preceding technical
explanation, quality instructions, or the project-dependent section. Evidence
references remain addressable in M2; the article uses compact numbered links
and a source list at the end.

The 90 A2.1 defaults remain unchanged. Public pages label them preliminary
platform assumptions, not norms or universal values. Requirement plus linked
class/reinforcement defaults renders a human material name (for example,
"Бетон B25" or "Арматура A500C Ø12"). Alternative values and bounded ranges
are read-only previews without M7 object persistence. Only compatible,
VERIFIED canonical M1 cards are linked; extra candidates are collapsed.
Missing cards receive a calm reader message. The A2.2 gap task, search,
resolution, and dismissal controls stay in the admin Workbench and retain
their RBAC and audit behavior. A material requirement page identifies itself
as a requirement, never a duplicate material card.

The A2.3.C navigation and permission model below supersedes the original A2.3
sidebar and technical-details presentation. Breadcrumbs and local article
navigation preserve the hierarchy. From Module 3, M2
borrows only visual tokens and interaction quality (type, colors, spacing,
borders, controls, active and responsive states), not business logic, table
layout, widgets or information hierarchy.

For A3-A11, `CONTENT_COMPLETE` requires the category and family overview
articles, each published Technology article, scoped preliminary defaults or
an explicit unresolved value, canonical M1 material references or a Material
Gap, ordered M1 work steps, nodes, quality and project-dependent sections,
evidence, cross-links, responsive presentation, and RBAC/link tests. Review
the underlying engineering evidence before adding any new claim. Do not seed
fake materials or a second Work Catalog. The final M2 UX format is applied
during the first content pass of each new category, not as a later corrective.

## A2.3.C: Information architecture and permissions

M2 has a reader-facing Encyclopedia and an administrative Technologies
registry. The common sidebar links to the Encyclopedia for readers and also
to Technologies for editors. Both sections have closed-by-default submenus;
article contents are contextual submenu links rather than a second navigation
column. Category management is inside Technologies. M2-HOME-1 below supersedes
the former permission-dependent module entry destination.

Encyclopedia GET routes require M2 VIEW at the existing LIMITED scope. The
administrative registry, categories and Technology detail require M2 EDIT at
the existing GLOBAL scope. Existing EDIT, APPROVE and ADMIN checks continue
to govern mutations and lifecycle transitions; explicit NO_ACCESS has priority
over role access. Browser login, CSRF and audit use the platform mechanisms.
The domain service accepts the authenticated user for permission checks while
retaining its role-code interface for existing internal callers.

Technology detail uses seven addressable tabs: General, Construction,
Materials and Parameters, Works, Rules, Sources, and Revisions. Each request
renders only the selected tab; action redirects retain the relevant tab.
Materials, default assumptions and existing M1 gap actions remain together.
Sources are grouped by document with their individual evidence links retained.
Normal UI uses human names rather than machine identifiers; public articles
keep their deduplicated source list at the end and link to canonical M1 cards.

For A3-A11, each published Technology belongs in the existing Encyclopedia
hierarchy and the common administrative registry. New categories do not add
separate main navigation sections. Content completion still requires reviewed
evidence, readable articles, canonical M1 references, ordered work, applicable
defaults, access tests and responsive navigation.

## M2-HOME-1: Interactive module home

`GET /api/v1/module2` is the shared M2 entry page for readers and editors.
M2 VIEW at LIMITED scope is required, and existing explicit deny takes
precedence. The existing Encyclopedia and administrative Workbench routes are
unchanged. The Dashboard and M2 widget source link open the common home;
administrative Technologies still requires EDIT at GLOBAL scope.

The home uses two coordinated architectural illustrations: a cutaway and an
exterior view. SVG hit areas highlight the selected construction element; a
separate card explains it and links to the corresponding existing Encyclopedia
category. Keyboard, hover and touch interaction share the same state. A text
list provides an alternative without requiring a hit on the illustration.
`view` and `part` query parameters preserve selection, and unknown values fall
back safely. The illustration is explanatory, not construction documentation.

`HOUSE_ZONES` is a small navigation mapping from house parts to stable M2
category codes. The page resolves links only against the public category tree;
missing or unpublished categories have an unavailable state. The mapping does
not create a second technology or material catalog. Search submits to the
existing Encyclopedia search, and published content and evidence remain there.

The standard UserModuleQuickAction bar shows only actions already saved by the
user and hides when empty. The page adds no widgets or statistics. On narrow
screens the existing M2 sidebar is a collapsible menu, the house and card stack,
and the list becomes touch-friendly rows. Future A3-A11 categories must retain
stable mappings, public visibility checks, keyboard/touch navigation, honest
empty states and the existing M1/M2 ownership boundaries.

## M2-UX-FINAL implementation

The technology registry provides combined category, status,
material-selection and activation-blocker filters. Its three operational
queues are projected through the existing M2 readiness widget payload and
remain protected by EDIT access. An open Material Gap is not a selected M1
material, and an activation blocker is not an estimation-readiness verdict.

The encyclopedia sidebar loads published root categories on demand, while the
category index and root category pages use illustrative category imagery.
These illustrations are not construction drawings or evidence. The technology
workspace retains its seven sections, actual M1 references, and lifecycle and
permission boundaries. Empty activation warnings are not shown for an active
technology; a missing M1 material is not represented as an established match.

The read-only foundation snapshot and follow-up checklist are in
`Module_02_Foundations_Full_Inventory.md`. Release remains conditional on the
targeted, regression and live visual checks and the controlled web deployment.

## M2-FOUNDATIONS-FULL + M1: current handoff

The current content state is PARTIAL / IN_PROGRESS, not full engineering or
estimation readiness. The 15 active foundation and substructure technologies,
their actual structure and the material gap counts are documented in
`Module_02_Foundations_Full_Inventory.md`. No active technology was directly
edited and no production data or schema migration was required for this slice.

The existing M1 normalization and matching pipeline is retained. Cyrillic
concrete classes and rebar diameter symbols are recognized; differing classes
and diameters remain conflicts. All 40 active requirements were checked through
the existing VERIFIED-compatible lookup: no compatible card was established,
and the 40 existing gaps already have acquisition tasks. No fake material,
product, price, certificate or evidence was created.

Category pages now explicitly distinguish own published technologies from
typed cross-category relationships, retaining the preparation relationship as
such. The generic illustration caption was removed. On FOUNDATIONS, a GET-based
comparison offers two or three currently public supported technologies, 13
shared qualitative criteria and four scenarios that reorder relevant criteria.
It is an educational overview, not a foundation recommendation, M5 calculation
or price ranking. The related external background references are not Russian
design norms. Administrative work rows link to the existing published M1 work
representation; compact node and rule layouts preserve permissions and actions.
Workbench lifecycle actions for a technology's engineering rules and norms are
restricted server-side to a DRAFT technology revision; its non-DRAFT revisions
cannot be altered through this endpoint by archiving active child records. The
independent knowledge service retains its existing internal lifecycle contract;
future entry points must enforce the same revision boundary.

Still required: detailed verified articles and images for each technology,
review of claim-level evidence and source applicability, actual compatible M1
materials, justified norms, construction and editing UX refinements for all
seven workbench tabs, and structured M2-to-M5 readiness review. Do not start A3
on the assumption that these tasks are complete. The canonical category and
material catalogs, lifecycle, RBAC, default priority and REF6 remain unchanged.

Verification for this slice: full isolated regression 1579 passed, 22 skipped,
2 deselected before the final localized Workbench lifecycle guard; subsequent
targeted M2 lifecycle/contract/Workbench checks passed (97 passed, 2 skipped),
as did the final direct-endpoint and comparison tests (22 passed). The two
deselected security tests directly read the protected Compose environment file.
Desktop/mobile browser smoke covered 390, 768, 1280 and 1440 pixels, all seven
tabs, the comparison scenarios and VIEW/admin access. The HousePlatform web
image was rebuilt and only web was recreated; health API returned 200. No live
business-data changes or migration were applied, so no new backup was created.
Counts of the audited M1/M2 tables matched before and after; this is a count
comparison, not a full row fingerprint. The isolated test DB was retained.
Commit and remote synchronization are recorded in the Git history.
