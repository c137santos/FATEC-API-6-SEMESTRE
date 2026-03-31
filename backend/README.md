# Backend - Inicializacao Rapida

## Documentacao do Celery

- Fluxo atual do ETL assíncrono: `docs/celery_app.md`
- Visao geral Celery + Redis: `docs/celery_redis.md`

## 1) Preparar variaveis de ambiente

Na raiz do projeto:

```bash
cp .env.example .env
```

Preencha os valores obrigatorios do arquivo `.env`.

## 2) Subir servicos com Docker Compose

Na raiz do projeto:

```bash
docker compose up --build -d api worker
```

Os servicos `db`, `mongodb` e `redis` sobem automaticamente por dependencia.

Para conferir status:

```bash
docker compose ps
```

Para ver logs do backend:

```bash
docker compose logs -f api
```

## 3) Rodar migracoes do banco (primeira execucao)

Na raiz do projeto:

```bash
docker compose exec api uv run alembic upgrade head
```

## 4) Testar se a API esta no ar

```bash
curl http://localhost:8000/
```

## 5) Rodar backend sem Docker (opcional)

Se voce estiver dentro do dev container e quiser iniciar so a API localmente:

```bash
cd backend
uv sync
PYTHONPATH=.. uv run uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

Observacao: para esse modo, `db`, `mongodb` e `redis` precisam estar ativos.

## 6) Dev Container: subir tudo automaticamente

Ao iniciar o Dev Container, os servicos de infraestrutura (`db`, `mongodb`, `redis`) e os processos de aplicacao (`uvicorn` e `celery worker`) sobem automaticamente.

Comandos uteis dentro do Dev Container:

```bash
# status dos processos
ps aux | grep -E "uvicorn|celery" | grep -v grep

# logs da API e do worker
tail -f .devcontainer/logs/api.log
tail -f .devcontainer/logs/worker.log

# parar processos manualmente (se necessario)
pkill -f "uvicorn backend.app:app"
pkill -f "celery -A backend.tasks.celery_app worker"
```
