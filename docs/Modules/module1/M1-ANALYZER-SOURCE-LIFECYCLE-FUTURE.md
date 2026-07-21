# M1-ANALYZER-SOURCE-LIFECYCLE-FUTURE

## Status

Fixed post-Module №1 requirement. Do not implement inside REF-6.

## Business rule

The Analyzer must distinguish one-time source harvesting from recurring refresh.

### 1. INITIAL_PRODUCT_HARVEST

Purpose: one-time collection of product/material cards from a selected source.

Allowed:

- discover product categories and product-card URLs;
- extract full product-card data;
- create RawProduct/evidence;
- run normalization, matching and moderation;
- create CatalogProduct/Material only through the existing positive-price Price Gate;
- preserve stable source identity: source ID, external product ID, URL and aliases.

After a successful initial harvest, the source must not perform recurring full product-card discovery by default.

### 2. PRICE_REFRESH

Purpose: recurring price and availability refresh only for products already collected from the source.

Allowed:

- visit known product URLs or use known external product IDs/API records;
- refresh price, previous price, currency, unit, availability and observed_at;
- recover a moved URL only for an already-known source product;
- append/update PriceHistory according to existing idempotency rules.

Forbidden by default:

- full category crawl;
- creation of new product cards discovered after the initial harvest;
- new Material or CatalogProduct caused only by recurring price refresh;
- rewriting normalized technical characteristics unless a separate controlled revalidation is requested.

New cards appearing on the source may be counted diagnostically, but their ingestion is not required and must remain disabled unless an administrator explicitly starts a new harvest/reindex run.

### 3. INITIAL_DOCUMENT_HARVEST

Purpose: one-time discovery and collection of technical documents from a selected source.

Allowed:

- discover document pages and direct document URLs;
- collect certificates, declarations, datasheets, manuals, technical albums and restrictions;
- link evidence to existing materials/products where confidence and ownership rules permit;
- send ambiguous or unlinked documents to review.

### 4. DOCUMENT_REFRESH

Purpose: periodic refresh only for documents that require revalidation.

Refresh candidates:

- documents with expiry/review_due date;
- documents with source-defined update cadence;
- documents whose ETag, Last-Modified, checksum or source metadata changed;
- documents explicitly selected by an administrator.

A document refresh must not trigger a full product-card harvest.

### 5. MANUAL_REINDEX

A repeated full product-card crawl is allowed only as an explicit administrator action, for example when:

- the source catalogue is intentionally re-baselined;
- the first harvest was incomplete or invalid;
- category structure changed materially;
- the administrator accepts that new cards may be ingested.

Manual reindex is never the default recurring schedule.

## Required run types

- `INITIAL_PRODUCT_HARVEST`
- `PRICE_REFRESH`
- `INITIAL_DOCUMENT_HARVEST`
- `DOCUMENT_REFRESH`
- `MANUAL_REINDEX`

## Operational requirements

- Each SourceProfile stores which initial harvests were completed.
- Recurring schedules target price refresh and/or document refresh separately.
- Product and document cursors/checkpoints are independent.
- Price refresh operates from the known-source-product registry, not from category discovery.
- All runs are idempotent and auditable.
- The UI must explain whether a run collects new cards, refreshes prices, or refreshes documents.
- Full product re-harvest requires explicit confirmation.

## Planned implementation

Separate post-completion sprint:

`M1-SOURCE-REFRESH-LIFECYCLE-1`

This requirement must be included in the final Module №1 handoff and in the source-adapter pilot plan.
