# ATOM Module №1 — REF-6 Review v1.0

## Статус

**Preliminary approved by user on 2026-07-21.**

REF-6 authored by the assistant under five approved product rules. Codex may validate and integrate, but may not invent or expand work-material content.

## Baseline

- Work groups: **24**
- Works: **209**
- REF-1 material types: **978**
- Existing role evidence rows: **42**
- Existing executable work→material registry before REF-6: **0**

## Work classification

- `NO_MATERIAL`: **39**
- `DIRECT`: **80**
- `CONDITIONAL`: **87**
- `REVIEW_ONLY`: **3**

## Mapping policy

- Total role mappings: **193**
- Safe type-level role hints: **82**
- Conditional read-only hints: **104**
- Review-only mappings: **7**
- Total review queue: **10**

## Hard boundaries

- Quantity calculation: **0**
- REF-3 formula activation: **0**
- SKU/CatalogProduct selection: **0**
- Automatic Material/CatalogProduct creation: **0**
- Automatic alias/analog writes: **0**
- Database writes: **0**

## Responsibility

- Module №1: allowed material roles/types, conditions and restrictions.
- Module №2: technology, geometry, volume and quantity.
- Module №5: price selection, package rounding and estimate.

## Examples

Safe hints:

- sand cushion → `sand`
- crushed-stone cushion → `crushed_stone`
- geotextile installation → `geotextile`
- metal-tile installation → `metal_tile`
- cable installation → `cable`
- laminate installation → `laminate`

Conditional:

- strip/slab/pile-grillage foundations
- frame wall
- ventilated facade
- wet-zone sheet systems
- underfloor heating
- drainage and stormwater systems

Review-only examples:

- backfill material
- exterior/door slope finish
- generic electrical/water/sewer point
- generic sanitary fixture
- blind-area technology
- bath screen

## Analyzer lifecycle

The separate future Analyzer source lifecycle requirement is not implemented by REF-6 and remains a post-Module №1 task.
