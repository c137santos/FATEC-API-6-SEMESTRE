import csv
import gzip
import json
import logging
import os
import smtplib
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

import boto3
from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

REQUIRED_ENV_VARS = [
    "S3_BUCKET_NAME",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "MONGO_URI",
    "MAIL_SERVER",
    "MAIL_USERNAME",
    "MAIL_PASSWORD",
    "MAIL_FROM",
]

AUDIT_LOG_COLLECTION = "audit_logs"


class _BsonEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def _upload_and_verify(s3, local_path: str, s3_key: str, bucket: str) -> None:
    s3.upload_file(
        local_path,
        bucket,
        s3_key,
        ExtraArgs={"ServerSideEncryption": "AES256"},
    )
    head = s3.head_object(Bucket=bucket, Key=s3_key)
    if head["ContentLength"] == 0:
        raise RuntimeError(f"uploaded file is empty: s3://{bucket}/{s3_key}")
    log.info("verified s3://%s/%s (%d bytes)", bucket, s3_key, head["ContentLength"])


def backup_postgres(s3, bucket: str, timestamp: str) -> None:
    s3_key = f"postgres/{timestamp}.dump.gz"
    env = os.environ.copy()
    env["PGPASSWORD"] = os.environ["POSTGRES_PASSWORD"]

    with tempfile.NamedTemporaryFile(suffix=".dump.gz", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with gzip.open(tmp_path, "wb") as gz:
            proc = subprocess.Popen(
                [
                    "pg_dump",
                    "-h", os.environ.get("POSTGRES_HOST", "db"),
                    "-U", os.environ["POSTGRES_USER"],
                    "-d", os.environ["POSTGRES_DB"],
                    "--format=plain",
                    "--no-password",
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stderr_chunks: list[bytes] = []
            stderr_thread = threading.Thread(
                target=lambda: stderr_chunks.extend(iter(lambda: proc.stderr.read(4096), b""))
            )
            stderr_thread.start()
            for chunk in iter(lambda: proc.stdout.read(64 * 1024), b""):
                gz.write(chunk)
            proc.stdout.close()
            stderr_thread.join()
            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError(f"pg_dump failed: {b''.join(stderr_chunks).decode()}")

        _upload_and_verify(s3, tmp_path, s3_key, bucket)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    log.info("postgres backup done → %s", s3_key)


def backup_mongo_audit_logs(s3, bucket: str, timestamp: str) -> None:
    s3_key = f"mongo-audit-logs/{timestamp}.json.gz"
    mongo_db = os.environ.get("MONGO_DB", "fatec_api")

    with tempfile.NamedTemporaryFile(suffix=".json.gz", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with MongoClient(os.environ["MONGO_URI"]) as client:
            with gzip.open(tmp_path, "wt", encoding="utf-8") as gz:
                gz.write("[")
                first = True
                for doc in client[mongo_db][AUDIT_LOG_COLLECTION].find({}).batch_size(1000):
                    if not first:
                        gz.write(",")
                    json.dump(doc, gz, cls=_BsonEncoder, ensure_ascii=False)
                    first = False
                gz.write("]")

        _upload_and_verify(s3, tmp_path, s3_key, bucket)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    log.info("mongo audit_logs backup done → %s", s3_key)


def restore_mongo_audit_logs(s3, bucket: str, dump_key: str) -> None:
    """Restaura audit logs do MongoDB a partir de um dump JSON.gz no S3."""
    mongo_db = os.environ.get("MONGO_DB", "fatec_api")

    with tempfile.NamedTemporaryFile(suffix=".json.gz", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        s3.download_file(bucket, dump_key, tmp_path)
        log.info("downloaded %s", dump_key)

        with gzip.open(tmp_path, "rt", encoding="utf-8") as gz:
            docs = json.load(gz)

        if not docs:
            log.info("dump is empty, nothing to restore")
            return

        for doc in docs:
            if "_id" in doc and isinstance(doc["_id"], str):
                from bson import ObjectId
                doc["_id"] = ObjectId(doc["_id"])

        with MongoClient(os.environ["MONGO_URI"]) as client:
            collection = client[mongo_db][AUDIT_LOG_COLLECTION]
            inserted = 0
            skipped = 0
            for doc in docs:
                try:
                    collection.insert_one(doc)
                    inserted += 1
                except DuplicateKeyError:
                    skipped += 1

        log.info("mongo restore done: %d inserted, %d skipped (duplicates)", inserted, skipped)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _write_failure_marker(s3, bucket: str, timestamp: str, errors: list[str]) -> None:
    key = f"failures/{timestamp}.txt"
    try:
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body="\n".join(errors).encode(),
            ServerSideEncryption="AES256",
        )
        log.info("failure marker written → s3://%s/%s", bucket, key)
    except Exception:
        log.exception("could not write failure marker to S3")


def send_failure_email(errors: list[str]) -> None:
    notify_email = os.environ.get("BACKUP_NOTIFY_EMAIL", "thunderstonefatec@gmail.com")
    body = (
        "O backup diário do Thunderstone falhou.\n\n"
        "Erros:\n" + "\n".join(f"  - {e}" for e in errors) + "\n\n"
        "Verifique os logs do container 'backup' para mais detalhes.\n"
        "  docker-compose logs backup"
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = "[Thunderstone] Falha no backup diário"
    msg["From"] = os.environ["MAIL_FROM"]
    msg["To"] = notify_email

    try:
        with smtplib.SMTP(os.environ["MAIL_SERVER"], int(os.environ.get("MAIL_PORT", 587))) as smtp:
            smtp.starttls()
            smtp.login(os.environ["MAIL_USERNAME"], os.environ["MAIL_PASSWORD"])
            smtp.sendmail(os.environ["MAIL_FROM"], [notify_email], msg.as_string())
        log.info("failure email sent to %s", notify_email)
    except Exception:
        log.exception("could not send failure email — failure marker in S3 is the fallback")


DELETED_IDS_PATH = Path(os.getenv("DELETED_IDS_PATH", "/data/deleted_users.csv"))
DELETED_IDS_S3_KEY = "deleted-users/deleted_users.csv"


def backup_deleted_user_ids(s3, bucket: str) -> None:
    if not DELETED_IDS_PATH.exists():
        log.info("no deleted_users.csv found, skipping")
        return

    _upload_and_verify(s3, str(DELETED_IDS_PATH), DELETED_IDS_S3_KEY, bucket)
    log.info("deleted_users.csv uploaded → s3://%s/%s", bucket, DELETED_IDS_S3_KEY)


def restore_postgres(s3, bucket: str, dump_key: str) -> None:
    """Restaura um dump do S3 e remove usuários deletados em seguida."""
    env = os.environ.copy()
    env["PGPASSWORD"] = os.environ["POSTGRES_PASSWORD"]
    pg_host = os.environ.get("POSTGRES_HOST", "db")
    pg_user = os.environ["POSTGRES_USER"]
    pg_db = os.environ["POSTGRES_DB"]

    with tempfile.NamedTemporaryFile(suffix=".dump.gz", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        s3.download_file(bucket, dump_key, tmp_path)
        log.info("downloaded %s", dump_key)

        with gzip.open(tmp_path, "rb") as gz:
            proc = subprocess.Popen(
                ["psql", "-h", pg_host, "-U", pg_user, "-d", pg_db],
                stdin=gz,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            _, stderr = proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"psql restore failed: {stderr.decode()}")

        log.info("postgres restore done")
        _apply_deleted_users_cleanup(s3, bucket, env, pg_host, pg_user, pg_db)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _apply_deleted_users_cleanup(s3, bucket, env, pg_host, pg_user, pg_db) -> None:
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as tmp:
        tmp_path = tmp.name

    try:
        s3.download_file(bucket, DELETED_IDS_S3_KEY, tmp_path)
    except Exception:
        log.info("no deleted_users.csv in S3, skipping cleanup")
        os.unlink(tmp_path)
        return

    try:
        with open(tmp_path, newline="") as f:
            raw = [row[0] for row in csv.reader(f) if row]

        ids = []
        for raw_id in raw:
            try:
                ids.append(int(raw_id))
            except ValueError:
                log.warning("skipping non-integer id in deleted_users.csv: %r", raw_id)

        if not ids:
            log.info("deleted_users.csv is empty, nothing to clean")
            return

        ids_literal = ",".join(str(i) for i in ids)
        sql = f"DELETE FROM users WHERE id IN ({ids_literal});"
        proc = subprocess.run(
            ["psql", "-h", pg_host, "-U", pg_user, "-d", pg_db, "-c", sql],
            env=env,
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"cleanup failed: {proc.stderr.decode()}")

        log.info("removed %d deleted user(s) after restore", len(ids))
    finally:
        os.unlink(tmp_path)


def main() -> None:
    missing = [k for k in REQUIRED_ENV_VARS if k not in os.environ]
    if missing:
        sys.exit(f"missing required env vars: {', '.join(missing)}")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    bucket = os.environ["S3_BUCKET_NAME"]
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "sa-east-1"))

    errors: list[str] = []

    try:
        backup_postgres(s3, bucket, timestamp)
    except Exception as exc:
        log.exception("postgres backup failed")
        errors.append(f"Postgres: {exc}")

    try:
        backup_mongo_audit_logs(s3, bucket, timestamp)
    except Exception as exc:
        log.exception("mongo audit_logs backup failed")
        errors.append(f"MongoDB audit_logs: {exc}")

    try:
        backup_deleted_user_ids(s3, bucket)
    except Exception as exc:
        log.exception("deleted_users.csv backup failed")
        errors.append(f"Deleted IDs: {exc}")

    if errors:
        _write_failure_marker(s3, bucket, timestamp, errors)
        send_failure_email(errors)
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", metavar="S3_KEY", help="Restore a Postgres dump from S3 (e.g. postgres/2026-05-28T03-00-00.dump.gz)")
    parser.add_argument("--restore-mongo", metavar="S3_KEY", help="Restore a MongoDB audit log dump from S3 (e.g. mongo-audit-logs/2026-05-28T03-00-00.json.gz)")
    args = parser.parse_args()

    missing = [k for k in REQUIRED_ENV_VARS if k not in os.environ]
    if missing:
        sys.exit(f"missing required env vars: {', '.join(missing)}")

    bucket = os.environ["S3_BUCKET_NAME"]
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "sa-east-1"))

    if args.restore:
        restore_postgres(s3, bucket, args.restore)
    elif args.restore_mongo:
        restore_mongo_audit_logs(s3, bucket, args.restore_mongo)
    else:
        main()
