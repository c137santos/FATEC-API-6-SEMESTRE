## Parent PRD

`issues/prd.md`

## What to build

Scaffolding do endpoint de lookup externo de CNPJ — estrutura completa (rota, schema, handler) sem a lógica de consulta à API externa, que depende de uma fonte confiável ainda a ser escolhida.

O endpoint serve como ponto de integração futuro para resolver distribuidoras com `cnpj_enrichment_status='no_match'` sob demanda.

1. **Rota** — `POST /distribuidoras/{dist_id}/cnpj-lookup` em `backend/routes/dist.py`
2. **Schema de resposta** — `CnpjLookupResponse` com campos: `dist_id`, `dist_name`, `cnpj_enrichment_status`, mensagem informativa
3. **Handler** — retorna `HTTP 501 Not Implemented` com body `{"detail": "External CNPJ lookup not yet configured"}` até a fonte externa ser definida
4. **Proteção** — rejeita distribuidoras com `cnpj_enrichment_status='matched'` (retorna `HTTP 409 Conflict`)

Nenhuma chamada a API externa é implementada neste slice.

## Acceptance criteria

- [ ] Rota `POST /distribuidoras/{dist_id}/cnpj-lookup` existe e está registrada no app
- [ ] Distribuidora com `cnpj_enrichment_status='matched'` retorna `409 Conflict`
- [ ] Distribuidora com `cnpj_enrichment_status='no_match'` retorna `501 Not Implemented` com mensagem clara
- [ ] Distribuidora inexistente retorna `404 Not Found`
- [ ] Nenhuma lógica de consulta a API externa implementada
- [ ] Testes cobrem os três casos acima

## Blocked by

- Blocked by `issues/001-db-migration-normalize-cnpj.md`

## Parallelism note

Pode ser trabalhado **em paralelo** com `issues/002-aneel-client-exact-match-sync.md` e `issues/004-decfec-cnpj-normalization-mongodb-indexes.md` após `issues/001-db-migration-normalize-cnpj.md` estar concluído.

## User stories addressed

- User story 11 — serviço independente para resolver distribuidoras `no_match` sob demanda
