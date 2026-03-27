# Celery + Redis: Fluxo de Tarefas Assíncronas

## Visão Geral

O processamento de arquivos GDB (download e descompactação) é feito de forma **assíncrona**, fora do ciclo de resposta da API. Para isso, o projeto usa dois componentes:

| Componente | Papel | Como roda |
|---|---|---|
| **Redis** | Broker — armazena a fila de mensagens | Serviço Docker (`redis`) |
| **Celery** | Worker — consome e executa as tarefas | Serviço Docker (`worker`) |
| **`redis` (Python)** | Driver/cliente — permite o Python falar com o servidor Redis | Pacote instalado via `celery[redis]` |

---

## Fluxo Passo a Passo

```
                        ┌─────────────────────────────────────┐
                        │           Docker Network            │
                        │                                     │
  HTTP Request          │  ┌──────────┐      ┌────────────┐  │
 ─────────────────────► │  │   API    │      │   Redis    │  │
  POST /etl/download    │  │(FastAPI) │─────►│  (broker)  │  │
                        │  └──────────┘  2   └─────┬──────┘  │
                        │       │ 1             3   │         │
                        │       │ enfileira     consome       │
                        │       ▼ tarefa            ▼         │
                        │  resposta 202     ┌────────────┐    │
  HTTP Response         │  task_id          │   Worker   │    │
 ◄───────────────────── │                   │  (Celery)  │    │
                        │                   └────────────┘    │
                        │                        │ 4          │
                        │                        │ executa    │
                        │                        ▼            │
                        │                  download/          │
                        │                  descompactação     │
                        │                  do arquivo GDB     │
                        └─────────────────────────────────────┘
```

### Detalhamento das etapas

1. **A API recebe a requisição** e chama `task.delay()` ou `.apply_async()`, serializando a tarefa como mensagem.
2. **A mensagem é publicada no Redis** (broker) — a API retorna imediatamente com `202 Accepted` + `task_id`, sem bloquear.
3. **O Worker (Celery) consome a mensagem** da fila Redis assim que um slot estiver disponível.
4. **O Worker executa a tarefa** (ex.: `task_download_gdb`, `task_descompact_gdb`) e pode salvar o resultado de volta no Redis (result backend) ou no banco de dados.

### Fluxo atual: download -> extracao -> chord -> finalizacao

No fim da `task_download_gdb`, apos baixar e validar o ZIP, a task de extracao e disparada explicitamente:

```python
signature('etl.extrair_gdb', args=(job_id, str(zip_path))).delay()
```

`etl.extrair_gdb` e o nome registrado da `task_descompact_gdb`.

Depois da validacao de camadas/colunas, a `task_descompact_gdb` dispara um `chord`:

```python
chord(
  [
    signature('etl.processar_ctmt', args=(job_id, gdb_path)),
    signature('etl.processar_ssdmt', args=(job_id, gdb_path)),
    signature('etl.processar_conj', args=(job_id, gdb_path)),
  ],
  signature('etl.finalizar', args=(job_id, zip_path, str(tmp_dir))),
).delay()
```

Resumo do fluxo:

1. API dispara `etl.download_gdb` com `task_download_gdb.delay(job_id, url)`.
2. `etl.download_gdb` baixa e valida ZIP; em sucesso, dispara `etl.extrair_gdb`.
3. `etl.extrair_gdb` extrai o ZIP, localiza `.gdb`, valida schema de `CTMT`, `SSDMT` e `CONJ`.
4. `etl.extrair_gdb` dispara `chord` com 3 tasks paralelas: `etl.processar_ctmt`, `etl.processar_ssdmt`, `etl.processar_conj`.
5. Ao final do header do chord, o callback `etl.finalizar` consolida o resultado.

Se o download falhar (erro HTTP, timeout ou ZIP invalido), a extracao nao e disparada. Se a validacao do GDB falhar, o chord nao e disparado.

---

## Por que dois pacotes para o Redis?

O **servidor Redis** (Docker) e o **cliente Python** são camadas independentes:

```
Python (Worker/API)
      │
      │  usa
      ▼
  redis (pacote Python)   ←── instalado via celery[redis]
      │
      │  protocolo TCP
      ▼
  Redis Server (Docker)   ←── serviço de infraestrutura
```

É a mesma separação do PostgreSQL: o servidor roda no Docker, mas o `psycopg2` é necessário no Python para conectar nele.

---

## Configuração Relevante

### `pyproject.toml`
```toml
dependencies = [
    "celery[redis]>=5.6.2",   # inclui o pacote redis automaticamente
    ...
]
```

### `docker-compose.yml`
```yaml
services:
  redis:            # servidor Redis (broker)
    image: redis:alpine

  worker:           # processo Celery que consome a fila
    command: celery -A backend.tasks.celery_app worker ...
    depends_on:
      - redis

  api:              # FastAPI que enfileira as tarefas
    depends_on:
      - redis
```

### Variável de ambiente
```env
CELERY_BROKER_URL=redis://redis:6379/0
```

O hostname `redis` resolve para o container Redis dentro da rede Docker.

---

## Registro de tasks no worker

As tasks sao carregadas pelo `include` em `backend/tasks/celery_app.py`.

Modulos registrados:

- `backend.tasks.task_download_gdb`
- `backend.tasks.task_descompact_gdb`
- `backend.tasks.task_process_layers`

Nomes de tasks esperados no startup do worker:

- `etl.download_gdb`
- `etl.extrair_gdb`
- `etl.processar_ctmt`
- `etl.processar_ssdmt`
- `etl.processar_conj`
- `etl.finalizar`
