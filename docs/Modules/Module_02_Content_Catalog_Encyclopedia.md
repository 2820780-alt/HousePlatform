# Module 2 / Technology Catalog and Construction Encyclopedia

Status: architecture implemented; taxonomy candidate still awaits product approval.
M2 Core remains COMPLETED; catalog content and encyclopedia content are EMPTY.
No taxonomy or technology content is approved or seeded by this document.

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
No category rows are created until the product owner approves scope and naming.

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
complete residential taxonomy. Packages may then close one category at a time:

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

## Unapproved taxonomy candidate

The following are discussion areas, not stable production codes or seed data:
site preparation; foundations and below-grade parts; floors on ground; walls;
partitions; beams, columns and lintels; slabs; stairs; roof structure and
coverings; roof details and drainage; facades; windows and external doors;
terraces, porches and canopies; perimeter drainage; rough and finish walls;
dry construction; wet-area waterproofing; screeds and floor coverings;
ceilings and internal doors; acoustic insulation; water supply and wastewater;
sanitary fixtures; house water treatment and autonomous sewage; heating,
ventilation and cooling; chimneys; electrical and low-voltage systems; smart
home; internal gas; final installation works. Scope is residential construction,
renovation and apartment/interior repair, not industrial or city infrastructure.

Before approval, decide exact category tree, whether these areas are categories
or cross-cutting facets, names/codes, residential scope rules, and the first
complete category inventory. No production technology is implied by this list.

## Delivery and verification gate

The SQL migration is additive and seeds nothing. Because HousePlatform web uses
a repository bind mount and autoreload, the live schema must be migrated before
registering the ORM model or route. Required order: inspect live schema and disk
space, make a HousePlatform-only backup without pruning older copies, restore it
to an isolated database, run migration twice there, verify M1/M3 counters, then
apply only the reviewed M2 migration to live. Only after that may the M2 code be
activated and `houseplatform-web` rebuilt/recreated. No global Docker prune or
volume deletion is allowed.

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
  introduced. Unapproved taxonomy candidates remain documentation only.
