# Pipeline ETL: como funciona e como agregar novas tasks Celery

Este guia descreve o desenho atual da pipeline ETL do projeto — uma cadeia
sequencial de tasks Celery onde cada etapa dispara a próxima ao terminar.
Use este documento para entender o fluxo e para plugar novas tasks respeitando
a ordem da pipeline.

## Visão geral da arquitetura

```
HTTP POST /pipeline/trigger
        │
        ▼
┌──────────────────────────────────────────────────────────────────┐
│  trigger_pipeline_flow (service / orquestrador)                   │
│                                                                  │
│  1. valida, resolve URL, cria job_id                             │
│  2. task_download_gdb.delay(job_id, ...)   ← pipeline ETL        │
│  3. task_pos_etl.delay(job_id, ...)        ← tasks pós-ETL       │
│     (quantas forem necessárias, mesmo job_id)                    │
└──────────────────────────────────────────────────────────────────┘
        │                              │
        ▼  pipeline ETL                ▼  tasks pós-ETL
┌────────────────────────────┐   ┌────────────────────────────────┐
│  etl.download_gdb          │   │  etl.minha_etapa               │
│  → etl.extrair_gdb         │   │  (aguarda job completed no     │
│  → chord [ctmt, conj,      │   │   MongoDB antes de executar)   │
│    unsemt, ssdmt]           │   └────────────────────────────────┘
│  → etl.finalizar            │
│  (persiste, marca completed)│
└────────────────────────────┘
```

O `job_id` nasce uma vez no service e identifica todo o processamento.
Dentro da pipeline ETL, cada task encadeia a próxima via `signature(...).delay()`.
Tasks pós-ETL são disparadas **pelo orquestrador** (`pipeline_trigger.py`) no
mesmo momento, usando o mesmo `job_id`, mas aguardam o job ser marcado como
`completed` no MongoDB antes de executar sua lógica.

## Separação de responsabilidades

| Camada | Arquivo | Papel |
|--------|---------|-------|
| Rota HTTP | `backend/routes/pipeline.py` | Recebe request, injeta session, traduz exceções |
| Service agregador | `backend/services/pipeline_trigger.py` | Valida, resolve URL, cria job_id, dispara ETL + tasks pós-ETL |
| Tasks Celery | `backend/tasks/task_*.py` | Execução assíncrona, encadeia próxima etapa |
| Celery app | `backend/tasks/celery_app.py` | Configuração do broker, lista de tasks registradas |

## Código real do fluxo

### Rota (adaptador HTTP fino)

```python
# backend/routes/pipeline.py
@router.post('/trigger', status_code=202, response_model=PipelineTriggerResponse)
async def trigger_pipeline(
    request: PipelineTriggerRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await trigger_pipeline_flow(
            session=session,
            distribuidora_id=request.distribuidora_id,
            ano=request.ano,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
```

### Service agregador (orquestra o disparo)

```python
# backend/services/pipeline_trigger.py
async def trigger_pipeline_flow(
    session: AsyncSession,
    distribuidora_id: str,
    ano: int,
) -> dict:
    if await distribuidora_job_already_triggered(session, distribuidora_id, ano):
        raise ValueError(
            'Pipeline já foi acionada para a distribuidora no ano informado'
        )

    dist_name = await _get_distribuidora_name(session, distribuidora_id, ano)
    download_url = await resolve_download_url_from_aneel(distribuidora_id)
    job_id = str(uuid.uuid4())

    task = task_download_gdb.delay(job_id, download_url, distribuidora_id)

    await save_distribuidora_job_tracking(
        session=session,
        distribuidora_id=distribuidora_id,
        ano=ano,
        job_id=job_id,
    )

    return {
        'job_id': job_id,
        'task_id': task.id,
        'status': 'queued',
        'distribuidora_id': distribuidora_id,
        'ano': ano,
        'download_url': download_url,
    }
```

### Tasks Celery (pipeline sequencial)

Cada task encadeia a próxima via `signature(...)`:

```python
# task_download_gdb.py (name='etl.download_gdb')
# Ao finalizar download + validação ZIP:
signature('etl.extrair_gdb', args=(job_id, str(zip_path), distribuidora_id)).delay()
```

```python
# task_descompact_gdb.py (name='etl.extrair_gdb')
# Após extrair e validar camadas, dispara processamento paralelo:
chord(
    [
        signature('etl.processar_ctmt', args=(job_id, gdb_path, distribuidora_id)),
        signature('etl.processar_conj', args=(job_id, gdb_path, distribuidora_id)),
        signature('etl.processar_unsemt', args=(job_id, gdb_path, distribuidora_id)),
        signature('etl.processar_ssdmt', args=(job_id, gdb_path, distribuidora_id)),
    ],
    signature('etl.finalizar', args=(job_id, zip_path, str(tmp_dir), distribuidora_id)),
).delay()
```

```python
# task_process_layers.py (name='etl.finalizar')
# Callback do chord: persiste resultados, marca job como completed no MongoDB.
```

## Tutorial: adicionando uma nova task na pipeline

### Passo 1 — Decida ONDE na sequência sua task deve rodar

A pipeline hoje é:

```
download_gdb → extrair_gdb → [ctmt, conj, unsemt, ssdmt] → finalizar
```

Perguntas para decidir o ponto de inserção:

| Cenário | Onde inserir |
|---------|------|
| Precisa dos dados já persistidos no MongoDB? | Opção A: task pós-ETL disparada do orquestrador |
| Pode rodar em paralelo com processamento de camadas? | Opção B: dentro do chord (header) |
| Precisa dos dados GDB extraídos mas antes de persistir? | Opção C: entre etapas da pipeline ETL |

### Passo 2 — Crie a task no padrão do projeto

Crie o arquivo em `backend/tasks/`:

```python
# backend/tasks/task_minha_etapa.py
import logging

from celery import signature
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='etl.minha_etapa')
def task_minha_etapa(self, job_id: str, distribuidora_id: str | None = None) -> dict:
    """Descrição do que essa task faz."""
    logger.info('[task_minha_etapa] Inicio. job_id=%s', job_id)

    # ... lógica de negócio ...

    # Se houver próxima task na cadeia:
    # signature('etl.proxima_etapa', args=(job_id, distribuidora_id)).delay()

    logger.info('[task_minha_etapa] Concluida. job_id=%s', job_id)
    return {'job_id': job_id, 'status': 'done'}
```

Convenções obrigatórias:

- `bind=True` para acesso a `self` (retry, request info)
- `name='etl.<nome_descritivo>'` — prefixo `etl.` é padrão do projeto
- Primeiro argumento é sempre `job_id`
- Log de início e fim com `job_id` para rastreabilidade
- Retorno é sempre um `dict` com pelo menos `job_id` e `status`

### Passo 3 — Registre a task no Celery

Adicione o módulo em `backend/tasks/celery_app.py`:

```python
celery_app = Celery(
    'etl',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    include=[
        'backend.tasks.task_download_gdb',
        'backend.tasks.task_descompact_gdb',
        'backend.tasks.task_process_layers',
        'backend.tasks.task_load_dec_fec',
        'backend.tasks.task_minha_etapa',      # ← adicione aqui
    ],
)
```

### Passo 4 — Encadeie na posição correta

#### Opção A: task pós-ETL (precisa dos dados já persistidos no MongoDB)

Este é o caso mais comum para novas funcionalidades. Sua task precisa que a
pipeline ETL tenha completado (dados no MongoDB) mas faz parte do mesmo
processamento lógico.

**A task é disparada do orquestrador `pipeline_trigger.py`**, usando o mesmo
`job_id`. NÃO coloque nada dentro de `task_finalizar` — ele deve permanecer
responsável apenas por persistir resultados e marcar o job como `completed`.

A sequência é garantida pela própria task, que verifica se o job foi concluído
antes de executar:

```python
# backend/tasks/task_minha_etapa.py
from backend.database import get_mongo_sync_db
from backend.tasks.celery_app import celery_app

WAIT_COUNTDOWN = 30  # segundos entre retries
MAX_WAIT_RETRIES = 60  # máx ~30 min esperando


@celery_app.task(bind=True, max_retries=MAX_WAIT_RETRIES, name='etl.minha_etapa')
def task_minha_etapa(self, job_id: str, distribuidora_id: str | None = None) -> dict:
    """Executa após a pipeline ETL completar."""
    db = get_mongo_sync_db()
    job = db['jobs'].find_one({'job_id': job_id})

    if not job or job.get('status') != 'completed':
        # ETL ainda não terminou — reagenda com countdown
        raise self.retry(countdown=WAIT_COUNTDOWN)

    # Aqui os dados já estão persistidos no MongoDB.
    # ... lógica de negócio ...

    return {'job_id': job_id, 'status': 'done'}
```

E no orquestrador, dispare junto com a ETL:

```python
# backend/services/pipeline_trigger.py
async def trigger_pipeline_flow(...) -> dict:
    ...
    job_id = str(uuid.uuid4())

    # Pipeline ETL (sempre primeiro)
    task = task_download_gdb.delay(job_id, download_url, distribuidora_id)

    # Tasks pós-ETL (mesmo job_id, aguardam ETL completar)
    task_minha_etapa.delay(job_id, distribuidora_id)

    ...
```

Por que este padrão?

- O `job_id` identifica que todas as tasks pertencem ao mesmo processamento
- A sequência é respeitada: a task pós-ETL só executa quando encontra
  `status: 'completed'` no MongoDB
- `task_finalizar` permanece simples e com responsabilidade única
- O orquestrador é o único lugar que decide o que dispara no processamento
- Novas tasks pós-ETL são apenas mais um `.delay()` em `pipeline_trigger.py`

#### Opção B: rodar EM PARALELO com as camadas (dentro do chord)

Adicione sua task na lista `header_tasks` em `task_descompact_gdb`:

```python
header_tasks = [
    signature('etl.processar_ctmt', args=(job_id, gdb_path, distribuidora_id)),
    signature('etl.processar_conj', args=(job_id, gdb_path, distribuidora_id)),
    signature('etl.processar_unsemt', args=(job_id, gdb_path, distribuidora_id)),
    signature('etl.processar_ssdmt', args=(job_id, gdb_path, distribuidora_id)),
    signature('etl.minha_etapa', args=(job_id, gdb_path, distribuidora_id)),  # ← aqui
]
```

`etl.finalizar` só executa quando TODAS as tasks do header terminam.

#### Opção C: inserir ENTRE duas etapas da pipeline ETL

Se sua task precisa rodar entre `download` e `extrair`, altere o encadeamento em
`task_download_gdb.py`:

```python
# Antes (encadeia direto para extrair):
signature('etl.extrair_gdb', args=(job_id, str(zip_path), distribuidora_id)).delay()

# Depois (encadeia para sua task, que por sua vez encadeia extrair):
signature('etl.minha_etapa', args=(job_id, str(zip_path), distribuidora_id)).delay()
```

E na sua task, ao final:

```python
signature('etl.extrair_gdb', args=(job_id, zip_path, distribuidora_id)).delay()
```

### Passo 5 — Escreva testes

Crie `backend/tests/test_task_minha_etapa.py`:

```python
import pytest
from unittest.mock import patch, MagicMock

from backend.tasks.task_minha_etapa import task_minha_etapa


class TestTaskMinhaEtapa:
    @patch('backend.tasks.task_minha_etapa.signature')
    def test_executa_e_encadeia_proxima(self, mock_sig):
        mock_sig.return_value.delay = MagicMock()

        result = task_minha_etapa('job-123', 'dist-456')

        assert result['job_id'] == 'job-123'
        assert result['status'] == 'done'
        # Se encadeia próxima:
        # mock_sig.assert_called_once_with('etl.proxima_etapa', args=(...))

    def test_falha_com_dados_invalidos(self):
        with pytest.raises(RuntimeError):
            task_minha_etapa('job-123', None)
```

Padrão nos testes do projeto: mocke `signature` para não precisar de broker real.

## Princípios que devem ser mantidos

### 1. O `job_id` é único por execução

Nasce em `trigger_pipeline_flow` e percorre toda a cadeia. Não crie novos UUIDs
dentro das tasks — use o mesmo `job_id` para rastrear tudo no MongoDB.

### 2. A rota não orquestra

A rota apenas traduz HTTP. Toda lógica de validação, resolução de URL e disparo
fica no service `trigger_pipeline_flow`. Se amanhã o mesmo fluxo for chamado por
outro service ou job administrativo, ele funciona igual.

### 3. Dentro da pipeline ETL, cada task dispara a próxima

O encadeamento interno da ETL é feito task a task via `signature(...).delay()`:

- Retry individual por etapa
- Visibilidade no Celery Flower
- Composição com `chord` para paralelismo + callback

Mas tasks **pós-ETL** não entram nessa cadeia. Elas são disparadas pelo
orquestrador e se auto-regulam verificando o status do job.

### 4. `task_finalizar` não deve ser alterada

`task_finalizar` tem uma única responsabilidade: persistir os resultados do
chord no MongoDB e marcar o job como `completed`. Não adicione encadeamentos,
lógica de negócio ou `.delay()` de outras tasks dentro dela.

Tasks que precisam rodar após a ETL devem ser disparadas do orquestrador
(`pipeline_trigger.py`) e aguardar o job completar usando retry com countdown.

### 5. O orquestrador decide toda a composição do processamento

Tudo que faz parte de um processamento é disparado em `trigger_pipeline_flow`:

```python
task_download_gdb.delay(job_id, ...)        # pipeline ETL
task_minha_etapa.delay(job_id, ...)          # pós-ETL, mesmo job_id
task_outra_coisa.delay(job_id, ...)          # pós-ETL, mesmo job_id
```

Isso mantém a visibilidade de tudo que compõe um processamento num único lugar.

### 6. Novas dependências de infra entram via task

Se sua etapa precisa de MongoDB, use `get_mongo_sync_db()` dentro da task (como
`task_process_layers` faz). Se precisa de PostgreSQL assíncrono, considere se a
lógica realmente pertence a uma task Celery (tasks Celery são síncronas neste
projeto).

## Registro de tasks existentes

| Nome Celery | Arquivo | O que faz |
|-------------|---------|-----------|
| `etl.download_gdb` | `task_download_gdb.py` | Baixa ZIP do ArcGIS, valida, encadeia `etl.extrair_gdb` |
| `etl.extrair_gdb` | `task_descompact_gdb.py` | Extrai GDB, valida schema, dispara chord de processamento |
| `etl.processar_ctmt` | `task_process_layers.py` | Processa camada CTMT |
| `etl.processar_conj` | `task_process_layers.py` | Processa camada CONJ |
| `etl.processar_ssdmt` | `task_process_layers.py` | Processa camada SSDMT |
| `etl.processar_unsemt` | `task_process_layers.py` | Processa camada UNSEMT |
| `etl.finalizar` | `task_process_layers.py` | Callback do chord: persiste resultados, atualiza status |
| `etl.load_dec_fec_realizado` | `task_load_dec_fec.py` | Carrega CSV DEC/FEC realizado |
| `etl.load_dec_fec_limite` | `task_load_dec_fec.py` | Carrega CSV DEC/FEC limite |

## Checklist para nova task

- [ ] Arquivo criado em `backend/tasks/` com `@celery_app.task(bind=True, name='etl.<nome>')`
- [ ] Módulo adicionado em `celery_app.py` → `include`
- [ ] `job_id` como primeiro argumento
- [ ] Encadeamento na posição certa (`.delay()` em `pipeline_trigger.py` ou alterou task anterior)
- [ ] Logs com `job_id` no início e fim
- [ ] Retorno é `dict` com `job_id` e `status`
- [ ] Testes com `signature` mockado
- [ ] Teste roda verde: `uv run pytest backend/tests/test_task_<nome>.py`

## O que NÃO fazer

- Colocar lógica de negócio dentro da rota (`backend/routes/pipeline.py`)
- Criar múltiplos `job_id` para a mesma execução
- Adicionar `.delay()`, encadeamentos ou lógica dentro de `task_finalizar`
- Disparar tasks pós-ETL de dentro de outras tasks (devem sair do orquestrador)
- Usar `await` em lógica assíncrona dentro de tasks (o worker Celery é síncrono)
- Importar tasks entre si circularmente (use `signature('etl.nome')` para evitar isso)
