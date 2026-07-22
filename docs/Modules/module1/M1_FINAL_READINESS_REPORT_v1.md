# ATOM Module No. 1 Final Readiness Report v1

Sprint: M1-CROSS-MODULE-FINAL-REGRESSION-2

Overall status: **PASS_WITH_WARNINGS**

Module No. 1 satisfies the agreed functional Definition of Done, the security-regressed limited-pilot gate, and the governed cross-platform REF portability gate. No deploy was performed. A deploy sprint must still complete manual credential rotation and use the approved portability contract.

## 1. Baseline and scope

- Branch: feature/module1-material-data-hub-docs
- HEAD before sprint: aaf0cb2a0cfec57da71abe1cc792cc026df012b8
- Upstream before sprint: 0 0
- Platform security baseline: aaf0cb2a0cfec57da71abe1cc792cc026df012b8
- Decisions No. 032 through No. 041: unchanged
- Approved REF source, runtime, manifest, and approval content: unchanged
- Module No. 3 files changed: 0
- Module No. 8 files changed: 0
- Module No. 3 tests modified: 0
- Module No. 3 and No. 8 business behavior changed: false
- Old untracked test_module1_final_regression.py: not used
- Existing line-ending status in test_module1_material_normalizer.py: not edited or staged
- Push and deploy: not performed

The readiness commit is created after this report with message: fix(module1): close final production readiness gaps.

## 2. Readiness by concern

| Concern | Result | Meaning |
|---|---|---|
| Agreed Module No. 1 functional DoD | PASS | E2E, price gate, REF reads, Work Cost, documents, exports, widgets, idempotency, and boundaries pass |
| Limited production pilot | PASS_WITH_WARNINGS | Security and CRLF/LF container smoke pass; manual credential rotation remains a pre-deploy action |
| Authoritative REF write model | NOT READY | REF remains governed read-only; review queues and compatibility work are intentionally open |
| Whole Module No. 1 to No. 2 to No. 5 execution | NOT READY | Read contracts pass, but technology, quantity, estimate, and final-cost consumers are future work |

No blended percentage is used because these readiness levels have different product and risk boundaries.

## 3. Production fixes

Three minimal production fixes were retained from the first gate:

1. Material normalization requires a normalized unit before is_ready_for_matching can be true. Unsupported units remain diagnostic raw data and fail closed before matching.
2. Approved REF-4/5 runtime validation is cached. Explicit custom validation remains uncached.
3. Approved REF-6 runtime validation is cached. Explicit custom validation remains uncached.

Security-aware verification changes:

- production readiness E2E now proves anonymous Material Hub is 401 and uses an explicit admin dependency only for authenticated query-budget checks;
- benchmark records anonymous 401 separately and measures query counts only through an authenticated admin path.

No ORM model, migration, API contract, UI layout, Dashboard, Quick Action, widget contract, Module No. 2, Module No. 3, Module No. 5, or Module No. 8 implementation changed.

## 4. Fixed REF baselines

REF-4 and REF-5:

- material type profiles: 978
- aliases: 89
- trusted aliases: 44
- review/context aliases: 45
- duplicate alias keys: 0
- context compatibility rules: 15
- substitution policies: 13
- active read-only/safety substitutions: 3
- review substitutions: 10
- automatic replacements: 0
- work-material mappings from REF-5: 0

REF-6:

- work groups: 24
- works: 209
- NO_MATERIAL: 39
- DIRECT: 80
- CONDITIONAL: 87
- REVIEW_ONLY: 3
- mappings: 193
- safe hints: 82
- conditional hints: 104
- review mappings: 7
- review queue: 10
- legacy material-role evidence: 42
- quantity calculations: 0
- REF-3 formula activation: 0
- SKU selections: 0
- CatalogProduct selections: 0
- material creation: 0
- policy database writes: 0

Source/artifact/approval validation passed in the targeted and full tracked suites. No approved hash was changed.

## 5. Mode matrix and rollback

All six startup combinations passed in the final Linux container built from the validated tracked Windows worktree:

| Main | REF45 | REF6 | Health | Anonymous | Admin | DB writes |
|---|---|---|---:|---:|---:|---:|
| legacy | legacy | legacy | 200 | 401 | 200 | 0 |
| artifact_validation | legacy | legacy | 200 | 401 | 200 | 0 |
| dual_read | legacy | legacy | 200 | 401 | 200 | 0 |
| ref1_read | approved | legacy | 200 | 401 | 200 | 0 |
| ref2_read | approved | legacy | 200 | 401 | 200 | 0 |
| ref3_read | approved | approved | 200 | 401 | 200 | 0 |

Validated rollback:

    ref3_read / approved / approved
    -> ref2_read / approved / legacy
    -> ref1_read / legacy / legacy
    -> legacy / legacy / legacy

Unknown main, REF45, and REF6 modes fail explicitly in E2E. Defaults remain legacy. No silent fallback was introduced.

Isolated database counts remained identical across mode changes:

- Material: 0
- CatalogProduct: 0
- PriceHistory: 0
- MaterialMatchCandidate: 0
- MaterialQualityIssue: 0
- Work Cost offers: 1 test fixture
- SourceTaskResult: 0

## 6. Local E2E, idempotency, and cleanup

Production-readiness E2E: 7 passed.

The positive scenario proves:

- SourceProfile exists;
- stable external ID and source URL are retained;
- positive price, currency, unit, category, supplier, region, characteristics, and document link are ingested;
- dimensions, grade, brand/manufacturer, and technical tokens survive normalization;
- safe existing-material matching does not create a duplicate canonical material;
- positive price enables readiness;
- product page is evidence, not MaterialDocument;
- PDF document evidence validates;
- export preview respects Module No. 5 boundaries;
- repeated processing preserves source identity and idempotency;
- transaction rollback removes fixture data.

Negative scenarios prove:

- missing, zero, negative, and invalid prices fail closed;
- no-price input does not create Material, CatalogProduct, or candidate;
- unsupported unit is not ready for matching;
- ambiguous generic alias does not auto-resolve a subtype;
- REF-5 does not select a replacement;
- REF-6 does not calculate quantity or select SKU;
- Work Cost is absent from product analysis;
- Module No. 2 and No. 5 are not executed;
- anonymous Material Hub is 401.

Main local database counts after E2E cleanup:

- Material: 394
- CatalogProduct: 441
- MaterialAlias: 395
- MaterialAnalog: 0
- PriceHistory: 188
- MaterialMatchCandidate: 54
- MaterialQualityIssue: 26
- Work Cost offers: 0

The E2E checks equality before and after its outer transaction.

## 7. Price, documents, Work Cost, and cross-module contracts

Price Gate:

- canonical readiness requires a positive price observation;
- no-price records remain raw/evidence or cleanup data;
- no-price data is excluded from ready export;
- existing positive prices are not zeroed by no-price scans;
- legacy records are not physically deleted.

Documents and evidence:

- product page and HTML stay source/evidence;
- document link validation remains separate;
- evidence and document references remain traceable;
- no new material is created from a page without positive price.

Work Cost:

- 24 groups and 209 works;
- fixed and range pricing remain distinct;
- provider ownership filter passed in the container;
- work prices remain separate from material prices;
- Module No. 1 does not scrape work prices or calculate an estimate.

Module No. 1 to No. 2:

- exports material type/role hints and constraints;
- does not choose technology or calculate quantity;
- conditional hints require external technology context;
- NO_MATERIAL gets no synthetic role;
- REF-3 formulas remain non-executable;
- contract reads do not write to the database.

Module No. 1 to No. 5:

- positive price is required for ready material export;
- material and Work Cost payloads remain separate;
- source/document traceability remains;
- Module No. 5 owns package rounding, estimate, offer selection, and final costing;
- REF-5 does not auto-replace;
- REF-6 does not select SKU.

## 8. Performance and query baseline

These are diagnostics for the current workstation, not universal SLA values.

| Measurement | Result |
|---|---:|
| Startup import process | 8097.203 ms |
| REF load and memory measurement | 3425.695 ms |
| Current memory after load | 5869.9 KiB |
| Peak memory after load | 44426.8 KiB |
| Artifact validation cold | 79.843 ms |
| Dual read cold | 114.157 ms |
| REF-1 read cold | 77.427 ms |
| REF-2 read cold | 635.289 ms |
| REF-3 read cold | 524.224 ms |
| REF45 approved cold | 40.109 ms |
| REF6 approved cold | 27.324 ms |
| REF45 cached alias median | 0.499 ms |
| REF6 cached hint median | 0.057 ms |

Authenticated read-only SELECT counts:

- overview: 1
- materials: 40
- documents: 3
- work costs: 1

Anonymous Material Hub in the benchmark returned 401 and was not used to claim query performance.

Synthetic 1,000 observations:

- duration: 9903.560 ms
- ready: 600
- review/fail-closed: 400
- duplicate observations: 989
- unique source identities: 11
- database writes: 0

## 9. Docker build, E2E, restart, and security

Final no-cache portability images:

- CRLF tag/digest: `atom-module1-portability:normal-pass` / `sha256:81bf555797164a0309a33725cd7c1d223010dca4a20d46908e89b4d504b49ae7`;
- LF tag/digest: `atom-module1-portability:lf-pass` / `sha256:21c2efa7a5c3570144f5506d72ccb485ba2cee606bb22c132ff0fb4225afb33e`;
- passlib: 1.7.4;
- bcrypt: 4.0.1;
- `.env.docker` files in either image: 0;
- private-key markers in either image: 0;
- credential markers in either image history: 0;
- Docker readiness E2E: 7 passed in CRLF and 7 passed in LF;
- isolated startup, auth/RBAC, mode matrix, four-step rollback and zero policy-load DB writes: passed.

The isolated stack used local disposable QA services. No deploy or remote server operation occurred.

## 10. Artifact portability closure

Decision No. 042 and approval `ref-portability-v1-db5b6b691b8b` replace raw-byte-only cross-platform identity with strict canonical identity while retaining every approved raw SHA-256 as provenance.

- portability manifest canonical SHA-256: `cb6e7864a8f2b08d9b771a78f2d68721c0c4ccca0239af6dd5c8967ed6a89f10`;
- governed pre-existing files: 49;
- CRLF materialization: 49 raw mismatches, 0 canonical mismatches;
- LF materialization: 0 raw mismatches, 0 canonical mismatches;
- canonical aggregate in both images: `96cefa8bfc961692eb52a0a5f5019a0e2441a7e0ff4db2998bc61ec581e34686`;
- original and LF mode matrices: 6 of 6 passed;
- original and LF rollback chains: 4 of 4 passed;
- generated main, REF-4/5 and REF-6 artifacts remained byte-identical.

Only newline materialization and non-semantic JSON representation changes are portable. Semantic values, strings, arrays and text whitespace remain protected. Duplicate keys, BOM, invalid UTF-8/JSON and non-finite numbers fail closed. There is no silent fallback or automatic re-signing.

## 11. Security regression

The platform security commit remains effective:

- no tracked .env.docker;
- local .env.docker remains ignored;
- safe example contains placeholders;
- no credentials in the final image or logs;
- authentication dependency versions are pinned;
- anonymous Material Hub is 401;
- admin is 200;
- non-admin widget catalog is 403;
- public registration is server-owned SUPPLIER;
- public role escalation is blocked;
- profile update cannot elevate role;
- Work Cost ownership is retained.

Module No. 3 and Module No. 8 files and behavior were not changed.

Manual rotations remain required before deployment:

- JWT_SECRET_KEY
- ADMIN_PASSWORD
- credentials in DATABASE_URL
- credentials in DATABASE_URL_SYNC
- REDIS_URL when it contains credentials

## 12. Observability audit

Existing records expose source/task identifiers, action type, task status, started/finished timestamps, result status, source health, price/document outcomes, and sanitized error fields.

Warnings:

- duration is derived rather than stored as a uniform structured metric;
- failure category remains free text;
- fetched/accepted/rejected/moderation/duplicate counters are not first-class and uniform for every path.

No monitoring framework was added. Full sensitive raw payloads and credentials are prohibited from logs.

## 13. Analyzer lifecycle and post-completion epics

The future contract file remains unchanged with SHA-256:

    caf223aab4c7dd9ac5197416f6c6cff0581807250e3d33e3310e44b202fba444

Future modes remain documentation-only:

- INITIAL_PRODUCT_HARVEST performs the full initial card harvest;
- PRICE_REFRESH updates price and availability for known products only;
- PRICE_REFRESH does not create new cards or traverse all categories;
- documents use a separate DOCUMENT_REFRESH;
- MANUAL_REINDEX is the only repeated full harvest.

No Analyzer lifecycle runtime, scheduler, or site adapter was added.

Post-completion epics:

- real site adapters;
- Analyzer Source Lifecycle implementation;
- real external-source pilot;
- authoritative REF write migration under a separate Decision;
- broader Module No. 2 and No. 5 E2E;
- governed authoritative REF write activation.

## 14. Tests and checks

- portability unit/contract suite: 16 passed
- extended targeted REF regression: 272 passed
- Docker production-readiness E2E: 7 passed on CRLF and 7 passed on LF
- full tracked repository suite: 1366 passed, 551 deprecation warnings
- compileall for changed Python paths: passed at sprint close
- configured lint/typecheck: no separate configured command found
- git diff --check: passed at sprint close
- forbidden old untracked regression test: not run
- no automatic internet call was made by tests

Warnings are existing Pydantic, Starlette, datetime.utcnow, and HTTP status deprecations. Manual credential rotation remains mandatory before deployment.

## 15. Final recommendation

Proceed to a separate deploy-preflight sprint, not directly to remote deployment.

That sprint must:

1. complete and record manual credential rotations;
2. verify database backup and restore;
3. verify Decision No. 042 portability approval and canonical digest during the build;
4. repeat image secret scan and health/auth smoke;
5. preserve legacy defaults and rollback controls;
6. obtain explicit deploy authorization.

Module No. 1 is complete under the agreed read-only governed architecture. Authoritative REF writes, site analyzers, and Module No. 2/No. 5 execution remain intentionally outside this readiness result.
