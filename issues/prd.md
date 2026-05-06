# PRD — Enriquecimento de Distribuidoras com CNPJ via API ANEEL

## Problem Statement

O cruzamento de dados entre o PostgreSQL (tabela `distribuidoras`) e o MongoDB (coleções `dec_fec_realizado` e `dec_fec_limite`) é feito hoje através do campo `sig_agente` — uma string com o nome/sigla da distribuidora. Esse campo vem com formatação inconsistente entre as fontes, causando falhas frequentes de match e comprometendo os cálculos de criticidade.

## Solution

Utilizar o CNPJ como chave de cruzamento entre PostgreSQL e MongoDB, substituindo a dependência em `sig_agente`. O CNPJ é um identificador único e estável, já presente nos documentos MongoDB (campo `num_cnpj`). O enriquecimento do PostgreSQL com CNPJ é feito via API de Dados Abertos da ANEEL, que retorna a relação `SigAgente → NumCNPJ`. O match entre os nomes da ANEEL e os nomes no PostgreSQL é feito por exact match primeiro, com fallback para fuzzy matching (threshold 95%). Um fallback explícito para `sig_agente` é mantido para distribuidoras sem CNPJ mapeado.

## User Stories

1. Como operador do sistema, quero que ao executar `/sync` o sistema enriqueça automaticamente as distribuidoras com CNPJ via API da ANEEL, para que o cruzamento de dados seja mais confiável.
2. Como operador do sistema, quero que o enriquecimento seja idempotente, para que executar `/sync` múltiplas vezes não recrie dados nem sobrescreva CNPJs já confirmados.
3. Como operador do sistema, quero visualizar o percentual de match do CNPJ associado a cada distribuidora no PostgreSQL, para que eu possa auditar a qualidade do enriquecimento.
4. Como operador do sistema, quero que distribuidoras com match abaixo de 95% sejam logadas em uma coleção MongoDB separada, para que eu possa tratá-las manualmente no futuro.
5. Como operador do sistema, quero que distribuidoras sem CNPJ ainda funcionem nos cálculos de criticidade via fallback por `sig_agente`, para que a operação não seja interrompida durante o processo de enriquecimento.
6. Como operador do sistema, quero que o CNPJ seja normalizado (14 dígitos sem formatação) em todo ponto de escrita e leitura, para que a comparação entre fontes não falhe por diferença de formato.
7. Como desenvolvedor, quero que a normalização de CNPJ esteja centralizada em uma única função utilitária, para que não haja divergência de implementação entre módulos.
8. Como operador do sistema, quero que a origem do CNPJ (ANEEL, API externa, manual) seja registrada na tabela de distribuidoras, para que eu saiba o nível de confiança de cada associação.
9. Como desenvolvedor, quero que o índice único das coleções MongoDB use `num_cnpj` no lugar de `sig_agente`, para que a integridade dos dados seja garantida pela chave correta.
10. Como desenvolvedor, quero que um índice secundário em `sig_agente` seja mantido no MongoDB, para que queries de fallback não causem full collection scan.
11. Como operador do sistema, quero um serviço independente para consultar o CNPJ de distribuidoras via API externa, para que distribuidoras com `cnpj_enrichment_status = 'no_match'` possam ser resolvidas sob demanda.

## Implementation Decisions

### Migration PostgreSQL — tabela `distribuidoras`
Adicionar as colunas:
- `cnpj` — TEXT, nullable — CNPJ normalizado (14 dígitos)
- `cnpj_match` — FLOAT, nullable — score de similaridade do match
- `cnpj_source` — TEXT, nullable — origem: `'aneel_api'`, `'external_api'`, `'manual'`
- `cnpj_enrichment_status` — TEXT, nullable — `'pending'`, `'matched'`, `'no_match'`, `'manual_review'`

### Utilitário `normalize_cnpj`
- Localização: `backend/core/utils.py`
- Remove pontos, barras e hífens; garante string de 14 dígitos
- Aplicado obrigatoriamente em todo ponto de escrita e leitura de CNPJ

### Cliente da API ANEEL
- Novo módulo em `backend/services/` ou `backend/clients/`
- Consome `https://dadosabertos.aneel.gov.br/api/3/action/datastore_search` com paginação
- Retorna dicionário `{SigAgente: NumCNPJ_normalizado}`
- Cache local da resposta durante a execução do `/sync` para evitar múltiplas chamadas

### Serviço de enriquecimento de CNPJ
- Executado dentro do fluxo do `/sync` como segundo passo, após sincronização das distribuidoras
- Filtra distribuidoras com `cnpj_enrichment_status != 'matched'`
- Estratégia de match:
  1. Exact match entre `SigAgente` da ANEEL e `dist_name` do PostgreSQL
  2. Fuzzy match (biblioteca a definir, ex: `rapidfuzz`) com threshold mínimo de 95%
- Match aceito: grava CNPJ normalizado, score, `cnpj_source='aneel_api'`, status `'matched'`
- Match rejeitado: grava documento em `cnpj_enrichment_log` no MongoDB com candidato, score e CNPJ tentado; status `'no_match'`

### Coleção MongoDB `cnpj_enrichment_log`
Estrutura do documento:
- `dist_id` — ID da distribuidora no PostgreSQL
- `dist_name` — nome no PostgreSQL
- `aneel_sig_agente` — melhor candidato encontrado na ANEEL
- `aneel_cnpj` — CNPJ do candidato (normalizado)
- `match_score` — percentual de similaridade
- `attempted_at` — timestamp

### Atualização do `task_load_dec_fec.py`
- Aplicar `normalize_cnpj()` ao campo `num_cnpj` antes de gravar em ambas as coleções MongoDB

### Índices MongoDB
- Coleção `dec_fec_realizado`:
  - Índice único: `[num_cnpj, ide_conj, sig_indicador, ano_indice, num_periodo]`
  - Índice secundário: `sig_agente`
- Coleção `dec_fec_limite`:
  - Índice único: `[num_cnpj, ide_conj, sig_indicador, ano_limite]`
  - Índice secundário: `sig_agente`

### Serviço de criticidade — novo fluxo de query
- O endpoint `/trigger` já realiza GET no PostgreSQL para obter dados da distribuidora; o CNPJ é injetado nesse ponto
- A Celery task recebe `cnpj` (preferencial) e `sig_agente` (fallback)
- Query primária: filtra MongoDB por `num_cnpj` normalizado
- Fallback explícito: filtra por `sig_agente` quando `cnpj_enrichment_status != 'matched'`

### Serviço externo de lookup de CNPJ
- Serviço independente, acionado por endpoint específico
- Consulta API externa de CNPJ para distribuidoras com status `'no_match'`
- Atualiza `cnpj`, `cnpj_source='external_api'`, status `'matched'`

## Testing Decisions

Um bom teste valida comportamento externo observável, não detalhes de implementação. Testa o contrato do módulo: dado um input, qual o output esperado e quais efeitos colaterais ocorrem no banco.

### Módulos a testar:
- **`normalize_cnpj`**: casos com e sem formatação, CNPJ com 14 dígitos, strings inválidas
- **Serviço de enriquecimento**: mock da API ANEEL, validar lógica de exact match antes do fuzzy, validar escrita correta no PostgreSQL e no log MongoDB para aceitos e rejeitados
- **Criticidade — fluxo com CNPJ**: mock do PostgreSQL retornando distribuidora com CNPJ, validar que a query MongoDB usa `num_cnpj`
- **Criticidade — fallback**: mock do PostgreSQL retornando distribuidora sem CNPJ, validar que a query MongoDB usa `sig_agente`

### Prior art:
- `backend/tests/test_task_load_dec_fec.py` — referência para testes de tasks com mock de MongoDB

## Out of Scope

- Migração de dados históricos no MongoDB (não há dados existentes)
- Interface visual para revisão de matches
- Enriquecimento automático via API externa (é manual e sob demanda)
- Alteração do formato de resposta dos endpoints existentes

## Further Notes

- O threshold de 95% foi escolhido para minimizar falsos positivos dado o risco de CNPJ errado propagar para cálculos regulatórios. Deve ser revisado após análise dos primeiros resultados de produção.
- A API da ANEEL pode ter indisponibilidade; o step de enriquecimento não deve bloquear o `/sync` principal em caso de falha — logar e continuar.
- Distribuidoras com `cnpj_enrichment_status = 'no_match'` são re-tentadas a cada `/sync`. Se isso gerar overhead, avaliar throttling ou status `'skipped'` após N tentativas.
