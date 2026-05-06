## Parent PRD

`issues/prd.md`

## What to build

Alicerce para todo o enriquecimento de CNPJ. Duas entregas independentes mas agrupadas por serem pré-requisito de tudo:

1. **Migração PostgreSQL** — adicionar as colunas `cnpj`, `cnpj_match`, `cnpj_source` e `cnpj_enrichment_status` à tabela `distribuidoras` via Alembic.
2. **Utilitário `normalize_cnpj`** — função centralizada em `backend/core/utils.py` que remove pontos, barras e hífens e garante string de 14 dígitos. Aplicada em todo ponto de escrita e leitura de CNPJ no sistema.

Nenhuma lógica de enriquecimento é implementada aqui — apenas a estrutura de dados e o utilitário que os demais slices consomem.

## Acceptance criteria

- [ ] Migration Alembic criada e aplicável com `alembic upgrade head` sem erro
- [ ] Tabela `distribuidoras` possui as colunas: `cnpj TEXT NULL`, `cnpj_match FLOAT NULL`, `cnpj_source TEXT NULL`, `cnpj_enrichment_status TEXT NULL`
- [ ] `backend/core/utils.py` existe e exporta `normalize_cnpj(value: str) -> str`
- [ ] `normalize_cnpj` remove pontos, barras e hífens e retorna string de exatamente 14 dígitos
- [ ] `normalize_cnpj` aceita CNPJ já normalizado sem alterar o resultado
- [ ] Testes cobrem: CNPJ com formatação completa, só dígitos, string inválida (len ≠ 14 após limpeza)
- [ ] Model SQLAlchemy `Distribuidora` em `backend/core/models.py` atualizado com os novos campos (todos nullable, default None)

## Blocked by

None — can start immediately.

## User stories addressed

- User story 6 — normalização de CNPJ centralizada em todo ponto de escrita e leitura
- User story 7 — função utilitária única para normalização, sem divergência entre módulos
