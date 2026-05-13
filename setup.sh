FLAG_FILE="/app/setup_flag/.setup_done"
ENDPOINT_DEC_FEC="http://localhost:8000/etl/load-dec-fec"
ENDPOINT_DIST_SYNC="http://localhost:8000/dist/sync"

uv run alembic -c backend/alembic.ini upgrade head

perform_setup() {    
    until curl -s --head  http://localhost:8000/ > /dev/null; do
      sleep 2
    done

    curl -s -X POST "$ENDPOINT_DIST_SYNC" -H "Content-Type: application/json"
    curl -s -X POST "$ENDPOINT_DEC_FEC" -H "Content-Type: application/json" 

    if [ $? -eq 0 ]; then
        echo "Setup concluído com sucesso."
        touch "$FLAG_FILE"
    else
        echo "Erro durante o setup. Verifique os logs para mais detalhes."
    fi
}

if [ ! -f "$FLAG_FILE" ]; then
    perform_setup &
else
    echo "Setup já foi concluído anteriormente"
fi

exec "$@"