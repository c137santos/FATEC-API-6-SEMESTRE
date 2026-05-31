#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"

ENV_CANDIDATES=(
  "$SCRIPT_DIR/.env"
  "$PROJECT_ROOT/backend/.env"
  "$PROJECT_ROOT/.env"
)

set -a
for env_file in "${ENV_CANDIDATES[@]}"; do
  if [[ -f "$env_file" ]]; then
    # shellcheck source=/dev/null
    source "$env_file"
    break
  fi
done
set +a

required_vars=(POSTGRES_USER POSTGRES_DB MONGO_ROOT_USER MONGO_ROOT_PASSWORD)
for var_name in "${required_vars[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "Erro: variável obrigatória '$var_name' não definida."
    echo "Defina as variáveis no ambiente ou em um destes arquivos:"
    printf ' - %s\n' "${ENV_CANDIDATES[@]}"
    exit 1
  fi
done

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Erro: docker-compose.yml não encontrado em '$COMPOSE_FILE'."
  exit 1
fi

echo "==> [1/3] Limpando distribuidora_cnpj no PostgreSQL..."
docker compose -f "$COMPOSE_FILE" exec -T db \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "TRUNCATE TABLE distribuidora_cnpj;"

echo "==> [2/3] Limpando cnpj_enrichment_log no MongoDB..."
docker compose -f "$COMPOSE_FILE" exec -T mongodb \
  mongosh --quiet \
    "mongodb://${MONGO_ROOT_USER}:${MONGO_ROOT_PASSWORD}@localhost:27017/fatec_api?authSource=admin" \
    --eval "db.cnpj_enrichment_log.drop(); print('ok');"

echo "==> [3/3] Rebuild e restart de api e worker..."
docker compose -f "$COMPOSE_FILE" up -d --build api worker

echo ""
echo "Pronto. Rode POST /sync para disparar o enriquecimento de CNPJs."
