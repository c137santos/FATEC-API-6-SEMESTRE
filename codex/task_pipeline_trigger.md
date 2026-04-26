# Instruction para Codex - Task Pipeline Trigger (ANEEL)

## Objetivo
Implementar um endpoint backend que receba `distribuidora_id` e `ano`, localize o item correspondente no ArcGIS da ANEEL, valide a disponibilidade do serviço e acione o pipeline ETL de forma assíncrona.

O endpoint deve responder imediatamente com `202 Accepted`, sem aguardar o término do processamento.

Decisão funcional confirmada:
- O acionamento do pipeline deve reutilizar o fluxo já existente do `POST /etl/download-gdb`.
- A resposta deve expor `job_id` e `task_id`.
- A validação de entrada com `422` deve ser mantida.

## Contexto
- Projeto backend em FastAPI + SQLAlchemy + Celery.
- Já existe endpoint ETL para enfileirar download:
  - `POST /etl/download-gdb` em [backend/routes/etl.py](backend/routes/etl.py)
- Já existe persistência de distribuidoras na tabela `distribuidoras` com chave composta:
  - `id` (ArcGIS item id)
  - `date_gdb` (ano inteiro)

## Escopo da Task
Criar endpoint:
- `POST /pipeline/trigger`

Payload de entrada:
```json
{
  "distribuidora_id": "<item_id_arcgis>",
  "ano": 2021
}
```

Resposta de sucesso:
- HTTP `202 Accepted`
- Corpo mínimo sugerido:
```json
{
  "status": "queued",
  "job_id": "<uuid>",
  "task_id": "<celery_task_id>",
  "distribuidora_id": "<item_id_arcgis>",
  "ano": 2021,
  "download_url": "<url_final_gdb_ou_item>"
}
```

## Regra de Negócio Esperada
1. Validar payload com Pydantic.
2. Consultar a tabela `distribuidoras` por (`id`, `date_gdb=ano`).
3. Se não encontrar registro, retornar `404` com mensagem clara.
4. Montar URL pública do item ANEEL a partir do id, por exemplo:
   - `https://dadosabertos-aneel.opendata.arcgis.com/documents/{id}`
5. Resolver/validar serviço correspondente no ArcGIS:
   - Aceitar apenas itens compatíveis com Feature Service / download válido.
   - Se o item existir, mas não for compatível, retornar `404` funcional (recurso não encontrado para o caso de uso).
6. Em caso válido, acionar pipeline assíncrono reutilizando a mesma estratégia do endpoint `POST /etl/download-gdb` (task Celery `task_download_gdb.delay(job_id, url)`).
7. Retornar `202` imediatamente ao frontend.

## Requisitos Não Funcionais
- Não bloquear thread com processamento pesado no request.
- Timeouts configurados para chamadas externas.
- Logs estruturados com `job_id`, `distribuidora_id`, `ano`.
- Mensagens de erro estáveis para frontend.

## Contrato de Erros
- `422 Unprocessable Entity`:
  - Payload inválido (id vazio, ano fora do intervalo, tipo incorreto).
- `404 Not Found`:
  - Distribuidora/ano não encontrado no PostgreSQL.
  - Item ArcGIS inexistente para o id informado.
  - Item encontrado, mas não compatível com Feature Service/download.
- `502 Bad Gateway`:
  - ANEEL/ArcGIS indisponível, timeout, erro upstream.
- `500 Internal Server Error`:
  - Falha inesperada local (com log de stack trace).

## OpenAPI / Swagger
Documentar no endpoint:
- Resumo e descrição do fluxo.
- Exemplo de request/response de sucesso.
- Exemplos de erro para `422`, `404`, `502`.

## Sugestão de Estrutura de Implementação
- `backend/core/schemas.py`
  - Criar `PipelineTriggerRequest`.
  - Criar `PipelineTriggerResponse`.
- `backend/services/etl_download.py` (novo)
  - Extrair da rota `POST /etl/download-gdb` a lógica de enfileiramento.
  - Implementar função reutilizável, por exemplo:
    - `enqueue_download_gdb(url: str) -> dict`
  - Responsabilidades da função:
    - gerar `job_id`
    - chamar `task_download_gdb.delay(job_id, url)`
    - retornar `status`, `job_id` e `task_id`
- `backend/services/` (novo arquivo sugerido: `pipeline_trigger.py`)
  - Lógica de lookup no banco (`distribuidora_id`, `ano`).
  - Resolução/validação de URL ArcGIS.
  - Acionar `backend/services/etl_download.py` para enqueue (não chamar endpoint HTTP interno).
- `backend/routes/` (novo arquivo sugerido: `pipeline.py`)
  - Endpoint `POST /pipeline/trigger`.
- `backend/routes/etl.py`
  - Refatorar `POST /download-gdb` para usar `enqueue_download_gdb`, mantendo o mesmo contrato externo.
- `backend/tests/`
  - Testes unitários do service.
  - Testes de rota para cada contrato HTTP.

## Critérios de Aceite
- Endpoint `POST /pipeline/trigger` implementado e documentado no OpenAPI/Swagger.
- `422` para inputs inválidos.
- `404` para item inexistente ou não compatível.
- `502` para indisponibilidade ANEEL/ArcGIS, com log.
- Acionamento assíncrono da SPIKE-01 com resposta `202` imediata.
- Resposta de sucesso contendo `job_id` e `task_id`.
- Refatoração aplicada: `POST /etl/download-gdb` e `POST /pipeline/trigger` reutilizam o mesmo service de enqueue.
- Testes cobrindo:
  - payload inválido
  - item válido
  - item inexistente
  - item incompatível
  - timeout/erro 502 de upstream

## Cenários de Teste (mínimos)
1. `POST /pipeline/trigger` com payload válido retorna `202` e `job_id`.
2. `ano` inválido (ex.: string ou < 1900) retorna `422`.
3. (`id`, `ano`) não encontrado em `distribuidoras` retorna `404`.
4. ArcGIS retorna 404 para item informado retorna `404`.
5. ArcGIS responde timeout/5xx retorna `502`.
6. Enfileiramento chamado exatamente 1 vez quando cenário válido.

## Restrições
- Não alterar contrato dos endpoints ETL existentes sem necessidade.
- Não duplicar lógica de enfileiramento já existente no `download-gdb`; reutilizar a task atual.
- Não chamar endpoint interno via HTTP para reutilizar regra de negócio; reutilizar service Python.
- Não acoplar lógica de longa duração no endpoint HTTP.
- Não adicionar dependências novas sem justificar.

## Observações para Implementação Futura
- Se houver divergência entre "document URL" e "Feature Service URL", priorizar:
  1. validar tipo do item no ArcGIS,
  2. extrair URL canônica de serviço usada pela SPIKE-01,
  3. persistir/metadatar no retorno quando fizer sentido.
- Padronizar erros com mensagens em português para manter consistência com a API atual.
