FROM python:3.12-alpine

RUN apk add --no-cache postgresql16-client

RUN pip install --no-cache-dir boto3 pymongo

COPY backup.py /backup.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
