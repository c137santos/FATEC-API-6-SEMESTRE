# Instruction para Codex - Persistência CTMT no MongoDB

---

## Objetivo

Implementar a persistência dos registros da camada `CTMT` na coleção `circuitos_mt` do MongoDB, dentro do callback `etl.finalizar`, mantendo compatibilidade de nomes de campos com os notebooks existentes.

> **Escopo desta task:** apenas o bloco CTMT dentro de `etl.finalizar`. CONJ e SSDMT são tratados em instruções separadas.

---

## Modelo de persistência: um documento por job (embedded array)

O CTMT de um GDB de distribuidora tipicamente possui entre 200 e 3.000 circuitos. Com ~1 KB por registro (50 campos numéricos/string em BSON), o tamanho total fica na faixa de 0,2 MB a 3 MB — bem abaixo do limite de 16 MB do MongoDB. Por isso, o modelo adotado é **um único documento por job**, com todos os registros embutidos em um campo `records`.

Benefícios desse modelo para CTMT:
- `replace_one` com `upsert=True` é atomicamente idempotente — não precisa de `delete_many` + `insert_many`.
- O notebook carrega exatamente como o Excel atual: `pd.DataFrame(doc["records"])`.
- Sem risco de duplicidade parcial de documentos.

Estrutura do documento salvo em `circuitos_mt`:
```
{
  _id:          <ObjectId>,
  job_id:       "abc123",
  processed_at: "2026-04-06T12:00:00+00:00",
  total:        247,
  descartados:  3,
  records: [
    { COD_ID, NOME, DIST, ENE_01..ENE_12, PERD_*, PNTMT_*, PNTBT_*, job_id, processed_at },
    ...
  ]
}
```

---

## Contexto obrigatório

- Linguagem: Python
- Celery já configurado
- MongoDB já usado no projeto: ver `backend/tasks/task_load_dec_fec.py` para o padrão `_get_collection(name)`
- Configs Mongo: `backend/settings.py` → `Settings.MONGO_URI` e `Settings.MONGO_DB`
- Callback alvo: `task_finalizar` em `backend/tasks/task_process_layers.py`
- A task `etl.finalizar` recebe `results: list[dict]`, onde um dos itens tem `layer='CTMT'`

---

## Contrato de entrada (CTMT)

O item CTMT em `results` tem esta estrutura:

```json
{
  "layer": "CTMT",
  "job_id": "<id>",
  "records": [
    {
      "COD_ID": "CT-001",
      "NOME": "Circuito Centro",
      "DIST": "404",
      "ENE_01": 100,
      "ENE_02": 120,
      "ENE_03": 130,
      "ENE_04": 140,
      "ENE_05": 150,
      "ENE_06": 160,
      "ENE_07": 170,
      "ENE_08": 180,
      "ENE_09": 190,
      "ENE_10": 200,
      "ENE_11": 210,
      "ENE_12": 220,
      "PERD_A3a": 1.1,
      "PERD_A4": 2.2,
      "PERD_B": 3.3,
      "PERD_MED": 4.4,
      "PERD_A3aA4": 5.5,
      "PERD_A3a_B": 6.6,
      "PERD_A4A3a": 7.7,
      "PERD_A4_B": 8.8,
      "PERD_B_A3a": 9.9,
      "PERD_B_A4": 10.1,
      "PNTMT_01": 11.0,
      "PNTMT_02": 12.0,
      "PNTMT_03": 13.0,
      "PNTMT_04": 14.0,
      "PNTMT_05": 15.0,
      "PNTMT_06": 16.0,
      "PNTMT_07": 17.0,
      "PNTMT_08": 18.0,
      "PNTMT_09": 19.0,
      "PNTMT_10": 20.0,
      "PNTMT_11": 21.0,
      "PNTMT_12": 22.0,
      "PNTBT_01": 23.0,
      "PNTBT_02": 24.0,
      "PNTBT_03": 25.0,
      "PNTBT_04": 26.0,
      "PNTBT_05": 27.0,
      "PNTBT_06": 28.0,
      "PNTBT_07": 29.0,
      "PNTBT_08": 30.0,
      "PNTBT_09": 31.0,
      "PNTBT_10": 32.0,
      "PNTBT_11": 33.0,
      "PNTBT_12": 34.0,
      "job_id": "<id>",
      "processed_at": "2026-04-06T12:00:00+00:00"
    }
  ],
  "total": 1,
  "descartados": 0
}
```

**Campos obrigatórios presentes em cada record:** todos os listados acima. Os campos `PNTMT_01..12` e `PNTBT_01..12` são obrigatórios — são usados pelos notebooks para calcular Perda Não Técnica.

---

## Regras de persistência

### Coleção alvo
`circuitos_mt`

### Nomes de campos no MongoDB
Salvar com os **nomes originais em maiúsculo do GDB** (`COD_ID`, `NOME`, `DIST`, `ENE_01`..`ENE_12`, `PERD_*`, `PNTMT_*`, `PNTBT_*`), mais os metadados `job_id` e `processed_at` em snake_case. NÃO renomear para snake_case.

### Idempotência
Usar `replace_one` com `upsert=True` filtrando por `job_id`. Isso substitui o documento inteiro se já existir, sem necessidade de `delete_many` separado.

### Inserção
```python
col.replace_one(
    {"job_id": job_id},
    {
        "job_id": job_id,
        "processed_at": processed_at,
        "total": len(records),
        "descartados": descartados,
        "records": records,
    },
    upsert=True,
)
```

### Índices (criar com `create_index(..., background=True)`)
1. Índice único em `job_id` — um documento por job, garante unicidade e acelera `find_one`.

```python
col.create_index("job_id", unique=True, background=True)
```

Não é necessário índice composto por `COD_ID` porque a busca dos notebooks é sempre por `job_id`, e o filtro por circuito é feito em pandas após carregar o `records`.

### Padrão de conexão
Reutilizar o padrão já existente em `task_load_dec_fec.py`:

```python
from backend.settings import Settings
from pymongo import MongoClient

def _get_collection(name: str):
    settings = Settings()
    client = MongoClient(settings.MONGO_URI)
    return client[settings.MONGO_DB][name]
```

Se `_get_collection` já estiver definida no arquivo, não duplicar — reutilizar ou importar.

---

## Implementação em `etl.finalizar`

A lógica de persistência CTMT deve ser extraída para uma função auxiliar privada dentro de `task_process_layers.py`:

```python
def _persist_ctmt(records: list[dict], job_id: str, descartados: int, processed_at: str) -> int:
    col = _get_collection('circuitos_mt')
    col.create_index('job_id', unique=True, background=True)
    col.replace_one(
        {'job_id': job_id},
        {
            'job_id': job_id,
            'processed_at': processed_at,
            'total': len(records),
            'descartados': descartados,
            'records': records,
        },
        upsert=True,
    )
    return len(records)
```

Em `task_finalizar`, localizar o resultado CTMT em `results` e chamar `_persist_ctmt`:

```python
ctmt_result = next((r for r in results if r.get('layer') == 'CTMT'), None)
ctmt_total = 0
if ctmt_result:
    ctmt_total = _persist_ctmt(
        records=ctmt_result['records'],
        job_id=job_id,
        descartados=ctmt_result['descartados'],
        processed_at=datetime.now(timezone.utc).isoformat(),
    )
```

### Como o notebook consome

```python
doc = db.circuitos_mt.find_one({"job_id": "abc123"})
ctmt = pd.DataFrame(doc["records"])
# ctmt.columns → [COD_ID, NOME, DIST, ENE_01..ENE_12, PERD_*, PNTMT_*, PNTBT_*, job_id, processed_at]
```

Idêntico ao uso atual com `pd.read_excel('CTMT.xlsx')` — apenas a origem muda.

---

## Atualização da coleção `jobs`

Após persistência bem-sucedida, realizar upsert em `jobs`:

```python
jobs_col = _get_collection('jobs')
jobs_col.update_one(
    {'job_id': job_id},
    {'$set': {
        'job_id': job_id,
        'status': 'completed',
        'ctmt_total': ctmt_total,
        'completed_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'error_message': None,
    }},
    upsert=True,
)
```

---

## Tratamento de falha

Se qualquer exceção ocorrer durante a persistência:
1. Executar cleanup: `col.delete_many({"job_id": job_id})` em `circuitos_mt` (remove documento parcial se `replace_one` falhar no meio).
2. Fazer upsert em `jobs` com `status='failed'` e `error_message=str(exc)`.
3. Re-raise da exceção para que o Celery registre a falha e o errback possa atuar.

```python
except Exception as exc:
    logger.error('[task_finalizar] Falha na persistencia CTMT. job_id=%s erro=%s', job_id, exc)
    _get_collection('circuitos_mt').delete_many({'job_id': job_id})
    _get_collection('jobs').update_one(
        {'job_id': job_id},
        {'$set': {
            'status': 'failed',
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'error_message': str(exc),
        }},
        upsert=True,
    )
    raise
```

---

## Arquivos a alterar

- `backend/tasks/task_process_layers.py` — adicionar `_persist_ctmt` e preencher `task_finalizar`
- `backend/tests/test_task_process_layers.py` — adicionar testes abaixo

---

## Testes mínimos a criar

1. **Persistência básica:** `_persist_ctmt` insere todos os campos (incluindo `PNTMT_*` e `PNTBT_*`) na coleção `circuitos_mt` com os nomes em maiúsculo.
2. **Idempotência:** chamar `_persist_ctmt` duas vezes com o mesmo `job_id` não duplica documentos.
3. **Índices criados:** após call, a coleção possui índice simples em `job_id` e índice único em `(job_id, COD_ID)`.
4. **`task_finalizar` chama `_persist_ctmt`:** mock do resultado com `layer='CTMT'` e verificar que `circuitos_mt` recebe os documentos.
5. **Falha aciona rollback:** se `insert_many` lançar exceção, `circuitos_mt` fica vazia para o `job_id` e `jobs` recebe `status='failed'`.

---

## Restrições

- Não renomear campos para snake_case — os nomes maiúsculos (`COD_ID`, `ENE_01`, `PNTBT_12`, etc.) devem chegar ao Mongo exatamente como a task os produz.
- Não mudar o contrato de retorno de `task_processar_ctmt`.
- Não adicionar dependências novas — `pymongo` já está no projeto.
- Manter logs estruturados com `job_id` em toda a lógica nova.
- `UNSEMT` fora do escopo desta task.

---

## Alerta obrigatório na resposta do Codex

- Confirmar que os 24 campos `PNTMT_01..12` e `PNTBT_01..12` foram persistidos e são consultáveis.
- Confirmar que o índice único `(job_id, COD_ID)` foi criado em `circuitos_mt`.
