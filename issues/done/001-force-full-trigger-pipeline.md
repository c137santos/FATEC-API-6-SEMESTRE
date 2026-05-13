## Parent PRD

`issues/prd.md`

## What to build

Adicionar o parâmetro `force_full: bool = False` à função `trigger_pipeline_flow` em `backend/services/pipeline_trigger.py`.

Quando `force_full=True`, o fluxo deve ignorar o caminho de replot (`_trigger_replot_flow`) mesmo que a distribuidora já possua `job_id` com `report_status == 'failed'`, e executar o pipeline completo criando um novo `job_id`. O campo `Distribuidora.job_id` no PostgreSQL deve ser atualizado para o novo job.

O comportamento existente (sem `force_full`) não deve ser alterado.

## Acceptance criteria

- [ ] `trigger_pipeline_flow` aceita `force_full: bool = False` sem quebrar chamadas existentes.
- [ ] Com `force_full=True` e distribuidora com `job_id` + `report_status == 'failed'`, executa o chain completo (14 tasks) em vez do replot (7 tasks).
- [ ] Com `force_full=True`, um novo `job_id` é gerado e persistido no PostgreSQL.
- [ ] Com `force_full=False` (padrão), o comportamento atual é preservado (replot quando `completed` ou `failed`, 409 quando em andamento).
- [ ] Teste cobrindo `force_full=True` adicionado em `backend/tests/test_route_pipeline_trigger.py`.

## Blocked by

Nenhum — pode começar imediatamente.

## User stories addressed

- User story 5
