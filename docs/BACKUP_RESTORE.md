# Backup and Restore

## Metadata Backup

For SQLite deployments use:

```bash
creator-dataset-backup --output backups
```

The command uses SQLite's online backup API.

It does **not** copy an actively-written database file directly.

Output:

```text
backups/
└── 20260919T120000Z/
    ├── creator_dataset.sqlite3
    └── manifest.json
```

The manifest records:

- deployment mode
- database backend
- schema version
- storage backend
- whether media is included

## Media Backup

Metadata backup and media backup are intentionally separate.

### Local Object Store

Back up:

```text
data/objects/
```

Recommended:

- filesystem snapshot
- rsync after a snapshot
- ZFS/APFS/Btrfs snapshot where available

The database stores SHA256 values that can be used to verify restored objects.

### S3

Recommended:

- bucket versioning
- lifecycle rules
- replication where required
- provider-native backup/retention policy

The application metadata backup does not duplicate the S3 bucket.

## Restore — Local

1. Stop API, Worker and Scheduler.
2. Restore the SQLite backup file to the configured database path.
3. Restore `data/objects/` if using local object storage.
4. Start the application.
5. Call:

```text
GET /api/system/readiness?deep_storage=true
```

6. Inspect:

```text
GET /api/system/status
```

## Restore — S3

1. Stop API, Worker and Scheduler.
2. Restore the metadata database.
3. Ensure the configured bucket/prefix points to the matching object set.
4. Start the service.
5. Run deep readiness.
6. Repair individual Stage Jobs if objects or derived outputs are missing.

## Upgrade Safety

Before an application upgrade that changes schema:

1. create metadata backup,
2. preserve media/object-store state,
3. deploy new version,
4. allow schema migrations to run,
5. verify readiness,
6. retain old backup until validation succeeds.

## Disaster-recovery Principle

Source-value priority:

```text
1. Raw platform snapshots
2. Original media objects
3. Normalized database rows
4. OCR/STT derived outputs
5. Exports
```

Exports and derived OCR/STT can be regenerated if source artifacts remain intact.
