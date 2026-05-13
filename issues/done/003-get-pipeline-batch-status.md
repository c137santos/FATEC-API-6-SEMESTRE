## Parent PRD

`issues/prd.md`

## What to build

Implementar o endpoint `GET /pipeline/batch/status` para consulta do estado do lote atual ou do último encerrado.

Adicionar `get_last_batch(mongo_db)` a `backend/services/pipeline_batch.py` (busca o documento mais recente de `batch_runs` por `started_at` decrescente). Adicionar `BatchDistribuidoraStatus` e `BatchStatusResponse` em `backend/core/schemas.py`. Adicionar o endpoint ao `backend/routes/pipeline.py` — retorna 404 se nunca houve lote, ou 200 com o documento do último lote incluindo `is_running`, contagens agregadas e lista de distribuidoras.

Ver seção "Persistência — coleção MongoDB `batch_runs`" do PRD para os campos esperados no documento de resposta.

## Acceptance criteria

- [ ] `GET /pipeline/batch/status` retorna 404 quando não existe nenhum documento em `batch_runs`.
- [ ] Retorna 200 com `is_running: False` quando o último lote está encerrado.
- [ ] Retorna 200 com `is_running: True` quando o lote ainda está em execução.
- [ ] A resposta inclui `batch_id`, `started_at`, `finished_at`, parâmetros usados, contagens (`total`, `pending`, `processing`, `completed`, `failed`, `skipped`) e lista de distribuidoras.
- [ ] Cada item da lista de distribuidoras contém `id`, `nome`, `ano`, `status` e `error` (opcional).
- [ ] Testes de rota cobrindo os três cenários (404, `is_running False`, `is_running True`) criados seguindo o padrão de `test_route_pipeline_trigger.py`.

## Blocked by

- Bloqueado por `issues/002-post-pipeline-batch.md`

## User stories addressed

- User story 11
- User story 12
- User story 13
- User story 14
- User story 15
