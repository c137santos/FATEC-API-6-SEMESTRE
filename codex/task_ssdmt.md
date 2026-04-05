# Instruction para Codex - Task SSDMT (Estado Atual)

---

## Objetivo Deste Documento

Documentar o comportamento REAL ja implementado para `SSDMT` e as regras obrigatorias para evolucao da proxima etapa (persistencia Mongo e consumo por notebooks).

Use este arquivo como fonte de verdade antes de editar qualquer task do pipeline ETL.

---

## Estado Atual Implementado

Arquivos principais:
- `backend/tasks/task_process_layers.py`
- `backend/tasks/task_descompact_gdb.py`
- `docker-compose.yml`

Tasks existentes:
- `etl.processar_ssdmt`
- `etl.processar_ssdmt_chunk`
- `etl.extrair_gdb` (decide se usa chunk)
- `etl.finalizar` (ainda placeholder de consolidacao)

Resumo:
- `SSDMT` NAO retorna mais lista gigante no payload Celery.
- O processamento escreve em NDJSON local no volume compartilhado.
- O retorno traz metadados e caminhos dos arquivos (`path`, `records_count`).

---

## Regras Funcionais SSDMT (Obrigatorias)

1. Ler camada via `fiona.open(gdb_path, layer='SSDMT')`.
2. Selecionar somente os dados de interesse:
	- `COD_ID`, `CTMT`, `CONJ`, `COMP`, `DIST`, `geometry`.
3. Limpar obrigatorios:
	- `COD_ID` e `CTMT` com trim; nulo/vazio descarta.
4. Reprojetar `geometry` para `EPSG:4326`.
5. Gravar duas saidas NDJSON:
	- `ssdmt_tabular` (sem geometria)
	- `ssdmt_geo` (Feature GeoJSON)
6. Contabilizar:
	- `total_lidos`, `total`, `descartados`, `falhas_reprojecao`.
7. Limiar de falha:
	- `falhas_reprojecao / total_lidos` > `0.01` deve quebrar a task.

---

## Contrato Atual de Retorno (SSDMT)

Retorno atual de `etl.processar_ssdmt` e `etl.processar_ssdmt_chunk`:

```json
{
  "layer": "SSDMT",
  "job_id": "<id>",
  "ssdmt_tabular": {
	 "storage_type": "ndjson",
	 "path": "/data/tmp/<job_id>/<job_id>_ssdmt_tabular.ndjson",
	 "records_count": 123
  },
  "ssdmt_geo": {
	 "storage_type": "ndjson",
	 "path": "/data/tmp/<job_id>/<job_id>_ssdmt_geo.ndjson",
	 "records_count": 123,
	 "crs": "EPSG:4326"
  },
  "total": 123,
  "total_lidos": 123,
  "descartados": 0,
  "falhas_reprojecao": 0,
  "window": {
	 "start_index": 0,
	 "size": null
  }
}
```

Observacoes:
- `ssdmt_tabular` e `ssdmt_geo` devem manter o mesmo `records_count` quando nao ha descartes/falhas apos validacao.
- No modo chunk, `layer` vira `SSDMT_CHUNK` e existe `chunk_index`.

---

## Estrategia de Chunk (Ja Implementada)

### Ativacao

Controlada por env:
- `SSDMT_PARALLEL_CHUNK_SIZE`

Regra em `etl.extrair_gdb`:
- Se `SSDMT_PARALLEL_CHUNK_SIZE <= 0`: usa task unica `etl.processar_ssdmt`.
- Se `SSDMT_PARALLEL_CHUNK_SIZE > 0` e `total_ssdmt > chunk_size`: cria N subtasks `etl.processar_ssdmt_chunk`.

### Detalhes

- Contagem da camada via `_get_layer_feature_count()`.
- Cada chunk recebe:
  - `chunk_index`
  - `start_index`
  - `chunk_size`
- Cada chunk gera arquivos com sufixo:
  - `_chunk_00000`, `_chunk_00001`, etc.

### Operacao recomendada no momento

Para estabilidade com 1 worker:
- Default atual no compose: `SSDMT_PARALLEL_CHUNK_SIZE=0`.

---

## Parametros de Performance

Definidos por env:
- `SSDMT_BATCH_SIZE` (default `10000`)
- `SSDMT_PROGRESS_LOG_INTERVAL_BATCHES` (default `25`)

Worker (compose atual):
- `CELERY_WORKER_CONCURRENCY` default `2`
- `prefetch-multiplier=1`
- `-O fair`
- `max-tasks-per-child=20`

Para uso conservador em maquina limitada:
- subir com `CELERY_WORKER_CONCURRENCY=1`.

---

## Relacao Entre `ssdmt_tabular` e `ssdmt_geo`

Chave recomendada de ligacao:
- `job_id + cod_id` (ou `job_id + cod_id + ctmt` para reforco)

Campos comuns entre tabular e geo:
- `job_id`, `cod_id`, `ctmt`, `conj`, `comp`, `dist`, `processed_at`.

---

## Excecoes Obrigatorias

A task deve falhar quando:
1. CRS nao identificavel.
2. Falha de reprojecao acima de 1%.
3. Sem registros validos (somente no modo full; chunk pode aceitar vazio local quando `allow_empty=True`).

Mensagens devem incluir contagens (`total_lidos`, `descartados`, `falhas_reprojecao`, `percentual_falhas`).

---

## Finalizacao (Status Atual e Proxima Etapa)

Status atual:
- `etl.finalizar` ainda e placeholder.
- Hoje retorna apenas resumo (`status`, `results_count`, `zip_path`, `tmp_dir`).

Proxima etapa obrigatoria:
- consolidar resultados do chord
- preparar payload definitivo para persistencia no Mongo
- opcionalmente salvar no Mongo na propria `etl.finalizar` ou em task dedicada

### Regras para a proxima IA (Mongo)

1. Nao quebrar formato atual das tasks CTMT/CONJ/SSDMT.
2. Ler `path` NDJSON de `ssdmt_tabular` e `ssdmt_geo` no `results` do chord.
3. Se houver chunks, consolidar todos os arquivos por `job_id`.
4. Persistir com schema consistente para notebook:
	- colecao tabular
	- colecao geo
5. Criar indices minimos:
	- `job_id`
	- `job_id + cod_id`
	- geoespacial em `geometry` quando aplicavel.

---

## Testes Ja Existentes (Cobertura Relevante)

Arquivo:
- `backend/tests/test_task_process_layers.py`

Cobre:
- caminho feliz SSDMT
- descarte por `COD_ID`/`CTMT`
- erro de CRS
- erro por taxa de falha de reprojecao
- erro sem registros validos
- processamento por janela chunk (`task_processar_ssdmt_chunk`)

Arquivo:
- `backend/tests/test_task_descompact_gdb.py`

Cobre:
- orquestracao com chunk em `etl.extrair_gdb` quando habilitado.

---

## Restricoes

- Nao renomear tasks Celery ja publicadas:
  - `etl.processar_ssdmt`
  - `etl.processar_ssdmt_chunk`
  - `etl.extrair_gdb`
  - `etl.finalizar`
- Nao reintroduzir retorno massivo de `records` completos no payload Celery.
- Manter logs operacionais de inicio/progresso/fim.

---

## Checklist de Implementacao para a Proxima IA

1. Ler este documento e confirmar contrato atual das tasks.
2. Implementar consolidacao real na `etl.finalizar` sem quebrar os testes existentes.
3. Adicionar testes para finalizacao com:
	- SSDMT full
	- SSDMT chunk
	- mistura de camadas CTMT/CONJ/SSDMT
4. Validar fluxo end-to-end com 1 worker e com chunk opcional.

