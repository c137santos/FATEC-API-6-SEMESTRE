# ETL CTMT - Como Funciona a Extracao

## Visao geral

A task `etl.processar_ctmt` foi implementada para extrair e tratar dados reais da camada `CTMT` de um arquivo `.gdb`.

Arquivo principal:
- `backend/tasks/task_process_layers.py`

Objetivo desta etapa:
- Ler dados da camada `CTMT`
- Validar schema minimo
- Limpar registros
- Retornar dados padronizados para consumo posterior

Importante:
- Esta task **nao persiste** dados em banco.
- A persistencia fica para uma task futura (exemplo: `etl.salvar_ctmt`).

---

## Fluxo da extracao

1. Recebe `job_id` e `gdb_path`.
2. Abre a camada `CTMT` com `fiona`.
3. Valida se todas as colunas obrigatorias existem no schema.
4. Itera pelos registros da camada.
5. Aplica limpeza:
   - `COD_ID` com `strip()` quando for `str`
   - `NOME` com `strip()` quando for `str`
   - descarta registro sem `COD_ID` valido
6. Mapeia os campos para formato `snake_case`.
7. Adiciona metadados em cada registro:
   - `job_id`
   - `processed_at` (ISO UTC)
8. Se nao sobrar registro valido, lanca `RuntimeError`.
9. Retorna payload padrao com `records`, `total` e `descartados`.

---

## Colunas obrigatorias (CTMT)

- `COD_ID`
- `NOME`
- `DIST`
- `ENE_01` ate `ENE_12`
- `PERD_A3a`, `PERD_A4`, `PERD_B`, `PERD_MED`
- `PERD_A3aA4`, `PERD_A3a_B`, `PERD_A4A3a`, `PERD_A4_B`
- `PERD_B_A3a`, `PERD_B_A4`

Se faltar qualquer coluna obrigatoria, a task falha com erro explicito de schema.

---

## Contrato de retorno

A resposta segue o mesmo padrao usado por `task_processar_conj`:

```json
{
  "layer": "CTMT",
  "job_id": "<id>",
  "records": [
    {
      "cod_id": "CT-001",
      "nome": "Circuito Centro",
      "dist": "404",
      "ene_01": 100,
      "ene_02": 120,
      "...": "...",
      "ene_12": 130,
      "perd_a3a": 1.1,
      "perd_a4": 2.2,
      "perd_b": 3.3,
      "perd_med": 4.4,
      "perd_a3aa4": 5.5,
      "perd_a3a_b": 6.6,
      "perd_a4a3a": 7.7,
      "perd_a4_b": 8.8,
      "perd_b_a3a": 9.9,
      "perd_b_a4": 10.1,
      "job_id": "<id>",
      "processed_at": "2026-04-03T12:00:00+00:00"
    }
  ],
  "total": 1,
  "descartados": 0
}
```

---

## Logs e observabilidade

A task registra:
- Inicio do processamento (`job_id`, `gdb_path`)
- Fim do processamento (`job_id`, `total`, `descartados`)

Isso ajuda a rastrear execucao por lote (`job_id`) e qualidade de dados (volume descartado).

---

## Testes implementados

Arquivo de testes:
- `backend/tests/test_task_process_layers.py`

Cenarios cobertos para CTMT:
- retorno valido com mapeamento correto
- descarte de registros sem `COD_ID`
- erro quando faltam colunas obrigatorias
- erro quando nenhum registro valido sobra apos limpeza

---

## Decisoes Arquiteturais do Pipeline

### Decisao 2026-04 - Saida da task SSDMT

Contexto:
- A camada `SSDMT` pode ter ~999k registros com geometria.
- Retornar todas as geometrias no payload do chord aumenta muito o tempo de serializacao e o uso de memoria no worker/broker.

Decisao registrada para avaliacao:
- Evoluir de retorno completo para um desenho em dois produtos:
  - `ssdmt_tabular`: colunas para analytics e joins (`COD_ID`, `CTMT`, `CONJ`, `COMP`, `DIST`)
  - `ssdmt_geo`: geometria reprojetada persistida fora do payload (DB/arquivo/objeto), acessada por referencia

Compatibilidade esperada:
- Notebooks tabulares (PT/PNT e parte relevante de TAM) continuam atendidos sem depender do retorno completo de geometria.
- Notebooks de mapa continuam atendidos ao ler geometria da base persistida.

Criterios de avaliacao:
1. Tempo total da `etl.processar_ssdmt`.
2. Pico de memoria do worker.
3. Tamanho do payload no broker/backend.
4. Tempo de callback (`etl.finalizar`) e estabilidade do chord.
5. Equivalencia funcional dos notebooks (tabular e mapa).

Documento detalhado:
- `codex/task_ssdmt.md`


