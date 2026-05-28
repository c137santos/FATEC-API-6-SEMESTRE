import gzip
import json
import logging
import os
import smtplib
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from email.mime.text import MIMEText

import boto3
from bson import ObjectId
from pymongo import MongoClient

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
            for chunk in iter(lambda: proc.stdout.read(64 * 1024), b""):
                gz.write(chunk)
            _, stderr = proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"pg_dump failed: {stderr.decode()}")

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

    if errors:
        _write_failure_marker(s3, bucket, timestamp, errors)
        send_failure_email(errors)
        sys.exit(1)


if __name__ == "__main__":
    main()
