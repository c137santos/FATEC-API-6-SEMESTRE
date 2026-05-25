#!/bin/sh
FLAG_FILE="/app/setup_flag/.setup_done"
ENDPOINT_DEC_FEC="http://localhost:8000/etl/load-dec-fec"
ENDPOINT_DIST_SYNC="http://localhost:8000/dist/sync"

uv run alembic -c backend/alembic.ini upgrade head

perform_setup() {
    if curl -s --retry 30 --retry-delay 4 --retry-connrefused http://localhost:8000/ > /dev/null; then
        echo "API detectada! Disparando cargas..."
        
        curl -s --fail -X POST "$ENDPOINT_DIST_SYNC" -H "Content-Type: application/json"
        curl -s --fail -X POST "$ENDPOINT_DEC_FEC" -H "Content-Type: application/json"
        
        echo "Setup concluído com sucesso. Criando flag..."
        mkdir -p "$(dirname "$FLAG_FILE")"
        touch "$FLAG_FILE"
    else
        echo "Erro: API não respondeu a tempo para o setup inicial."
    fi
}

if [ ! -f "$FLAG_FILE" ]; then
    perform_setup &
else
    echo "Setup já foi concluído anteriormente"
fi

exec "$@"