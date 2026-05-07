## Parent PRD

`issues/prd.md`

## What to build

Primeira camada de enriquecimento: buscar CNPJs na API da ANEEL e associá-los às distribuidoras via **exact match**, integrando o resultado como segundo passo do `/sync`.

Três peças end-to-end:

1. **ANEEL API client** (`backend/clients/aneel.py`) — consome `https://dadosabertos.aneel.gov.br/api/3/action/datastore_search` com paginação; retorna `dict[str, str]` (`{SigAgente: cnpj_normalizado}`); cache local durante a execução para evitar múltiplas chamadas; loga e relança em caso de falha HTTP.
2. **Enrichment service** (`backend/services/cnpj_enrichment.py`) — recebe lista de distribuidoras com `cnpj_enrichment_status != 'matched'`; tenta exact match entre `SigAgente` da ANEEL e `dist_name` do PostgreSQL; em match: grava `cnpj` (normalizado), `cnpj_match=1.0`, `cnpj_source='aneel_api'`, `cnpj_enrichment_status='matched'`; sem match: grava `cnpj_enrichment_status='no_match'` (sem tocar CNPJ).
3. **Integração no `/sync`** (`backend/services/distribuidoras.py`) — após upsert das distribuidoras, chama o enrichment service; idempotente: distribuidoras com status `'matched'` são ignoradas.

> **Ponto de feedback humano antes de avançar para `issues/003-fuzzy-match-enrichment-log.md`:** validar se a API ANEEL retorna os `SigAgente` esperados e se os exact matches fazem sentido para as distribuidoras do ambiente.

## Acceptance criteria

- [ ] `backend/clients/aneel.py` busca todos os registros com paginação e retorna dicionário `{SigAgente: cnpj_normalizado}`
- [ ] Cache da resposta ANEEL dura apenas a execução do `/sync` (não persiste entre chamadas)
- [ ] Falha na API ANEEL loga o erro e não bloqueia o `/sync` (retorna sem enriquecer)
- [ ] Exact match é case-insensitive entre `SigAgente` e `dist_name`
- [ ] Distribuidoras com match têm `cnpj_enrichment_status='matched'` e CNPJ normalizado gravado
- [ ] Distribuidoras sem match têm `cnpj_enrichment_status='no_match'`; CNPJ não é alterado; status não é re-tentado em syncs futuros
- [ ] Rodar `/sync` duas vezes não recria nem sobrescreve distribuidoras com status `'matched'` ou `'no_match'`
- [ ] `cnpj_source='aneel_api'` e `cnpj_match=1.0` para todos os exact matches
- [ ] Testes mockam a API ANEEL e validam: match aceito, match rejeitado, idempotência, falha HTTP

## Blocked by

- Blocked by `issues/001-db-migration-normalize-cnpj.md`

## Parallelism note

Após `issues/001-db-migration-normalize-cnpj.md` estar concluído, este slice pode ser trabalhado **em paralelo** com `issues/004-decfec-cnpj-normalization-mongodb-indexes.md` e `issues/006-external-cnpj-lookup-stub.md`.

## User stories addressed

- User story 1 — `/sync` enriquece distribuidoras com CNPJ via API da ANEEL
- User story 2 — enriquecimento idempotente
- User story 8 — origem do CNPJ registrada (`cnpj_source`)
