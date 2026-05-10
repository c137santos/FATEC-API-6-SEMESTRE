#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

set -a
# shellcheck source=.env
source "$ROOT/.env"
set +a

echo "==> [1/3] Limpando distribuidora_cnpj no PostgreSQL..."
docker compose -f "$ROOT/docker-compose.yml" exec -T db \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "TRUNCATE TABLE distribuidora_cnpj;"

echo "==> [2/3] Limpando cnpj_enrichment_log no MongoDB..."
docker compose -f "$ROOT/docker-compose.yml" exec -T mongodb \
  mongosh --quiet \
    "mongodb://${MONGO_ROOT_USER}:${MONGO_ROOT_PASSWORD}@localhost:27017/fatec_api?authSource=admin" \
    --eval "db.cnpj_enrichment_log.drop(); print('ok');"

echo "==> [3/3] Rebuild e restart de api e worker..."
docker compose -f "$ROOT/docker-compose.yml" up -d --build api worker

echo ""
echo "Pronto. Rode POST /sync para disparar o enriquecimento de CNPJs."
