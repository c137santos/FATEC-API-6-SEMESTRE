## Parent PRD

`issues/prd.md`

## What to build

Refinamento do serviço de enriquecimento: adicionar fallback por fuzzy match e auditoria dos casos não resolvidos.

Constrói sobre o exact match de `issues/002-aneel-client-exact-match-sync.md` — só altera o enrichment service e adiciona a coleção de log:

1. **Fuzzy match** — para distribuidoras que não tiveram exact match, aplicar `rapidfuzz` (ou equivalente) contra todos os `SigAgente` da ANEEL; threshold mínimo: 95%; se aceito: grava CNPJ + `cnpj_match=<score>` + `cnpj_source='aneel_api'` + `cnpj_enrichment_status='matched'`.
2. **`cnpj_enrichment_log`** (MongoDB) — para distribuidoras com score < 95%: grava documento com `dist_id`, `dist_name`, `aneel_sig_agente` (melhor candidato), `aneel_cnpj`, `match_score`, `attempted_at`; atualiza status para `'no_match'`.
3. **Percentual de match** — `SyncDistribuidorasResponse` (ou endpoint de auditoria dedicado) expõe contagem de `matched` / `no_match` / `pending` para que o operador possa auditar a qualidade do enriquecimento.

## Acceptance criteria

- [ ] Fuzzy match só é tentado para distribuidoras que falharam no exact match
- [ ] Match com score ≥ 95% é aceito; `cnpj_match` recebe o score real (ex: 0.97)
- [ ] Match com score < 95% grava documento em `cnpj_enrichment_log` e não altera o CNPJ da distribuidora
- [ ] Documento em `cnpj_enrichment_log` contém todos os campos do PRD: `dist_id`, `dist_name`, `aneel_sig_agente`, `aneel_cnpj`, `match_score`, `attempted_at`
- [ ] Distribuidoras com `cnpj_enrichment_status='no_match'` **não** são re-tentadas automaticamente — o status permanece `'no_match'` até resolução manual via `issues/006-external-cnpj-lookup-stub.md`
- [ ] Resposta do `/sync` inclui contagem de `matched`, `no_match` e `pending`
- [ ] Testes cobrem: fuzzy aceito (≥95%), fuzzy rejeitado (<95%), verificação do documento gravado no log, re-tentativa de `no_match` em novo sync

## Blocked by

- Blocked by `issues/002-aneel-client-exact-match-sync.md`

## User stories addressed

- User story 3 — percentual de match visível por distribuidora
- User story 4 — distribuidoras com match < 95% logadas em coleção separada
- User story 8 — origem e confiança do CNPJ registradas
