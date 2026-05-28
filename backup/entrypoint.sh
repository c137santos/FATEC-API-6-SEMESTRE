#!/bin/sh
set -e

# run once on startup so you can test with: docker-compose run backup
if [ "${RUN_NOW:-0}" = "1" ]; then
    exec python /backup.py
fi

# daily at 03:00 UTC
echo "0 3 * * * /usr/local/bin/python /backup.py >> /proc/1/fd/1 2>&1" | crontab -
echo "backup cron scheduled — daily at 03:00 UTC"
exec crond -f -l 2
