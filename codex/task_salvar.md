Objetivo
Implementar persistência MongoDB no pipeline ETL no callback `etl.finalizar`, sem quebrar o contrato atual das ETLs e mantendo compatibilidade com notebooks atuais.

Contexto obrigatório
- Linguagem: Python
- Celery já configurado
- Mongo já usado no projeto (`task_load_dec_fec.py`)
- Arquivo principal: `backend/tasks/task_process_layers.py`
- Orquestração do chord: `backend/tasks/task_descompact_gdb.py`
- Configs de Mongo: `backend/settings.py`

Contrato atual das ETLs (não alterar)
- `task_processar_ctmt` retorna `layer='CTMT'`, `records`, `total`, `descartados`.
- `task_processar_conj` retorna `layer='CONJ'`, `records`, `total`, `descartados`.
- `task_processar_ssdmt` retorna `layer='SSDMT'` com `ssdmt_tabular.path` e `ssdmt_geo.path`.
- `task_processar_ssdmt_chunk` retorna `layer='SSDMT_CHUNK'` com caminhos NDJSON por chunk.

Regras de persistência
1. Implementar em `etl.finalizar(results, job_id, zip_path, tmp_dir)`.
2. Mapear coleções:
   - CTMT -> `circuitos_mt`
   - CONJ -> `conjuntos`
   - SSDMT/SSDMT_CHUNK -> `segmentos_mt`
3. CTMT e CONJ — modelo **um documento por job** (embedded array):
   - Usar `replace_one({"job_id": job_id}, documento, upsert=True)`.
   - O documento tem: `job_id`, `processed_at`, `total`, `descartados`, `records: [...]`.
   - `records` contém todos os registros com os campos originais em maiúsculo do GDB.
   - Idempotência garantida pelo próprio `replace_one` (substitui se já existir).
   - Justificativa CTMT: tipicamente 200–3.000 circuitos × ~1 KB = 0,2–3 MB, dentro do limite BSON.
   - Justificativa CONJ: volume análogo ao CTMT, sem geometria.
4. SSDMT:
   - Ler NDJSON tabular e geo por caminho.
   - Consolidar múltiplos chunks no callback.
   - Produzir documentos com campos tabulares + campo `geometry` (GeoJSON válido).
5. Preservar nomes de campos conforme original do GDB em maiúsculo (`COD_ID`, `NOME`, `DIST`, `ENE_01`..`ENE_12`, `PERD_*`, `PNTMT_*`, `PNTBT_*`, `CTMT`, `CONJ`, `COMP`). NÃO converter para snake_case.
6. Idempotência:
   - CTMT/CONJ: `replace_one` com `upsert=True` já garante.
   - SSDMT: `delete_many({"job_id": job_id})` antes de inserir em `segmentos_mt`.
7. Índices:
   - `circuitos_mt`: índice único em `job_id`.
   - `conjuntos`: índice único em `job_id`.
   - `segmentos_mt`: índice simples `job_id` + índice único composto `(job_id, COD_ID, CTMT)` + índice geoespacial `2dsphere` em `geometry`.
   - NÃO criar `2dsphere` em `conjuntos` nesta task.
8. Atualizar `jobs` com upsert:
   - Campos: `job_id`, `status`, `ctmt_total`, `ssdmt_total`, `conj_total`, `descartados_por_layer`, `completed_at`, `updated_at`, `error_message`.
   - Sucesso: `status='completed'`, `error_message=None`.
9. Falha durante persistência:
   - Cleanup por `job_id` nas coleções afetadas (para CTMT/CONJ: `delete_many`; para SSDMT: `delete_many`).
   - Upsert em `jobs` com `status='failed'`, `updated_at`, `error_message`.
   - Re-raise da exceção para observabilidade.
10. Falha no header do chord:
   - Implementar errback no `chord` para marcar `jobs.status='failed'` quando ETL-03/04/05 falhar e `etl.finalizar` não for chamado.
   - Ajustar `task_descompact_gdb.py` para registrar esse errback.

Alertas obrigatórios na resposta do Codex
- Registrar explicitamente que `conjuntos` não terá `2dsphere` agora porque `processar_conj` não fornece geometria.
- Registrar que `UNSEMT` está fora do escopo desta task.

Arquivos esperados para alteração
- `backend/tasks/task_process_layers.py`
- `backend/tasks/task_descompact_gdb.py`
- Eventual utilitário de Mongo (se criado, manter simples e sem nova dependência)
- Testes:
  - `backend/tests/test_task_process_layers.py`
  - `backend/tests/test_task_descompact_gdb.py`
  - Novo teste para finalização/rollback/errback, se necessário

Testes mínimos a criar/atualizar
1. `finalizar` persiste CTMT/CONJ/SSDMT full.
2. `finalizar` consolida múltiplos `SSDMT_CHUNK`.
3. `finalizar` cria índices esperados (`job_id`, unique compostos, `2dsphere` só em `segmentos_mt`).
4. Reprocessamento do mesmo `job_id` não duplica.
5. Falha em insert aciona rollback e `jobs.failed`.
6. Falha no header do chord aciona errback e grava `jobs.failed`.

Restrições
- Não mudar nome das tasks Celery existentes.
- Não voltar a retornar payload gigante de SSDMT no Celery result.
- Não adicionar dependências novas sem necessidade.
- Manter logs estruturados com `job_id`.

Formato esperado da saída do Codex
1. Resumo objetivo do que foi implementado.
2. Lista de arquivos alterados.
3. Resultado dos testes executados.
4. Alertas/pendências explícitas (incluindo geometria de CONJ fora do escopo).
