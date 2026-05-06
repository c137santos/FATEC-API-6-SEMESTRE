## Parent PRD

`issues/prd.md`

## What to build

Atualizar o fluxo de cálculo de criticidade para usar `num_cnpj` como chave primária de query no MongoDB, mantendo `sig_agente` como fallback explícito.

Caminho end-to-end completo: endpoint `/trigger` → `pipeline_trigger.py` → `task_criticidade.py` → query MongoDB.

1. **`pipeline_trigger.py`** — ao montar a Celery chain, injetar `cnpj` (lido do PostgreSQL junto com `dist_name`) como parâmetro das tasks de criticidade.
2. **`task_score_criticidade` e `task_mapa_criticidade`** — recebem `cnpj` (opcional) e `sig_agente`; query primária filtra MongoDB por `num_cnpj` quando `cnpj` está presente e `cnpj_enrichment_status='matched'`; fallback filtra por `sig_agente` nos demais casos.
3. Nenhuma alteração no formato de resposta dos endpoints existentes.

## Acceptance criteria

- [ ] `pipeline_trigger.py` lê `cnpj` da distribuidora no PostgreSQL e o passa para as tasks de criticidade
- [ ] Quando `cnpj` está disponível (`cnpj_enrichment_status='matched'`), a query MongoDB usa `{'num_cnpj': cnpj_normalizado}`
- [ ] Quando `cnpj` não está disponível, a query MongoDB usa `{'sig_agente': sig_agente}` (comportamento idêntico ao atual)
- [ ] `normalize_cnpj()` é aplicado ao `cnpj` antes da query (defesa contra CNPJ mal formatado no PostgreSQL)
- [ ] Formato de resposta dos endpoints `/trigger` e de criticidade inalterado
- [ ] Testes cobrem: fluxo com CNPJ (mock PostgreSQL retorna distribuidora com `cnpj_enrichment_status='matched'`), fluxo de fallback (mock retorna distribuidora sem CNPJ), validação de qual campo é usado em cada caso

## Blocked by

- Blocked by `issues/003-fuzzy-match-enrichment-log.md`
- Blocked by `issues/004-decfec-cnpj-normalization-mongodb-indexes.md`

## User stories addressed

- User story 5 — distribuidoras sem CNPJ continuam funcionando nos cálculos via fallback por `sig_agente`
