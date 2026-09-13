# Module №2 / Technology Knowledge Base v1.2

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

The implemented Technology domain is FOUNDATION and uses the existing platform
lifecycle value `DRAFT`. No Module №2 route, widget or Quick Action is activated.
The historical module-registry `ACTIVE` value is a known metadata inconsistency
to resolve in a separate Module №3 decision.

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

No API or UI is exposed in this sprint, so server route guards remain future
work.

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

### FUTURE_DEPLOYMENT_BLOCKER

The live HousePlatform database must not receive these M2 migrations during this
sprint. Application startup still calls `Base.metadata.create_all()`; therefore
a web image containing the new models must not replace or restart the live web
container before controlled schema-lifecycle approval. Otherwise ORM startup
could create M2 tables outside the reviewed migration flow.

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

## Deferred to Sprint 2.5

- internal Technology Workbench/moderation UI;
- draft-oriented internal API and route guards;
- evidence, validation and conflict-review presentation;
- golden technology packs only after evidence-backed curation.

## Deferred to Sprint 2.6

- explicit M2-to-M5 consumption-norm read contract;
- quantity application, rounding and calculation trace owned by M5;
- selected-material recalculation inputs;
- no price, estimate or object calculation moves into M2.

## Non-goals and guards

Module №2 does not calculate prices, estimates, procurement, warehouse stock or
object geometry. It does not create Material, MaterialPrice,
ProviderWorkCostOffer, Supplier, Manufacturer, MaterialDocument or Work Catalog
records. Runtime AI/LLM generation is forbidden.

## History

- 17.06.2026: v1.0 initial outline.
- 11.09.2026: v1.1 Sprint 2.1-2.2 boundary lock and Technology foundation.
- 13.09.2026: v1.2 Sprint 2.3-2.4 evidence, norms and knowledge rules foundation.
