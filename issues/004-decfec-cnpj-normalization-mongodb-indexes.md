## Parent PRD

`issues/prd.md`

## What to build

Tornar `num_cnpj` a chave primária das coleções MongoDB, substituindo `sig_agente` nos índices únicos e normalizando o campo na escrita.

Duas mudanças em `backend/tasks/task_load_dec_fec.py`:

1. **Normalização** — aplicar `normalize_cnpj()` ao campo `num_cnpj` de cada documento antes do upsert em ambas as coleções (`dec_fec_realizado` e `dec_fec_limite`).
2. **Migração de índices** — alterar as constantes de índice único:
   - `dec_fec_realizado`: `[num_cnpj, ide_conj, sig_indicador, ano_indice, num_periodo]`
   - `dec_fec_limite`: `[num_cnpj, ide_conj, sig_indicador, ano_limite]`
   - Adicionar índice secundário em `sig_agente` em ambas as coleções (para queries de fallback não causarem full collection scan).

Nenhuma alteração nos endpoints ou no serviço de criticidade — esse slice prepara apenas a camada de dados.

## Acceptance criteria

- [ ] `normalize_cnpj()` é aplicado ao `num_cnpj` antes de todo upsert em `dec_fec_realizado` e `dec_fec_limite`
- [ ] Índice único de `dec_fec_realizado` usa `[num_cnpj, ide_conj, sig_indicador, ano_indice, num_periodo]`
- [ ] Índice único de `dec_fec_limite` usa `[num_cnpj, ide_conj, sig_indicador, ano_limite]`
- [ ] Índice secundário em `sig_agente` criado em ambas as coleções
- [ ] Documentos duplicados detectados pelo novo índice único são tratados como upsert (sem erro fatal)
- [ ] Testes existentes em `backend/tests/test_task_load_dec_fec.py` continuam passando
- [ ] Novos testes cobrem: `num_cnpj` normalizado no documento gravado, conflito de índice único tratado corretamente

## Blocked by

- Blocked by `issues/001-db-migration-normalize-cnpj.md`

## Parallelism note

Pode ser trabalhado **em paralelo** com `issues/002-aneel-client-exact-match-sync.md` e `issues/006-external-cnpj-lookup-stub.md` após `issues/001-db-migration-normalize-cnpj.md` estar concluído.

## User stories addressed

- User story 6 — CNPJ normalizado em todo ponto de escrita e leitura
- User story 9 — índice único das coleções MongoDB usa `num_cnpj`
- User story 10 — índice secundário em `sig_agente` para queries de fallback
