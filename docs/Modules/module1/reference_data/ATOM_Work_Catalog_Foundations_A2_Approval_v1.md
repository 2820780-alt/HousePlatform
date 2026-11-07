# M1 Work Catalog: FOUNDATIONS A2 additive approval v1

Approved: 2026-11-07. Scope: residential FOUNDATIONS content in HousePlatform.

The REF6 baseline is immutable: 24 groups, 209 WorkItems, seed version 1.0,
LF-normalized SHA-256
`2129670ddc418b2ce91a15c5d8a7b82130c352a5405f5a423e4121b57d45d78b`.
Neither the baseline seed nor its REF6 runtime artifacts are changed.

The approved additive file is
`src/modules/module1/seeds/work_catalog_extensions/foundations_a2_v1.json`,
extension id `foundations-a2-v1`, effective catalog version `1.1`.

| New stable work_code | Why the baseline is insufficient | Default unit |
| --- | --- | --- |
| `foundations_concrete_montazh_fundamentnyh_plit_fl` | FL placement is conditional and distinguishable from strip-system work | piece |
| `foundations_concrete_montazh_blokov_fbs` | FBS block assembly serves foundation and basement-wall contexts | piece |
| `foundations_concrete_pogruzhenie_zhelezobetonnyh_svay` | Driven factory-made RC piles are not boring or screw-pile installation | piece |

All three use the existing `foundations_concrete` group and existing `piece`
unit. No provider, price, quantity rule or material-hint activation is approved.
The effective catalog is 209 baseline + 3 extension = 212 unique WorkItems.
New work codes are visible to M1 resolution and M2/M5 contracts, but their
REF6 material hints fail closed to `review_required` until separately reviewed.
Old codes and their REF6 profiles retain their existing meaning and behavior.
