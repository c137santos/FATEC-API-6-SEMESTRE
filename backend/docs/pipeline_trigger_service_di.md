# Pipeline + Trigger: service agregado com DI no lugar certo

Este guia usa o codigo real do projeto para mostrar o que esta hoje no `/trigger`,
qual o problema de design e como refatorar sem quebrar comportamento.

## Como esta hoje (`backend/routes/pipeline.py`)

```python
@router.post('/trigger', status_code=202, response_model=PipelineTriggerResponse)
async def trigger_pipeline(
    request: PipelineTriggerRequest,
    session: AsyncSession = Depends(get_session),   # <-- DI do Postgres aqui
):
    # 1. consulta Postgres (via session injetada)
    if await distribuidora_job_already_triggered(session, request.distribuidora_id, request.ano):
        raise HTTPException(status_code=409, ...)

    # 2. chama ANEEL (HTTP externo)
    download_url = await resolve_download_url_from_aneel(request.distribuidora_id)

    # 3. enfileira task Celery
    enqueue_result = enqueue_download_gdb(download_url, request.distribuidora_id)

    # 4. grava job_id no Postgres (via session injetada)
    await save_distribuidora_job_tracking(session=session, ...)

    return {...}
```

O endpoint conhece e coordena os quatro passos da pipeline.
Se amanha um passo mudar (ex.: checar score antes de enfileirar),
a mudanca entra na rota — que e camada HTTP, nao de regra de negocio.

## O problema

- `session` e injetada pelo FastAPI e passada manualmente para cada funcao do service.
- A logica de orquestracao (ordem dos passos, regras de guarda) fica dentro do endpoint.
- As funcoes em `pipeline_trigger.py` recebem `session` como parametro, acoplando
  regra de negocio ao ciclo de vida da requisicao HTTP.
- Reuso fora de HTTP (ex.: chamar a mesma pipeline por um job interno) exige reimplementar
  o fluxo ou instanciar sessao artificialmente.

## O que mudar

### 1. Criar uma funcao agregadora em `pipeline_trigger.py`

Mover a orquestracao dos quatro passos para uma unica funcao no service,
que recebe `session` uma so vez e encapsula a ordem:

```python
# backend/services/pipeline_trigger.py  (adicionar ao final do arquivo)

async def trigger_pipeline_flow(
    session: AsyncSession,
    distribuidora_id: str,
    ano: int,
) -> dict:
    """Orquestra os passos da pipeline de download GDB."""
    if await distribuidora_job_already_triggered(session, distribuidora_id, ano):
        raise ValueError('Pipeline ja foi acionada para a distribuidora no ano informado')

    download_url = await resolve_download_url_from_aneel(distribuidora_id)

    enqueue_result = enqueue_download_gdb(download_url, distribuidora_id)

    await save_distribuidora_job_tracking(
        session=session,
        distribuidora_id=distribuidora_id,
        ano=ano,
        job_id=enqueue_result['job_id'],
    )

    return {
        **enqueue_result,
        'distribuidora_id': distribuidora_id,
        'ano': ano,
        'download_url': download_url,
    }
```

### 2. Endpoint vira so tradutor HTTP

```python
# backend/routes/pipeline.py  (substituir o corpo atual)

from backend.services.pipeline_trigger import trigger_pipeline_flow

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
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
```

## Por que so `session` no endpoint e nao Mongo tambem?

Mongo nao entra no `/trigger` hoje. Se entrar (ex.: gravar score de criticidade
apos o enqueue), ele deve ser resolvido dentro do service, nao injetado na rota:

```python
# dentro de trigger_pipeline_flow, ao adicionar score:
from backend.database import get_mongo_async_db

async def trigger_pipeline_flow(session: AsyncSession, ...) -> dict:
    ...
    db = get_mongo_async_db()           # resolvido aqui, sem passar pela rota
    await db['jobs'].insert_one({...})
    ...
```

O endpoint continua recebendo apenas `session` (Postgres). Mongo e resolvido
pelo singleton no service, sem precisar de DI extra na assinatura da rota.

## Beneficio direto

- Endpoint: so converte excecao em status HTTP.
- Service (`trigger_pipeline_flow`): pode ser chamado por job interno, teste unitario
  ou outro service sem passar por HTTP.
- `session` continua sendo injetada pelo FastAPI — correto, pois o ciclo de vida
  dela esta ligado a requisicao.
- Mongo e qualquer outra infra adicional entra no service, nao na assinatura da rota.
