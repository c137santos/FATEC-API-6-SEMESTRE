# Pipeline + Trigger: como agregar novos services no mesmo job Celery

Este guia descreve o desenho que o projeto usa hoje para o endpoint `/trigger`
e mostra como plugar novas regras de negocio no fluxo sem empurrar logica para
camada HTTP e sem criar outro job Celery quando o download continua sendo o mesmo.

Se alguem for agregar outra integracao, como score de criticidade, a regra deste
guia e literal: toda logica de negocio deve entrar no service e continuar
condizente com o contrato do `/trigger`. O endpoint deve continuar funcionando
como adaptador HTTP fino, nao como lugar de orquestracao.

## Objetivo do fluxo atual

Hoje a separacao de responsabilidade esta assim:

- `backend/routes/pipeline.py`: recebe HTTP, injeta `session` e traduz excecoes.
- `backend/services/pipeline_trigger.py`: orquestra o fluxo de negocio.
- `backend/services/etl_download.py`: enfileira o job Celery `etl.download_gdb`.
- `backend/tasks/task_download_gdb.py`: executa o download e encadeia a proxima task.

Em outras palavras: a rota nao decide mais a ordem da pipeline. Quem decide isso e
o service agregador `trigger_pipeline_flow`.

## Mapa rapido do flow

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

```python
# backend/services/pipeline_trigger.py
async def trigger_pipeline_flow(
    session: AsyncSession,
    distribuidora_id: str,
    ano: int,
) -> dict:
    if await distribuidora_job_already_triggered(session, distribuidora_id, ano):
        raise ValueError(
            'Pipeline ja foi acionada para a distribuidora no ano informado'
        )

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

```python
# backend/services/etl_download.py
def enqueue_download_gdb(
    url: str, distribuidora_id: str | None = None
) -> dict[str, str]:
    job_id = str(uuid.uuid4())
    task = task_download_gdb.delay(job_id, url, distribuidora_id)
    return {
        'job_id': job_id,
        'task_id': task.id,
        'status': 'queued',
    }
```

O ponto importante e este: o `job_id` nasce uma vez, no enqueue, e segue sendo a
identidade do processamento. Se voce quer agregar novos services no mesmo flow,
eles devem orbitar esse mesmo `job_id`, nao criar outro.

## Regra pratica: onde cada coisa entra

Use esta regra antes de alterar o codigo:

- Se a mudanca e traduzir request, status HTTP ou schema de resposta: altere a rota.
- Se a mudanca e validar, consultar infra, enriquecer dados ou persistir metadados do fluxo: altere o service agregador.
- Se a mudanca e sobre como o download assinado e colocado na fila: altere `enqueue_download_gdb`.
- Se a mudanca e sobre a execucao assincrona do download ou seu encadeamento: altere a task Celery.

Na maior parte dos casos de extensao, o lugar certo sera `trigger_pipeline_flow`.

## Regra obrigatoria para manter o `/trigger` reutilizavel

Se a mesma logica puder ser chamada por HTTP hoje e por job interno amanha, ela
nao pertence ao endpoint. Ela pertence ao service.

Em termos práticos:

- o endpoint recebe request, injeta dependencias HTTP e traduz excecoes em status;
- o service decide ordem, validacoes, integracoes, persistencia e montagem do resultado;
- o PostgreSQL ja entra no flow como `session: AsyncSession`; se uma nova funcao precisar de banco, ela deve receber essa `session` como parametro dentro do service;
- o endpoint nao pode conter regra que seria perdida ao chamar o flow fora da rota;
- tudo que fizer parte do significado do `/trigger` precisa estar dentro de `trigger_pipeline_flow` ou de helpers chamados por ele.

Se isso nao for respeitado, o sistema fica com dois comportamentos diferentes:

- um quando a pipeline e chamada pela rota;
- outro quando a pipeline e chamada por reuso interno.

Esse e exatamente o desenho que este documento quer evitar.

## Tutorial: adicionando um novo service no mesmo flow

### 1. Decida se o novo service roda antes ou depois do enqueue

Pergunta de projeto:

- O novo service precisa bloquear o disparo? Rode antes do `enqueue_download_gdb`.
- O novo service precisa usar o `job_id` gerado? Rode depois do `enqueue_download_gdb`.
- O novo service faz parte do processamento assincrono do arquivo? Ele provavelmente pertence a task, nao ao endpoint.

Exemplos:

- Validar regra de negocio antes do disparo: antes do enqueue.
- Salvar auditoria com `job_id` e `task_id`: depois do enqueue.
- Baixar outro arquivo em paralelo: isso ja nao e o mesmo job; precisa outro desenho.

### 2. Extraia o comportamento para uma funcao pequena

Nao empilhe regra nova diretamente dentro da rota. O padrao e criar helpers de
service, mantendo `trigger_pipeline_flow` como agregador.

Se o novo helper precisar consultar ou persistir no PostgreSQL, use a mesma
`session` que o `/trigger` recebeu via `Depends(get_session)` e repasse essa
dependencia para a nova funcao. Nao recrie sessao dentro do helper e nao mova a
regra para a rota so porque ela usa banco.

Exemplo de um service novo para registrar auditoria com o mesmo `job_id`:

```python
# backend/services/pipeline_trigger.py
async def save_pipeline_audit(
    session: AsyncSession,
    distribuidora_id: str,
    ano: int,
    job_id: str,
    task_id: str,
) -> None:
    ...
```

Ou, se a dependencia nao for o Postgres da requisicao, resolva dentro do service:

```python
from backend.database import get_mongo_async_db

async def save_pipeline_audit_external(
    distribuidora_id: str,
    ano: int,
    job_id: str,
) -> None:
    db = get_mongo_async_db()
    await db['pipeline_audit'].insert_one(
        {
            'distribuidora_id': distribuidora_id,
            'ano': ano,
            'job_id': job_id,
        }
    )
```

### 3. Agregue o novo passo dentro de `trigger_pipeline_flow`

Este e o ponto central do tutorial. O fluxo cresce no service agregador, e nao na
rota.

```python
async def trigger_pipeline_flow(
    session: AsyncSession,
    distribuidora_id: str,
    ano: int,
) -> dict:
    if await distribuidora_job_already_triggered(session, distribuidora_id, ano):
        raise ValueError(
            'Pipeline ja foi acionada para a distribuidora no ano informado'
        )

    await validate_pipeline_rules(session, distribuidora_id, ano)

    download_url = await resolve_download_url_from_aneel(distribuidora_id)
    enqueue_result = enqueue_download_gdb(download_url, distribuidora_id)

    await save_distribuidora_job_tracking(
        session=session,
        distribuidora_id=distribuidora_id,
        ano=ano,
        job_id=enqueue_result['job_id'],
    )

    await save_pipeline_audit(
        session=session,
        distribuidora_id=distribuidora_id,
        ano=ano,
        job_id=enqueue_result['job_id'],
        task_id=enqueue_result['task_id'],
    )

    return {
        **enqueue_result,
        'distribuidora_id': distribuidora_id,
        'ano': ano,
        'download_url': download_url,
    }
```

O detalhe importante aqui e a ordem:

- tudo que decide se pode ou nao disparar fica antes do enqueue;
- tudo que depende de `job_id` e `task_id` fica depois do enqueue;
- tudo que precisar de PostgreSQL deve receber a `session` ja aberta pelo flow;
- a resposta HTTP continua montada a partir do mesmo contrato.

### Exemplo explicito: agregando score de criticidade sem quebrar o `/trigger`

Imagine que alguem queira incluir uma integracao com score de criticidade antes de enfileirar a pipeline. O erro mais comum e colocar isso na rota, por exemplo:

```python
# errado: regra de negocio no endpoint
@router.post('/trigger')
async def trigger_pipeline(...):
    score = await calculate_criticidade_score(...)
    if score < 0.7:
        raise HTTPException(status_code=409, detail='Score insuficiente')

    return await trigger_pipeline_flow(...)
```

Isso deixa o endpoint "funcionando", mas quebra o reuso: quem chamar `trigger_pipeline_flow` fora do HTTP nao vai executar a regra do score.

O desenho correto e este:

```python
# backend/services/pipeline_trigger.py
async def validate_criticidade_before_trigger(
    session: AsyncSession,
    distribuidora_id: str,
    ano: int,
) -> None:
    # Se a validacao precisar do PostgreSQL, a mesma session do flow entra aqui.
    score = await calculate_criticidade_score(distribuidora_id, ano)
    if score < 0.7:
        raise ValueError('Score de criticidade insuficiente para disparar a pipeline')


async def trigger_pipeline_flow(
    session: AsyncSession,
    distribuidora_id: str,
    ano: int,
) -> dict:
    if await distribuidora_job_already_triggered(session, distribuidora_id, ano):
        raise ValueError(
            'Pipeline ja foi acionada para a distribuidora no ano informado'
        )

    await validate_criticidade_before_trigger(session, distribuidora_id, ano)

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

E a rota continua simples:

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

O motivo e simples: se amanha o mesmo flow for chamado por outro service, por um comando interno ou por um job administrativo, ele continua respeitando exatamente as mesmas regras do `/trigger`, porque a regra mora no lugar certo.

Resumo da regra para banco relacional: o `/trigger` injeta a `session`, o flow
recebe a `session`, e qualquer nova funcao que precise de PostgreSQL tambem deve
receber essa mesma `session` como argumento.

### 4. Preserve o contrato do job compartilhado

Se o objetivo e continuar usando o mesmo job Celery `etl.download_gdb`, preserve:

- a chamada `enqueue_download_gdb(download_url, distribuidora_id)`;
- a geracao unica de `job_id`;
- o retorno com `job_id`, `task_id` e `status`;
- o encadeamento da task `etl.extrair_gdb` em `task_download_gdb`.

Nao crie um segundo `delay()` so para anexar uma regra lateral. Se a regra nao
precisa de processamento assincrono separado, mantenha-a no service agregador.

## Quando criar um service novo versus alterar o existente

Crie um helper novo quando:

- a regra tem responsabilidade propria e nome claro;
- a regra pode ser testada isoladamente;
- a regra pode ser reutilizada em outro fluxo interno.

Altere `trigger_pipeline_flow` diretamente quando:

- a mudanca e so de ordem do fluxo;
- a mudanca apenas conecta passos ja existentes;
- a logica adicional e curta e especifica da orquestracao.

## Padrao recomendado para novas integracoes

Se voce for incluir novos services com frequencia, siga este esqueleto:

```python
async def trigger_pipeline_flow(
    session: AsyncSession,
    distribuidora_id: str,
    ano: int,
) -> dict:
    await preconditions(...)
    context = await collect_context(...)

    enqueue_result = enqueue_download_gdb(context.download_url, distribuidora_id)

    await persist_tracking(..., job_id=enqueue_result['job_id'])
    await run_post_enqueue_hooks(..., enqueue_result=enqueue_result)

    return build_trigger_response(...)
```

Mesmo quando o codigo nao estiver exatamente com esses nomes, a ideia e manter
quatro blocos visiveis:

1. pre-condicoes;
2. resolucao de contexto;
3. enqueue do job compartilhado;
4. persistencia e hooks pos-enqueue.

## O que nao fazer

Evite estes desvios, porque eles reintroduzem o problema antigo:

- colocar regra de negocio dentro de `backend/routes/pipeline.py`;
- injetar novas dependencias de infra na assinatura da rota sem necessidade real;
- criar varios `job_id`s para o mesmo processamento logico;
- duplicar chamadas a Celery quando o download continua sendo unico;
- esconder o fluxo em helpers que nao deixam clara a ordem da pipeline.

## Checklist para extender o flow com seguranca

- O endpoint continua apenas traduzindo HTTP?
- A nova regra entrou em `trigger_pipeline_flow` ou em helper chamado por ele?
- O mesmo `job_id` segue sendo usado como identidade do processamento?
- O enqueue continua centralizado em `enqueue_download_gdb`?
- O novo service roda antes ou depois do enqueue por um motivo claro?
- O retorno para `PipelineTriggerResponse` continua compativel?

Se a resposta for sim para esses pontos, o novo service foi agregado ao flow do
jeito certo: a rota segue fina, a orquestracao continua no service e o job Celery
permanece unico para o download GDB.
