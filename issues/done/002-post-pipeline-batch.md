## Parent PRD

`issues/prd.md`

## What to build

Implementar o endpoint `POST /pipeline/batch` e o serviço de processamento em lote assíncrono.

Criar `backend/services/pipeline_batch.py` com as funções descritas na seção "Implementation Decisions" do PRD: `_classify_distribuidoras`, `start_batch`, `_run_batch` e `_dispatch_and_poll`. O endpoint deve aceitar `BatchTriggerRequest`, disparar o lote como `asyncio.create_task` (retorno imediato 202) e persistir o estado inicial em `batch_runs` no MongoDB. Retorna 409 se já houver lote em execução (`is_running == True`). Exige autenticação via `get_current_user`.

Ver seções "Novos módulos", "Persistência — coleção MongoDB `batch_runs`", "Polling assíncrono direto no MongoDB" e "Paralelismo dentro do lote" do PRD para todos os detalhes de implementação.

## Acceptance criteria

- [ ] `POST /pipeline/batch` retorna 202 com `batch_id` quando nenhum lote está em execução.
- [ ] `POST /pipeline/batch` retorna 409 quando já há documento com `is_running == True` em `batch_runs`.
- [ ] `POST /pipeline/batch` retorna 401 quando requisição não está autenticada.
- [ ] Documento criado em `batch_runs` contém `is_running: True` e os parâmetros corretos.
- [ ] `_classify_distribuidoras` marca corretamente: sem `job_id` → processar; `report_status == 'completed'` → ignorar; `report_status == 'failed'` → processar; job ativo → ignorar.
- [ ] `is_running` é definido como `False` no `finally` do loop, mesmo em caso de erro inesperado.
- [ ] `_dispatch_and_poll` chama `trigger_pipeline_flow` com `force_full=True` para distribuidoras com `report_status == 'failed'`.
- [ ] Parâmetros `year`, `concurrency`, `poll_interval`, `max_attempts`, `max_retries`, `min_wait` seguem os padrões do PRD.
- [ ] Testes de rota (202, 409, 401) e de `_classify_distribuidoras` criados seguindo o padrão de `test_route_pipeline_trigger.py`.

## Blocked by

- Bloqueado por `issues/001-force-full-trigger-pipeline.md`

## User stories addressed

- User story 1
- User story 2
- User story 3
- User story 4
- User story 6
- User story 7
- User story 8
- User story 9
- User story 10
- User story 16
