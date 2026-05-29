# Backup and Restore Guide

**System:** Thunderstone  
**Last reviewed:** 2026-05-28

---

## Overview

Backups run daily at 03:00 UTC via the `backup` container. Two types are stored in S3:

| Type | S3 Prefix | Retention |
|---|---|---|
| PostgreSQL full dump | `postgres/` | 7 days (S3 lifecycle policy) |
| MongoDB audit logs | `mongo-audit-logs/` | 7 days (S3 lifecycle policy) |
| Deleted user IDs | `deleted-users/deleted_users.csv` | 7 days (S3 lifecycle policy) |

---

## Listing Available Backups

```bash
# PostgreSQL dumps
aws s3 ls s3://<S3_BUCKET_NAME>/postgres/

# MongoDB dumps
aws s3 ls s3://<S3_BUCKET_NAME>/mongo-audit-logs/
```

---

## Restoring PostgreSQL

Restores the database from a dump and automatically removes any users who had previously requested account deletion.

```bash
docker compose run --rm backup python /backup.py \
  --restore postgres/2026-05-28T03-00-00.dump.gz
```

**What happens:**
1. Downloads the dump from S3
2. Restores it into the PostgreSQL database
3. Downloads `deleted-users/deleted_users.csv` from S3
4. Runs `DELETE FROM users WHERE id IN (...)` to remove deleted users

> The deleted user cleanup is applied automatically. No manual step required.

---

## Restoring MongoDB Audit Logs

Restores audit log documents. Duplicate entries (same `_id`) are silently skipped, so re-running is safe.

```bash
docker compose run --rm backup python /backup.py \
  --restore-mongo mongo-audit-logs/2026-05-28T03-00-00.json.gz
```

**What happens:**
1. Downloads the JSON dump from S3
2. Inserts documents into the `audit_logs` collection
3. Skips any document whose `_id` already exists (idempotent)

---

## Running a Manual Backup

To trigger a backup immediately without waiting for the scheduled run:

```bash
docker compose run --rm -e RUN_NOW=1 backup
```

---

## Locating the Right Dump

Use the timestamp in the S3 key to find the correct point in time. Keys follow the format `YYYY-MM-DDTHH-MM-SS` in UTC.

Example: to restore to the state of May 27th at 03:00 UTC:

```bash
docker-compose run --rm backup python /backup.py \
  --restore postgres/2026-05-27T03-00-00.dump.gz
```

---

## References

- Backup script: `backup/backup.py`
- Backup container entrypoint: `backup/entrypoint.sh`
- Data breach response plan: `docs/security/data-breach-response.md`
