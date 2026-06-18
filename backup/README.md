# Backups

Backups are mandatory for HousePlatform.

Current backup scripts are designed for PostgreSQL running through Docker Compose.

## Stored In Git

- backup scripts;
- restore instructions;
- scheduled task setup scripts.

## Not Stored In Git

- database dump files;
- backup logs.

Dumps are written to `backup/dumps/`.
Logs are written to `backup/logs/`.

Both folders are ignored by Git.

## Manual Backup

Run from the project root:

```powershell
.\backup\scripts\backup-postgres.ps1
```

By default, the script:

- creates `backup/dumps/`;
- creates a PostgreSQL custom dump;
- saves `houseplatform-YYYYMMDD-HHMMSS.dump`;
- keeps the last 14 dumps.

Change retention:

```powershell
.\backup\scripts\backup-postgres.ps1 -Keep 30
```

Start the database container automatically before backup:

```powershell
.\backup\scripts\backup-postgres.ps1 -StartDb
```

## Nightly Backup

Register a Windows Task Scheduler task:

```powershell
.\backup\scripts\register-nightly-backup.ps1
```

Default schedule:

```text
Every day at 23:00
```

Change time:

```powershell
.\backup\scripts\register-nightly-backup.ps1 -At "22:30"
```

Change retention:

```powershell
.\backup\scripts\register-nightly-backup.ps1 -Keep 30
```

The scheduled task runs:

```powershell
.\backup\scripts\nightly-backup.ps1
```

Nightly logs are written to:

```text
backup/logs/
```

Remove the scheduled task:

```powershell
.\backup\scripts\unregister-nightly-backup.ps1
```

## Restore

Restore cleans existing database objects before import.

```powershell
.\backup\scripts\restore-postgres.ps1 -DumpFile .\backup\dumps\houseplatform-YYYYMMDD-HHMMSS.dump
```

## Notes

- Docker must be installed.
- The scheduled script starts the `db` container before making a dump.
- Keep important production backups in external storage too.
