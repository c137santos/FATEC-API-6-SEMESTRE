# Instruction para Codex - Task CTMT

---

## Objetivo

Implementar o processamento real da camada `CTMT` no pipeline ETL, substituindo o placeholder atual da task `etl.processar_ctmt`.

> **Escopo desta task:** leitura, validacao e limpeza dos dados. Persistencia no MongoDB sera tratada em task separada (`etl.salvar_ctmt`).

---

## Contexto do Projeto

- Linguagem: Python
- Framework principal: FastAPI + Celery
- Arquivo principal da task: `backend/tasks/task_process_layers.py`
- Task atual: `task_processar_ctmt(job_id: str, gdb_path: str) -> dict`
- Status atual: placeholder (nao processa registros reais)

---

## Especificacao da Camada CTMT

A camada `CTMT` representa os circuitos de media tensao e deve ser lida do `.gdb` via `fiona`.

Colunas obrigatorias (conforme validacao atual do projeto):

- `COD_ID`
- `NOME`
- `DIST`
- `ENE_01`, `ENE_02`, `ENE_03`, `ENE_04`
- `ENE_05`, `ENE_06`, `ENE_07`, `ENE_08`
- `ENE_09`, `ENE_10`, `ENE_11`, `ENE_12`
- `PERD_A3a`, `PERD_A4`, `PERD_B`, `PERD_MED`
- `PERD_A3aA4`, `PERD_A3a_B`, `PERD_A4A3a`, `PERD_A4_B`
- `PERD_B_A3a`, `PERD_B_A4`

---

## Requisitos de Implementacao

1. Abrir a camada `CTMT` com `fiona` a partir de `gdb_path`.
2. Validar presenca de todas as colunas obrigatorias acima.
3. Aplicar limpeza basica:
   - `COD_ID` e `NOME` com `strip()` quando forem string.
   - Descarta registros sem `COD_ID`.
4. Mapear registro de saida em formato padronizado (snake_case), por exemplo:
   - `cod_id`, `nome`, `dist`
   - `ene_01` ate `ene_12`
   - `perd_a3a`, `perd_a4`, `perd_b`, `perd_med`
   - `perd_a3aa4`, `perd_a3a_b`, `perd_a4a3a`, `perd_a4_b`, `perd_b_a3a`, `perd_b_a4`
5. Incluir `job_id` e `processed_at` (ISO UTC) em cada registro.
6. Manter logs de inicio/fim com `job_id`, `total` e `descartados`.
7. Se apos limpeza nao restar registro valido, lancar `RuntimeError`.

---

## Contrato de Retorno da Task

Retornar estrutura alinhada ao padrao de `task_processar_conj`:

- `layer`: `'CTMT'`
- `job_id`: id da execucao
- `records`: lista de registros processados
- `total`: quantidade valida
- `descartados`: quantidade descartada

---

## Criterios de Aceite

- `etl.processar_ctmt` deixa de retornar placeholder.
- A task retorna registros reais da camada `CTMT`.
- Falta de colunas obrigatorias gera erro explicito de schema.
- Registros sem `COD_ID` sao descartados e contabilizados.
- O retorno final segue o contrato padrao usado no projeto.

---

## Escopo de Arquivos

Alterar preferencialmente:

- `backend/tasks/task_process_layers.py`

Ajustar testes, se necessario:

- `backend/tests/test_task_process_layers.py`

---

## Restricoes

- Nao quebrar tasks existentes (`processar_ssdmt`, `processar_conj`, `finalizar`).
- Nao alterar nomes das tasks Celery.
- Nao adicionar dependencias novas sem necessidade.
- Manter padrao de logs, tipagem e tratamento de erro do projeto.
- **Nao persistir dados** — a task apenas retorna `records`. Persistencia e responsabilidade de task futura.

---

## Formato Esperado da Resposta do Codex

1. Resumo do que foi alterado.
2. Lista de arquivos modificados.
3. Evidencia de validacao (teste executado ou motivo de nao execucao).
4. Riscos ou pendencias, se houver.
