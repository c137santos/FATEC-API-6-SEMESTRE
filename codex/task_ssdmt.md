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
- `etl.finalizar` (consolida SSDMT e persiste no Mongo)

Resumo:
- `SSDMT` NAO retorna mais lista gigante no payload Celery.
- O processamento escreve em NDJSON local no volume compartilhado.
- O retorno traz metadados e caminhos dos arquivos (`path`, `records_count`).
- `etl.finalizar` consolida arquivos NDJSON (full/chunk), persiste no Mongo e limpa temporarios apos sucesso.

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

## Finalizacao (Payload Definitivo + Persistencia Mongo)

Objetivo da `etl.finalizar` para SSDMT:
- consolidar os resultados `SSDMT` e `SSDMT_CHUNK` por `job_id`
- persistir no Mongo em formato util para notebook
- manter compatibilidade de nomes com notebooks existentes (campos em maiusculo)

### Melhor Estrategia de Persistencia (Recomendada)

Salvar em DUAS colecoes, separando uso tabular e geoespacial:

1. `segmentos_mt_tabular`
- uso principal em notebooks de calculo (`COMP`, agregacoes por `CONJ`, joins com CTMT/CONJ)
- um documento por segmento

2. `segmentos_mt_geo`
- uso em notebook de mapa/plot geoespacial
- um documento por segmento com `geometry` GeoJSON

Justificativa:
- evita documento gigante >16MB
- facilita consultas por `job_id` e por conjunto
- separa workloads tabulares de geoespaciais
- permite indice `2dsphere` sem impactar consulta tabular

### Compatibilidade com Notebooks (Obrigatorio)

Embora o processamento interno use `cod_id`, `ctmt`, `conj`, `comp`, `dist`,
na persistencia final devem ser gravados os aliases em MAIUSCULO:

- `COD_ID`, `CTMT`, `CONJ`, `COMP`, `DIST`
- `job_id`, `processed_at` (metadados em snake_case)

Para geometria, manter campo:
- `geometry` (GeoJSON em EPSG:4326)

Recomendacao de compatibilidade:
- gravar os campos em maiusculo como fonte oficial para notebooks
- opcionalmente manter os minusculos apenas como espelho tecnico temporario

### Contrato de Payload Consolidado em `etl.finalizar`

`etl.finalizar` deve montar um payload consolidado de SSDMT antes de salvar:

```json
{
	"layer": "SSDMT",
	"job_id": "<id>",
	"processed_at": "2026-04-07T10:00:00+00:00",
	"total": 123456,
	"descartados": 123,
	"falhas_reprojecao": 10,
	"sources": {
		"mode": "full|chunked",
		"chunks": 8,
		"tabular_paths": ["/data/tmp/..._ssdmt_tabular_chunk_00000.ndjson"],
		"geo_paths": ["/data/tmp/..._ssdmt_geo_chunk_00000.ndjson"]
	}
}
```

Observacao:
- este payload e de controle/orquestracao
- o volume de dados fica no Mongo (nao retornar `records` no Celery result)

### Schema Recomendado no Mongo

#### Colecao `segmentos_mt_tabular`

```json
{
	"job_id": "<id>",
	"COD_ID": "MT123",
	"CTMT": "CT001",
	"CONJ": "12807",
	"COMP": 153.2,
	"DIST": "404",
	"processed_at": "2026-04-07T10:00:00+00:00"
}
```

#### Colecao `segmentos_mt_geo`

```json
{
	"job_id": "<id>",
	"COD_ID": "MT123",
	"CTMT": "CT001",
	"CONJ": "12807",
	"COMP": 153.2,
	"DIST": "404",
	"processed_at": "2026-04-07T10:00:00+00:00",
	"geometry": {
		"type": "LineString",
		"coordinates": [[-46.0, -23.0], [-46.1, -23.1]]
	}
}
```

### Indices Minimos (Obrigatorios)

Em `segmentos_mt_tabular`:
- `create_index([("job_id", 1)], background=True)`
- `create_index([("job_id", 1), ("COD_ID", 1)], unique=True, background=True)`
- `create_index([("job_id", 1), ("CONJ", 1)], background=True)`
- `create_index([("job_id", 1), ("CTMT", 1)], background=True)`

Em `segmentos_mt_geo`:
- `create_index([("job_id", 1)], background=True)`
- `create_index([("job_id", 1), ("COD_ID", 1)], unique=True, background=True)`
- `create_index([("geometry", "2dsphere")], background=True)`

### Fluxo Recomendado dentro de `etl.finalizar`

1. Filtrar resultados `SSDMT` e `SSDMT_CHUNK` de `results`.
2. Consolidar `path` de `ssdmt_tabular` e `ssdmt_geo`.
3. Ler NDJSON em streaming (sem carregar tudo em memoria).
4. Normalizar nomes para maiusculo (`COD_ID`, `CTMT`, `CONJ`, `COMP`, `DIST`).
5. Fazer escrita idempotente por `job_id`:
	- `delete_many({"job_id": job_id})` nas 2 colecoes
	- `insert_many` em lotes (bulk)
6. Atualizar `jobs` com:
	- `ssdmt_total`, `ssdmt_descartados`, `ssdmt_falhas_reprojecao`, `status`
7. Remover arquivos temporarios NDJSON apos sucesso.

### Tratamento de Falhas e Rollback

Se qualquer erro ocorrer durante consolidacao/persistencia:
1. limpar `segmentos_mt_tabular` e `segmentos_mt_geo` por `job_id`
2. marcar `jobs.status='failed'` com `error_message`
3. relancar excecao

Isso evita meio-job persistido e garante idempotencia de reprocessamento.

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
2. Implementar consolidacao real na `etl.finalizar` para SSDMT sem quebrar os testes existentes.
3. Garantir persistencia com nomes compativeis para notebook (`COD_ID`, `CTMT`, `CONJ`, `COMP`, `DIST`).
4. Criar indices nas colecoes `segmentos_mt_tabular` e `segmentos_mt_geo`.
5. Adicionar testes para finalizacao com:
	- SSDMT full
	- SSDMT chunk
	- mistura de camadas CTMT/CONJ/SSDMT
6. Validar rollback de erro limpando colecoes por `job_id`.
7. Validar fluxo end-to-end com 1 worker e com chunk opcional.
