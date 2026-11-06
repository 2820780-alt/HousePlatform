# Module №2 / Technology Knowledge Base v1.7

## Purpose

Module №2 превращает проверенные данные Module №1 в инженерное знание о том,
как применять материалы и выполнять строительную технологию.

Короткая граница ответственности:

- M1 = WHAT IT IS: canonical material, characteristics, prices, evidence,
  provenance, Work Catalog и quality state.
- M2 = HOW TO BUILD WITH IT: technology composition, layers, requirements,
  nodes, work sequence, applicability and engineering interpretation.
- M5 = HOW MUCH / HOW MANY: quantity and cost calculation, estimate and
  material selection.
- M7 = WHERE / ACTUAL OBJECT: geometry and state of a concrete construction
  object.

Module №2 не копирует сущности и первичные данные Module №1.

## Existing foundation audit

| Entity / file | Purpose | Status | Decision | Reason |
| --- | --- | --- | --- | --- |
| `KnowledgeResource` | M1 evidence/resource metadata | Used by Material Hub | Keep | M1 owns primary evidence; this is not a Technology aggregate. |
| `KnowledgeResourceLink` | Link M1 evidence to material taxonomy | Used by Material Hub | Keep | M2 may reference it but must not take ownership. |
| `KnowledgeCandidate` | Extracted knowledge pending moderation | Existing foundation | Keep | It is an ingestion/moderation candidate, not approved M2 knowledge. |
| `material_construction_usage.py` | M2-to-M1 moderation adapter | Existing boundary | Keep | M2 output becomes an M1 candidate, never an automatically verified material fact. |
| `Module2TechnologyInputPackage` | Read-only M1-to-M2 material package | Stable contract | Keep | Carries references, hints, missing fields and blockers with no calculations or side effects. |
| `Module_02_KnowledgeBase_v1.0.md` | Canonical M2 architecture | Minimal | Extend in place | Avoids a parallel architecture document. |
| `module2_technology_engine_codex_plan.md` | Long-term implementation roadmap | Planning only | Keep as roadmap | It is not proof of implemented runtime behavior. |
| Module registry/dashboard entry | Discovery and access metadata | Historically marked ACTIVE | Keep unchanged in this sprint | Module №3 is out of scope; ACTIVE metadata is not proof of a working M2 user contour. |

No existing Technology, ConsumptionNorm or KnowledgeRule engine was found.
The knowledge resource tables remain M1 evidence foundation and are not renamed,
merged or deprecated by Sprint 2.1-2.2.

## Current module status

The Technology domain, internal Technology Workbench and read-only M2-to-M5
estimation input contract are `COMPLETED` for the agreed Module №2 scope. The
server-rendered contour is live inside HousePlatform at
`/api/v1/admin/module2/workbench`; its passport and module route open the same
contour. The readiness widget is `ACTIVE` in the formal registry and available
for user placement, but is not enabled or placed by default. Safe user-owned
Quick Action candidates remain opt-in. M2-to-M5 is an input contract only; it
does not run an M5 calculation or create an estimate.

## Sprint 2.7 action and widget review

The initial Sprint 2.7 audit found an empty formal Module №2 widget inventory and
no M2-specific Quick Action candidates. Corrective 2.7.C closes the useful parts
of that gap without adding a module-specific persistence layer. No estimate-like
or M5 action is exposed.

| Surface | Existing action | Lifecycle / RBAC result | Sprint 2.7 decision |
| --- | --- | --- | --- |
| Technology list | Create DRAFT, search, status filter, open detail | Create requires EDIT | Keep |
| Technology header | Submit review, return to DRAFT, activate, create revision, archive | EDIT / APPROVE / ADMIN; backend transition guard is authoritative | Keep; confirm archive |
| DRAFT composition | Create, edit, delete requirements, layers, nodes, work steps and evidence | DRAFT plus EDIT | Keep; confirm delete |
| Ordered composition | Move layers and work steps | DRAFT plus EDIT; shared move service | Expose existing work-step move control |
| Knowledge records | Submit review, return to DRAFT, activate, archive | EDIT / APPROVE / ADMIN; blockers disable activation | Keep; clarify labels and confirm archive |
| Readiness panels | M1 input blockers and Technology activation blockers | Read-only | Clarify scope; not M5 calculation readiness |

The generic Module №2 passport reports `Активен` and opens the existing
Workbench. The common module registry resolves the same route.

The single readiness widget is backed by real Technology records and module RBAC.
Its registry definition is available but disabled by default, has no mock
provider, no default settings and no automatic placement. The Workbench exposes
safe candidates for opening the registry, opening a concrete Technology and
creating a DRAFT. Saving,
pinning and running those shortcuts uses the existing user-owned platform service;
no default or seeded Quick Action is created. Lifecycle transitions, delete,
archive and M5-like actions are not Quick Action candidates.

## Canonical Technology aggregate

`Technology` is the canonical aggregate for both the construction system
description and the method of performing it at this stage.

Minimum identity and lifecycle:

- `technology_code` is stable across revisions;
- `revision` identifies an immutable published variant;
- `name`, `description` and optional `system_code` describe the aggregate;
- `status` is `DRAFT`, `REVIEW`, `ACTIVE` or `ARCHIVED`;
- `owner_module_code` is always `MODULE_02_KNOWLEDGE_BASE`;
- `source_kind` records curation semantics without copying an M1 source;
- `supersedes_id` links a new draft revision to historic active knowledge;
- M1 missing fields and blockers are retained as activation guards.

### ConstructionSystem decision

A separate ConstructionSystem table is not created in 2.1-2.2. Today it would
duplicate the Technology aggregate without a distinct lifecycle or owner.
`system_code` provides a lightweight classifier. A separate entity is justified
only when several independently versioned technologies must compose one system.

## Layers

`TechnologyLayer` is ordered by a positive `position`, unique inside one
Technology revision. A layer stores:

- functional role;
- optional material requirement reference;
- optional thickness/parameter expression;
- mandatory/optional flag;
- notes and restrictions.

A layer never stores a Material copy.

## Material requirements

`TechnologyMaterialRequirement` expresses one of four selector semantics:

- `CANONICAL_MATERIAL`: reference to an M1 `materials.id`;
- `MATERIAL_CLASS`: reference to M1 category or material type;
- `TECHNICAL_CONSTRAINTS`: engineering constraints interpreted by M2;
- `ROLE`: a role that a later M1 material resolver can satisfy.

The model intentionally does not implement a recommender and does not persist
material names, prices, suppliers, manufacturers or normalized characteristics.

## Nodes

`TechnologyNode` provides a minimal Technology-to-Node ownership relation for
openings, corners, junctions, penetrations and other standard details. It stores
a stable node code, type, name, description and conditions. No visual node
constructor is included.

## Work steps

`TechnologyWorkStep` owns order, applicability, dependencies and instructions.
It stores only the existing M1 `work_code`; creation validates the code through
the read-only Work Catalog service. It cannot create or modify Work Catalog
items and contains no provider work cost.

### WORK CATALOG STRUCTURE FOUND

The implemented M1 Work Catalog is an immutable, seed-backed read service and
the only source of truth. Its actual hierarchy has exactly two levels:

`WorkGroup -> WorkItem`

There are no stage, substage or operation entities in the current M1 catalog.

| Level | Entity / model | Stable identity | Ordering | Lifecycle | Technology / M2 usage | M2-to-M5 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `WorkGroup` | `work_group`; `work_category` is display text | Seed list order only; no explicit position | No status field; loaded entries are available | Resolved from M1 through each work item's `work_group`; not copied into M2 | Sends stable `work_group`, resolved read-only from M1 by `work_code` |
| 2 | `WorkItem` | `work_code`; `work_name` is display text | Seed list order only; no explicit position | No status field; inactive state is not represented | `TechnologyWorkStep.work_code` is validated against M1; Technology owns only its step `position`, conditions, dependencies and instructions | Sends `work_step_id`, `order`, stable `work_code` and its M1 `work_group`, never display name as identity |

The catalog currently contains 24 groups and 209 work items. M2 renders the
Technology work composition by resolving names from M1, stores no copied catalog
name/category, and preserves Technology-specific work order in
`TechnologyWorkStep.position`. The estimation package preserves that order, the
stable M1 `work_code` and its read-only resolved `work_group`. An unknown code
produces `unknown_m1_work_code`, leaves `work_group` empty and never invents a
catalog value.

Gaps recorded for later decision: M1 has no explicit catalog ordering field,
lifecycle/status or stage/substage/operation hierarchy; the M2 selector is flat;
the estimation package has no catalog snapshot or catalog version. Sprint 2.7
does not invent or persist any of those missing concepts.

## ConsumptionNorm

`ConsumptionNorm` is a versioned relative engineering norm attached to one
Technology revision. It stores:

- a stable norm code and revision;
- optional layer, material requirement and work-step scope;
- a structured resource selector containing M1 IDs or M2 requirement semantics;
- a positive basis quantity and canonical basis unit;
- a positive consumption quantity and canonical consumption unit;
- structured applicability conditions;
- lifecycle, blockers, provenance and supersession.

The M1 `UnitConversionRegistry` normalizes both units. Unknown units are
rejected and no implicit conversion is performed. The stored relation can express
`5 kg / 1 m2`, but M2 never multiplies it by object geometry and never applies a
price. Quantity application and cost belong to M5.

## Structured conditions

`StructuredCondition` permits only declared fields, a source
(`M1_MATERIAL_PROPERTY` or `CONTEXT`) and these deterministic operators:

`EQUAL`, `NOT_EQUAL`, `IN`, `NOT_IN`, `GT`, `GTE`, `LT`, `LTE`,
`BETWEEN` and `EXISTS`.

There is no executable expression, Python/JavaScript/SQL payload, `eval`, DSL,
recursive inference or AI evaluator. M1 property values are consumed through the
read-only `Module2TechnologyInputPackage`; they are not copied into M2 tables.
Missing values produce `UNKNOWN`, and fields marked critical for activation
produce an activation blocker.

## CompatibilityRule

`CompatibilityRule` is an independently versioned M2 entity scoped to a
Technology revision. Subject and object are structured selectors for canonical
M1 materials, M1 material classes, M2 material requirements, technical
constraints or roles. The relation is one of:

- `COMPATIBLE`;
- `INCOMPATIBLE`;
- `CONDITIONAL`;
- `UNKNOWN`.

The evaluator matches active rules and evaluates only their structured
conditions. Missing evidence or properties returns `UNKNOWN`. A simultaneous
compatible/conditional and incompatible result returns `REVIEW` with every
matching rule and evidence reference; it is never silently resolved. This is a
validation foundation, not a recommender.

## KnowledgeRule

`KnowledgeRule` binds structured IF conditions to one outcome:

- `REQUIREMENT`;
- `WARNING`;
- `PROHIBITION`;
- `CONSTRAINT`;
- `INFORMATION`.

Its scope must resolve to a Technology, layer, material requirement, node, work
step, consumption norm or compatibility rule. The evaluator returns
`APPLIES`, `DOES_NOT_APPLY`, `UNKNOWN` or `REVIEW`; it does not execute
arbitrary code or infer new engineering facts. Existing `KnowledgeCandidate`
remains an M1 moderation input and is not reused as approved M2 knowledge.

## Evidence ownership

`TechnologyEvidenceReference` stores exactly one foreign reference to either
an M1 `MaterialDocument` or an M1 `KnowledgeResource`, plus the M2-owned
engineering interpretation. It does not duplicate files, URLs, certificate
contents, extracted text or document metadata.

The same typed link now targets a Technology, layer, material requirement, node,
work step, consumption norm, compatibility rule or knowledge rule by an M2
target kind and revision-specific reference. This deliberately reuses the
existing evidence table instead of creating a parallel polymorphic evidence
system. Before activation, a read-only query verifies that every referenced M1
record exists; a missing or unverified reference is a blocker.

M1 owns primary evidence and its lifecycle. M2 owns only engineering
interpretation, applicability and links to M2 knowledge.

## Versioning and lifecycle

Allowed transitions:

- `DRAFT -> REVIEW`;
- `REVIEW -> DRAFT`;
- `REVIEW -> ACTIVE`;
- `ACTIVE -> ARCHIVED`.

ACTIVE Technology, ConsumptionNorm, CompatibilityRule and KnowledgeRule records
are immutable. A change creates a new DRAFT revision with the same stable code
and a `supersedes_id` reference; evidence is revision-specific and must be
attached and verified for that revision.

Activation is blocked by missing/broken evidence, unresolved critical M1
properties, inherited Technology input blockers or conflicting active rules.

## RBAC

The service consumes the existing platform role-access matrix for
`MODULE_02_KNOWLEDGE_BASE`:

- VIEW or higher can be used by future read contours;
- EDIT can create/update drafts and submit review;
- APPROVE can return review to draft or activate;
- ADMIN can archive;
- no separate Module №2 authentication or permissions are introduced.

The Workbench applies the same permission guard on every GET and POST route.
The template hides draft editors and lifecycle actions that the current user
cannot execute, while backend checks remain authoritative. Legacy application
role `ADMIN` is normalized to the existing `PLATFORM_ADMIN` matrix role.

## Persistence and migration

Sprint 2.1-2.2 added these `module2_*` tables:

- technologies;
- material requirements;
- layers;
- nodes;
- work steps;
- evidence references.

Sprint 2.3-2.4 adds only:

- consumption norms;
- compatibility rules;
- knowledge rules;
- two target-integrity constraints on the existing M2 evidence table.

Both migrations are additive and include a manual reverse order. They do not
seed, alter or delete M1 data.

Sprint 2.5 adds no migration and no new infrastructure. The Workbench uses the
existing M2 tables, HousePlatform web application and database connection.

Sprint 2.6 also adds no migration and no new infrastructure. The estimation
input package is assembled from existing M2 and referenced M1 records without
persisting an export, estimate or calculation result.

### Controlled live deployment (Sprint 2.8)

Normal application startup validates that mapped tables exist and never calls
`Base.metadata.create_all()`. Explicit schema creation is restricted to
development/test environments and must use an isolated database; missing tables
fail normal startup with a migration error.

Before live migration, a HousePlatform-only PostgreSQL backup was created at
`backup/m2-sprint-2.8/houseplatform-20261106-200935.dump`. It was restored into
an isolated temporary database. The three M2 SQL migrations below passed a
dry-run and repeat run there, then were applied to live `buildplatform` in order:

1. `20260911_module02_technology_foundation.sql`;
2. `20260913_module02_knowledge_foundation.sql`;
3. `20261106_module02_reconcile_schema.sql`.

The reconciliation migration aligns the legacy auto-created M2 schema with the
reviewed SQL schema. It requires all nine M2 tables to be empty before changing
JSON columns to `jsonb` and adding server defaults. Live verification found nine
M2 tables, 16 `jsonb` columns, zero M2 rows and the expected migration marker.
M1 material/document/category counts remained 394/31/71. Only the HousePlatform
web service was rebuilt and recreated; db and redis containers were unchanged.

## Implemented in Sprint 2.1-2.2

- audited existing M2 and M1-to-M2 foundation;
- fixed the domain boundary in one canonical document;
- added canonical Technology ORM foundation;
- added layers, material requirements, nodes, work steps and evidence references;
- added M1 package acceptance and blocker preservation;
- added draft/update/lifecycle/revision domain services;
- reused platform RBAC and M1 Work Catalog read contract;
- added targeted boundary and migration tests.

## Implemented in Sprint 2.3-2.4

- persisted relative ConsumptionNorm records with canonical unit validation;
- persisted CompatibilityRule and KnowledgeRule records;
- reused typed M1 evidence references for every M2 knowledge scope;
- added deterministic structured-condition evaluation;
- added explicit UNKNOWN/insufficient-evidence semantics;
- added activation blockers, conflict detection and evidence verification;
- extended ACTIVE immutability and revision semantics to all knowledge entities;
- reused the existing platform RBAC without a new auth contour.

## Implemented in Sprint 2.5

- added server-rendered Technology list, filters, detail and revision history;
- added structured DRAFT create/edit controls for layers, material requirements,
  nodes, M1 Work Catalog steps, norms, compatibility and engineering rules;
- added lifecycle controls with backend and frontend RBAC enforcement;
- rendered conditions, selectors, norms, blockers and conflicts in human-readable
  form without a raw JSON editor;
- added read-only M1 material, taxonomy, document, resource and Work Catalog
  lookups without creating or changing M1 records;
- added evidence verification and safe unavailable-reference presentation;
- kept Technology activation on the shared domain validator; knowledge conflicts
  remain explicit warnings and block only the relevant knowledge activation;
- verified the contour against an isolated HousePlatform database.

## M2-to-M5 estimation input contract

`Module5EstimationInputPackage` is the versioned, typed, read-only handoff from
`MODULE_02_KNOWLEDGE_BASE` to the planned `MODULE_05_ESTIMATE_ENGINE`. The
current contract version is `1`. It does not create an M5 aggregate or imply
that the M5 calculation engine is implemented.

The package pins one exact ACTIVE Technology identity and revision and carries:

- material requirements as selectors or canonical M1 references, never Material copies;
- ordered layers and their engineering restrictions;
- ordered M1 Work Catalog codes, stable groups and applicability expressions;
- ACTIVE relative consumption norms with explicit quantities and units;
- calculation-relevant ACTIVE compatibility and knowledge constraints;
- scoped M1 evidence references, verification state, structured blockers and warnings.

Production export rejects DRAFT, REVIEW and ARCHIVED Technology revisions. An
ACTIVE revision is `ready_for_estimation` only when its activation foundation is
valid, at least one ACTIVE norm is available, all included knowledge has verified
evidence, selectors/scopes resolve, units have a known quantity basis, M1 work
codes resolve and active rules do not conflict. Non-ACTIVE knowledge is excluded
with a warning rather than silently promoted.

Unit handling is intentionally conservative. M2 classifies canonical units into
area, area-thickness, volume, length, count or mass bases, but never converts a
quantity. Unknown or unsupported units remain visible and block readiness. M5
must apply object geometry, quantity conversion, waste, rounding and calculation
trace rules.

The builder performs only reads and deterministic DTO assembly. It creates no
database record and exposes explicit `no_object_quantity_result`,
`no_price_result` and `no_side_effects` invariants. Prices, provider work costs,
material resolution, estimate lines, totals, procurement and project geometry
remain outside Module №2.

## Implemented in Sprint 2.6

- audited the planned M5 boundary and found no existing estimate engine or conflicting contract;
- added strict immutable DTOs for the M2-to-M5 estimation input package;
- added deterministic read-only assembly from one exact ACTIVE Technology revision;
- reused M1 canonical units and Work Catalog through read-only services;
- propagated evidence traceability, blockers, warnings and applicability conditions;
- added contract, serialization, revision pinning, no-write and ownership-boundary tests;
- kept M5 calculations, persistence, API and UI out of scope.

## Implemented in Sprint 2.7

- audited formal Module №2 widgets and Quick Actions in code and live read-only data;
- reviewed every Workbench contextual action against lifecycle and RBAC guards;
- exposed the existing guarded work-step ordering operation in the UI;
- added explicit confirmation for delete and archive actions;
- distinguished M1 input completeness and Technology activation readiness from M5 readiness;
- documented the actual two-level M1 Work Catalog and its M2/M5 references;
- added no estimate action, migration or M5 behavior.

## Corrective 2.7.C

- amended contract version `1` in place because no deployed M5 consumer exists;
- resolved `work_code -> WorkItem -> work_group` through the read-only M1 service;
- preserved `work_step_id`, Technology step order and stable catalog identities;
- registered one real M2 readiness widget and kept it `DISABLED` during Beta;
- added a real RBAC-protected payload endpoint with DRAFT, REVIEW, ACTIVE,
  ARCHIVED and activation-blocker counts;
- connected safe Workbench GET/create-DRAFT candidates to the existing user-owned
  Quick Action persistence, pinning and run flow without defaults or seeds;
- aligned the passport and canonical module route with Technology Workbench;
- retained `Foundation / Beta` product semantics and added no database migration.

## Sprint 2.8 FINAL closure

- replaced automatic runtime table creation with controlled schema validation;
- backed up, restored and rehearsed all three M2 migrations before applying them
  to the live HousePlatform database;
- activated the real readiness widget as opt-in, without a default placement;
- aligned the passport and Workbench UI with the deployed module status;
- preserved browser login redirect and API authentication for the Workbench;
- verified the new image with 173 targeted tests and the deployed web with
  1530 passing regression tests (two existing security-gate deselections);
- confirmed live health, protected Workbench routes and unchanged M1 data.

## Deferred after Sprint 2.8

- M5 quantity application, conversions, waste, rounding and calculation trace;
- M5 estimate persistence, line items, pricing and totals;
- project/object geometry input and selected-material recalculation;
- explicit Work Catalog ordering, lifecycle and deeper hierarchy, pending an M1 domain decision.

## Non-goals and guards

Module №2 does not calculate prices, estimates, procurement, warehouse stock or
object geometry. It does not create Material, MaterialPrice,
ProviderWorkCostOffer, Supplier, Manufacturer, MaterialDocument or Work Catalog
records. Runtime AI/LLM generation is forbidden.

The Workbench is an internal HousePlatform contour, not a separate application,
Compose project, database service or Module №2 container. It is live in the
HousePlatform web service with the controlled M2 schema described above.

## History

- 17.06.2026: v1.0 initial outline.
- 11.09.2026: v1.1 Sprint 2.1-2.2 boundary lock and Technology foundation.
- 13.09.2026: v1.2 Sprint 2.3-2.4 evidence, norms and knowledge rules foundation.
- 13.09.2026: v1.3 Sprint 2.5 Technology Workbench and guarded moderation UI.
- 13.09.2026: v1.4 Sprint 2.6 typed read-only M2-to-M5 estimation input contract.
- 14.09.2026: v1.5 Sprint 2.7 action/widget review and M1 Work Catalog composition audit.
- 14.09.2026: v1.6 Corrective 2.7.C hierarchy preservation, readiness widget, Quick Actions and navigation closure.
- 06.11.2026: v1.7 Sprint 2.8 controlled migration, web deployment and final M2 closure.
