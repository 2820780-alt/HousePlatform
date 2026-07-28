# ATOM Module No. 1 Final Local Release Report v1

Sprint: M1-FINAL-LOCAL-RELEASE-SMOKE-1

Date: 2026-07-28

Release gate: **PASS_WITH_WARNINGS**

Completion status: **MODULE_1_COMPLETE_BY_AGREED_LOCAL_DOD**

This was a local-only release gate. No push, production deployment, merge, rebase, new branch, schema migration, or destructive Git operation was performed.

## 1. Baseline and scope

The mandatory baseline was checked before release work:

- branch: `feature/module1-material-data-hub-docs`;
- initial HEAD: `452b7f76fdb814da6018b317b7774c36a40262c1`;
- initial commit: `fix(module1): make REF approvals portable across line endings`;
- initial upstream divergence: `0 0`;
- staged files: none;
- known line-ending-only status in `tests/test_module1_material_normalizer.py`: preserved and never staged;
- untracked `tests/test_module1_final_regression.py`: preserved and never run.

The first credential-rotation attempt stopped on a procedural execution limitation without changing product semantics. Work resumed only under the explicit continuation and result-triage authorization. No mismatch in the mandatory repository baseline was bypassed.

Module No. 3 and Module No. 8 were outside scope and were not changed. Dashboard, Quick Actions, Module No. 2 execution, Module No. 5 costing, authoritative REF writes, site adapters, and Analyzer Source Lifecycle implementation also remained outside scope.

## 2. Backup and local credential rotation

Before rotation, a PostgreSQL custom-format backup was created outside the repository:

- file: `houseplatform-20260728-102033.dump`;
- size: 898221 bytes;
- SHA-256: `9c99ea4b70eb36569e1e09e0ac0adfba5ea043730f055fdfbcda55e58e7f80c5`;
- `pg_restore --list`: passed;
- backup and pre-rotation environment file access: restricted.

New local database, administrator, and JWT secrets were generated with Python's cryptographic `secrets` module. The database role password and the existing canonical administrator password hash were updated transactionally. No administrator was added, and no schema, ownership, or grant change was made. The ignored local environment file was replaced atomically.

Validation proved:

- new database credentials accepted;
- old database credentials rejected;
- new administrator password accepted;
- old administrator password rejected with 401;
- new JWT accepted through the normal login flow;
- old JWT rejected with 401;
- no generated value appeared in tracked files, the image, image history, build log, or final container log.

The local Redis URL contains no credential. Redis authentication could therefore not be rotated or validated; Redis was not flushed. This remains a release warning and must be resolved by the target deployment environment's own secret policy.

Production credentials were not accessed or changed.

## 3. Defect found and corrected

Real HTTP smoke found one Module No. 1 defect: the administrator Work Cost list could return 500 because asynchronous response serialization attempted to lazy-load `ProviderWorkCostOffer.owner`.

The minimal correction eagerly loads the owner on list and single-offer reads. It changed only:

- `app/services/module1_provider_work_cost_offers.py`;
- `tests/test_module1_work_cost_service.py`.

Targeted Work Cost regression: **20 passed**.

The product correction is isolated in commit:

`40e10f939fa54c8daa06acef414555e2711f6f9e` — `fix(module1): eager-load work cost owners for async reads`

No migration, schema change, Module No. 3 change, or Module No. 8 change was required.

## 4. Final image and security evidence

The final no-cache image was built from the exact product commit above:

- tag: `atom-module1-local-release:40e10f9-final`;
- image ID: `sha256:a528dd77f6918f45dda253d43c5af82b328d4c8ddf12da58fa1fc71c0b2358b0`;
- image size: 291465705 bytes;
- saved archive size: 291486208 bytes;
- `passlib`: 1.7.4;
- `bcrypt`: 4.0.1;
- changed Python paths compile: passed.

Image filesystem inspection found 362 files, zero environment files, zero private-key markers, and zero developer-absolute-path hits. Scans of the image, history, build log, final container log, and exact tracked source found zero occurrences of either current or pre-rotation credential values. The tracked-source scan covered 641 files.

The image contains the 30 governed files required at runtime. Another 19 source-only governed documents are intentionally excluded by `.dockerignore`; the clean complete source context validated all 49.

## 5. Governed REF activation

The following sequence passed through isolated candidate restarts:

1. `legacy / legacy / legacy`
2. `ref1_read / legacy / legacy`
3. `ref2_read / legacy / legacy`
4. `ref3_read / legacy / legacy`
5. `ref3_read / approved / legacy`
6. `ref3_read / approved / approved`

At every step:

- health and administrator access passed;
- anonymous Material Hub access remained 401;
- approval and portability validation passed;
- Redis ping passed;
- canonical mismatches were zero;
- silent fallback was absent;
- REF-only database writes were zero;
- Module No. 2 execution, Module No. 5 costing, REF-3 formula execution, REF-5 automatic replacement, REF-6 quantity calculation, and REF-6 SKU selection remained disabled.

Final local modes are:

- `MODULE1_REF_RUNTIME_MODE=ref3_read`;
- `MODULE1_REF45_MODE=approved`;
- `MODULE1_REF6_MODE=approved`.

## 6. API, RBAC, widget, and Work Cost smoke

The final candidate and the post-rollback restored candidate both passed the self-cleaning HTTP smoke:

- health: 200;
- normal registration and login: 200;
- administrator login: 200;
- wrong and old administrator passwords: 401;
- old JWT: 401;
- anonymous Material Hub: 401;
- administrator Material Hub: 200;
- all six Material Hub tabs: 200 with no raw/debug markers;
- administrator widget catalog: 200;
- supplier, contractor, and customer administrator widget catalog: 403;
- Work Catalog: 200;
- fixed and range Work Cost offer creation: 201;
- owner-scoped contractor reads: 200;
- foreign-contractor and customer Work Cost reads: 403;
- multiple widget instances and independent settings readback: passed.

The public supplier Work Cost API returns 403 by the constitutional role matrix. The supported supplier contract is its own Work Cost widget, so no broader API permission was inferred from the sprint wording.

All disposable users, audit records, layouts, widget settings, and Work Cost offers were removed after each smoke.

## 7. Portability and test evidence

- targeted Work Cost regression: 20 passed;
- platform security suite with the real ignored local environment: 12 passed;
- portability unit/contract suite: 16 passed;
- governed LF validation: passed;
- governed CRLF validation: 49 of 49 accepted, with 49 expected raw mismatches and zero canonical mismatches;
- Docker readiness E2E on LF: 7 passed;
- Docker readiness E2E on governed-only CRLF: 7 passed;
- final exact tracked full suite: 1366 passed, 1 skipped, 29 warnings.

The one full-suite skip is the packaged-config comparison that cannot run in a tracked-only snapshot because the ignored `.env.docker` is intentionally absent. That exact case passed in the separate 12-test platform security run using the real ignored local environment. Therefore all 1367 unique tracked tests have passing evidence.

The final full suite used an external tracked-only Windows materialization of the exact product commit. Test-only legacy REF mode overrides preserved each historical test's declared default contract; the final approved-mode behavior was exercised separately by the activation, Docker E2E, restart, rollback, and HTTP smoke checks.

No forbidden untracked regression test was run. No automatic internet call was made by tests.

## 8. Restart, rollback, and data integrity

A restart without clearing PostgreSQL or Redis passed health, governed REF validation, administrator/anonymous checks, full API smoke, and settings readback.

The rollback drill passed:

1. `ref3_read / approved / approved` to `ref2_read / approved / legacy`;
2. to `ref1_read / legacy / legacy`;
3. to `legacy / legacy / legacy`;
4. switch to prior image `atom-module1-local-release:452b7f7-final` in legacy mode;
5. restore final image and final approved read modes.

No schema rollback was needed. The prior image, prior commit, verified database backup, and pre-rotation local environment backup remain available.

Module No. 1 counts before and after the gate were identical:

- Material: 394;
- CatalogProduct: 441;
- MaterialAlias: 395;
- MaterialAnalog: 0;
- PriceHistory: 188;
- moderation records: 26;
- SourceTask: 55;
- MaterialDocument: 31;
- ProviderWorkCostOffer: 0;
- user preferences: 19;
- dashboard widget placements: 5;
- Module No. 8 read-only widget preferences: 0.

The self-cleaning API smoke also restored users to 19, audit events to 9, user dashboard layouts to 0, and Work Cost offers to 0.

## 9. Result triage and warnings

Non-product harness corrections made outside the repository included PowerShell API invocation, Compose override semantics, helper import paths, the `ACTIVE` enum value, bounded post-response database readback, probe packaging, Docker E2E network selection, and limiting CRLF transformation to Decision No. 042 governed artifacts. None changed product semantics.

Remaining warnings:

- local Redis has no authentication to rotate;
- `APP_DEBUG=true` in the isolated local candidate produces verbose SQL logs and is not a production setting;
- REF startup observability is valid but not uniformly structured;
- 29 test warnings are existing dependency/deprecation warnings;
- site adapters, external-source pilot, and Analyzer Source Lifecycle are future epics;
- production secrets, backup, infrastructure, and deploy authorization require a separate deploy-preflight.

## 10. Final decision

The final local candidate is healthy on the isolated local port, uses the exact image built from product commit `40e10f939fa54c8daa06acef414555e2711f6f9e`, and is restored to the approved read-only REF modes. Database counts are unchanged, secrets scans are clean, and rollback is proven.

Release gate: **PASS_WITH_WARNINGS**

Completion status: **MODULE_1_COMPLETE_BY_AGREED_LOCAL_DOD**

No push or production deployment is authorized by this result.
