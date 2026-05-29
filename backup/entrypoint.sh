#!/bin/sh
set -e

# pass-through: docker compose run backup python /backup.py --restore ...
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

# run once on startup: docker compose run -e RUN_NOW=1 backup
if [ "${RUN_NOW:-0}" = "1" ]; then
    exec /usr/local/bin/python /backup.py
fi

# daily at 03:00 UTC
echo "0 3 * * * /usr/local/bin/python /backup.py >> /proc/1/fd/1 2>&1" | crontab -
echo "backup cron scheduled — daily at 03:00 UTC"
exec crond -f -l 2
