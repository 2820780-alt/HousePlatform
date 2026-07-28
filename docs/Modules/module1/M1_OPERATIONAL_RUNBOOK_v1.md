# ATOM Module No. 1 Operational Runbook v1

Status: validated for a limited production deploy sprint. Production deployment still requires manual credential rotation, a verified backup, and a separately approved deploy.

## 1. Purpose and boundaries

Module No. 1 is the Material Data Hub. It ingests source observations, normalizes material data, supports matching and moderation, stores append-only price observations and document evidence, exposes governed read-only REF projections, and stores provider work-cost offers separately from material prices.

Module No. 1 must not calculate technology or quantity for Module No. 2, calculate an estimate for Module No. 5, select a SKU through REF-6, execute REF-3 formulas, choose a replacement automatically through REF-5, scrape work costs, or implement the future Analyzer Source Lifecycle.

Module No. 3, Module No. 8, Dashboard, Quick Actions, and shared UI are outside this runbook.

## 2. Security preflight

The platform security baseline is commit aaf0cb2a0cfec57da71abe1cc792cc026df012b8.

Before deployment, prove:

1. Runtime secrets come from a deployment secret store or untracked environment file.
2. No .env file is present in the image.
3. Image filesystem, layers, history, build logs, and container logs contain no known credential values.
4. passlib is 1.7.4 and bcrypt is 4.0.1.
5. Anonymous Material Hub returns 401.
6. Authenticated admin Material Hub and widget catalog return 200.
7. Supplier, contractor, and customer calls to the admin widget catalog return 403.
8. Public registration assigns SUPPLIER; public ADMIN and SUPER_ADMIN requests return 422.
9. Wrong password returns 401, and profile updates cannot elevate role.
10. Provider Work Cost ownership isolation passes.

Never print credential values while checking these conditions.

## 3. Required environment variables

Provide values outside Git and outside the image:

- DATABASE_URL
- DATABASE_URL_SYNC
- REDIS_URL
- JWT_SECRET_KEY
- JWT_ALGORITHM
- JWT_ACCESS_TOKEN_EXPIRE_MINUTES
- JWT_REFRESH_TOKEN_EXPIRE_DAYS
- APP_ENV
- APP_DEBUG
- MAX_UPLOAD_SIZE_MB
- TEMP_UPLOAD_DIR
- MODULE1_REF_RUNTIME_MODE
- MODULE1_REF45_MODE
- MODULE1_REF6_MODE

OLLAMA_BASE_URL and OLLAMA_MODEL are optional platform settings. Module No. 1 readiness does not depend on a locally installed Ollama service.

## 4. Governed mode matrix

| Main mode | REF45 | REF6 | Purpose |
|---|---|---|---|
| legacy | legacy | legacy | Current production-compatible behavior |
| artifact_validation | legacy | legacy | Validate immutable artifacts without reads |
| dual_read | legacy | legacy | Compare projections without writes |
| ref1_read | approved | legacy | Approved REF-1 read projection |
| ref2_read | approved | legacy | Approved REF-1 and REF-2 read projection |
| ref3_read | approved | approved | Approved REF-1 through REF-3 administrative read projection |

Defaults remain legacy. Unknown modes must fail startup explicitly. Mode switches must not write to the database.

## 5. Build and startup

Use the existing repository Docker contract:

    docker compose build --no-cache web
    docker compose up -d --wait
    docker compose ps

Decision No. 042 governs cross-platform REF identity. Raw SHA-256 remains provenance, while approved runtime identity uses strict canonical content SHA-256. JSON object-key order and token whitespace, plus CRLF/LF/CR newline materialization, are portable; array order, string values, text whitespace and business content remain significant. BOM, duplicate JSON keys, invalid UTF-8/JSON and NaN/Infinity fail closed. Both CRLF and LF no-cache Docker builds are validated.

The first startup against an empty database may exceed the health retry window while schema initialization runs. Do not treat starting or unhealthy as ready.

## 6. Health and Material Hub smoke

Check:

- GET /api/v1/health
- GET /api/v1/admin/material-hub/view
- GET /api/v1/admin/material-hub/view/materials
- GET /api/v1/admin/material-hub/view/documents
- GET /api/v1/admin/material-hub/view/work-costs
- GET /api/v1/admin/cabinet/view/modules/1

Expected: health 200, anonymous Material Hub 401, authenticated admin views 200.

Authenticated API smoke also checks /api/v1/auth/me, sources, widget catalog, Work Catalog, export preview, and REF-3 units. Do not hard-code production credentials in commands, scripts, or logs.

## 7. Approval validation

Each enabled read mode must validate source provenance, canonical digest, runtime manifest, portability approval and mode approval before serving traffic. Expected validation is is_valid=true. `raw_exact_match` and `canonical_portable_match` are accepted after strict parsing; the latter must remain observable as a diagnostic. Semantic mismatch and malformed content fail closed. Silent fallback is prohibited.

Do not edit approval manifests, change approved REF bytes, activate review subsets, enable REF-3 formulas, enable REF-5 automatic replacement, or enable REF-6 quantity/SKU selection.

## 8. Rollback

Validated chain:

    ref3_read / approved / approved
    -> ref2_read / approved / legacy
    -> ref1_read / legacy / legacy
    -> legacy / legacy / legacy

For each step update only the governed mode variables, restart web, verify health 200, anonymous 401, admin 200, approval validity, and unchanged database counts.

Emergency rollback sets all three modes to legacy and restarts. Never edit immutable artifacts to force startup.

## 9. Database safety and backup

Before deployment create and verify a backup, record Module No. 1 counts, verify restore, and preserve price history, evidence, supplier ownership, and moderation state.

Any future authoritative REF write, migration, or backfill requires a separate Decision, compatibility-aware rollback release, proof against destructive overwrite, and rollback testing on a disposable copy. Current read modes require no migration or policy-load database mutation.

## 10. Source task failures and observability

Use existing Source, SourceTask, SourceTaskResult, and task log records. Preserve source/task identifiers, action type, timestamps/status, available fetched/accepted/rejected/moderation/price/document/duplicate counts, last success, and sanitized failure summary.

Duration is derived from timestamps. Failure category and several counters are not uniformly structured. These remain governed warnings; do not create a second monitoring framework during an incident.

Never log passwords, tokens, database credentials, full sensitive raw payloads, or developer-local paths.

## 11. Work Cost smoke

Prove 24 groups and 209 works, distinct fixed/range contracts, provider ownership and region filters, separate material/work prices, and no offer selection or estimate calculation in Module No. 1. Source analyzers must not ingest work costs.

## 12. Widgets smoke

Use the existing Module No. 1 widget registry and permission filtering. Admin catalog returns 200; supplier, contractor, and customer admin catalog calls return 403. Widget payloads hide raw/system/debug data, and Work Cost stays separate from material price.

Do not change Dashboard, Quick Actions, or widget contracts during an incident.

## 13. Export preview smoke

Ready material export requires a positive price observation. No-price material is excluded. Source/document evidence remains traceable. Material price and Work Cost remain separate. Module No. 5 owns package rounding, estimate, and final costing.

## 14. Container restart and readback

1. Restart web without recreating the database.
2. Wait for health 200.
3. Login with an existing deployment test account.
4. Read back its role and one permitted Module No. 1 record.
5. Confirm no duplicate material, product, source identity, or price observation.
6. Compare database counts.
7. Remove only disposable test records.

## 15. Governed review queues

Do not activate or auto-resolve:

- REF-2 review queue: 48
- REF-3 unit review queue: 17
- REF-3 packaging review queue: 51
- packaging/REF-2 mismatches: 345
- REF-4/5 review/context aliases: 45
- REF-6 review queue: 10

REF-5 automatic replacements, REF-6 quantity calculations, and REF-6 SKU selections remain zero.

## 16. Credential rotation prerequisite

Before first deployment after the security baseline, manually rotate JWT_SECRET_KEY, ADMIN_PASSWORD, credentials embedded in DATABASE_URL and DATABASE_URL_SYNC, and inspect REDIS_URL for credentials. Record completion outside application logs. Never commit resulting values.

## 17. Analyzer Source Lifecycle: future only

M1-ANALYZER-SOURCE-LIFECYCLE-FUTURE.md is future-only:

- INITIAL_PRODUCT_HARVEST: full initial card harvest
- PRICE_REFRESH: prices and availability for known products only
- INITIAL_DOCUMENT_HARVEST: initial document collection
- DOCUMENT_REFRESH: separate document refresh
- MANUAL_REINDEX: explicit repeated full harvest

Ordinary PRICE_REFRESH must not create new cards or traverse all categories. No lifecycle runtime, scheduler, or source-site adapter is implemented by this runbook.

## 18. Site adapters and external pilot

Real site adapters, internet collection, and a real external-source pilot are post-completion epics. They require source-specific acceptance, rate limits, evidence retention, legal review where applicable, and a separate rollback plan.

## 19. Incident checklist

1. Stop new source tasks without deleting evidence.
2. Record REF modes and approval IDs.
3. Check health, logs, database, and Redis.
4. Classify startup, auth, ingestion, database, or external-source failure.
5. Preserve identifiers and sanitized errors.
6. Roll governed reads back to legacy when validation is implicated.
7. Recheck Material Hub, Work Cost, widgets, and export preview.
8. Compare counts and recent positive price observations.
9. Escalate architecture, migration, security, or data correction separately.

## 20. Prohibited emergency actions

- no force migration or destructive database edit;
- no manual approval artifact editing;
- no silent mode fallback;
- no git add dot;
- no credentials in images, reports, or logs;
- no destructive data fix without verified backup and Decision;
- no remote deploy from an uncommitted or unvalidated tree;
- no Module No. 2, 3, 5, or 8, Dashboard, Quick Action, or shared UI change as an incident shortcut.

## 21. Final local release gate record

The M1-FINAL-LOCAL-RELEASE-SMOKE-1 local gate completed on 2026-07-28 with `PASS_WITH_WARNINGS` and `MODULE_1_COMPLETE_BY_AGREED_LOCAL_DOD`. Its complete evidence is recorded in `M1_FINAL_LOCAL_RELEASE_REPORT_v1.md`.

The validated replay order is:

1. verify the exact branch, HEAD, upstream divergence, empty staging area, and known working-tree exceptions;
2. create a restricted PostgreSQL custom-format backup and prove it with `pg_restore --list`;
3. rotate local database, administrator, and JWT secrets without printing or committing them, then prove both new acceptance and old rejection;
4. build a no-cache image from an exact clean commit and scan its filesystem, history, build log, source context, and final container log;
5. activate `legacy/legacy/legacy` through `ref3_read/approved/approved` one governed step at a time;
6. run health, auth/RBAC, six-tab Material Hub, widgets, Work Catalog, Work Cost ownership, portability, and data-count checks at the applicable steps;
7. restart without clearing PostgreSQL or Redis and prove readback;
8. roll back through the governed mode chain, start the prior image in legacy mode, and restore the final image and modes;
9. remove only explicitly identified disposable smoke records and verify exact before/after counts.

The final validated local image is `atom-module1-local-release:40e10f9-final`, built from commit `40e10f939fa54c8daa06acef414555e2711f6f9e`. The final governed modes are:

- `MODULE1_REF_RUNTIME_MODE=ref3_read`;
- `MODULE1_REF45_MODE=approved`;
- `MODULE1_REF6_MODE=approved`.

The final candidate uses an isolated local port. It is not a production deployment. Production must use its own credentials and backup, must not reuse the local candidate's `APP_DEBUG=true`, and still requires separate deploy authorization.

The local Redis URL contained no credential, so Redis authentication was not rotated and Redis was not flushed. Treat missing Redis authentication as an explicit deployment warning, not as evidence that a production Redis instance may remain unauthenticated.

When reproducing the portability check, convert only the 49 Decision No. 042 governed files. A whole-repository newline rewrite is not a valid portability test because unrelated future documents may intentionally retain raw-byte identity.

The FastAPI test harness must not assume that an HTTP response proves completion of dependency-finalizer commits. For self-cleaning smoke only, use bounded readback before cleanup. Do not change application transaction semantics merely to accommodate the harness.
