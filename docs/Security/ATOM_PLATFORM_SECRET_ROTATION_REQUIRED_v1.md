# ATOM Platform Secret Rotation Required v1

Status: deployment blocker.

The previously tracked `.env.docker` file contained runtime credentials. Those values must be treated as compromised even after the file is removed from the current Git tree and Docker build context.

## Variables requiring rotation

- `JWT_SECRET_KEY`
- `ADMIN_PASSWORD`
- database passwords embedded in `DATABASE_URL`
- database passwords embedded in `DATABASE_URL_SYNC`

Also verify whether environment-specific credentials are present in `REDIS_URL` or other deployment-only variables before reuse.

## Affected environments

- local developer environments that copied the tracked file;
- GitHub repository history and clones;
- CI or GitHub secrets derived from the tracked values;
- server environment files and container runtime configuration;
- locally cached images or archives built before the security fix.

## Required rotation order

1. Inventory GitHub, CI, server, and local secret stores without printing values.
2. Generate new unique database, JWT, and administrative credentials.
3. Rotate database credentials and update runtime secret stores atomically.
4. Rotate `JWT_SECRET_KEY`; expect existing sessions and refresh tokens to become invalid.
5. Rotate the administrative password through the approved administrative process.
6. Rebuild images from a clean clone and verify that no `.env*` secret file or known old value exists in the filesystem, layers, history, or logs.
7. Revoke and remove old credentials from all environments and local build artifacts.
8. Record independent operational confirmation before deployment approval.

Old values must never be reused or copied into an example file. Git history is not rewritten in this sprint; any later history remediation requires a separately approved repository-security procedure.

Push and deployment remain prohibited until credential owners confirm rotation and a clean Docker security smoke passes.