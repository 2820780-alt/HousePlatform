# ATOM Module №1 — REF-4 / REF-5 Approval Record v1.0.1

## Status

**Preliminary approved by user on 2026-07-19.**

## Approved product decisions

1. Generic aliases never resolve automatically to a concrete subtype.
2. REF-5 remains limited to the existing evidence-backed 15 context rules and 13 substitution policies.
3. `cement_screed → dry_screed` remains review-only.
4. `legacy_alias_060–062` use legacy scope and normalized value `gypsum_board_regular`.

## Correction boundary

For `gkl`, `plasterboard`, and `drywall` only `legacy_normalized_value` and `scope`
were corrected to `gypsum_board_regular`.

The following remain unchanged:

- `classification = context_required`;
- `automatic_material_type_resolution_allowed = false`;
- `status = review_required`;
- target candidate lists;
- REF-5 content.

## Fixed counts

- REF-1 material types: **978**.
- REF-4 alias rules: **89**.
- Trusted automatic REF-4 rules: **44**.
- Context/review-only REF-4 rules: **45**.
- REF-5 context rules: **15**.
- REF-5 substitution policies: **13**.
- Active read-only/safety substitutions: **3**.
- REF-5 review items: **10**.
- Automatic replacement/selection: **0**.
- Work→material mappings: **0**.

## Deterministic package identity

- Manifest SHA-256: `5fe5e067d0dd7235ac54062ed34bad640f1689d358b365dc98b728d0e9682ff7`
- Proposed runtime artifact ID: `ref45-runtime-v1-5fe5e067d0dd`
- Codex may validate and integrate only; it may not expand content.
