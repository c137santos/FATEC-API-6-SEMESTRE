# Backlog da Sprint 1

| Rank | Prioridade | User Story | Requisitos Relacionados | Estimativa (Story Points) | Sprint |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 |  Alta | Como um consultor comercial/técnico da Tecsys, eu quero visualizar uma tabela de classificação calculando o Índice de Criticidade (desvio percentual de DEC e FEC com base nos limites da ANEEL) de cada conjunto elétrico, para que eu possa identificar e priorizar rapidamente quais regiões possuem a pior eficiência estrutural. | [`RF1-DATA-INGEST`](../requisitos.md#rf1-data-ingest---ingestão-de-dados-regulatórios), [`RF2-ANALYTICS-CRIT`](../requisitos.md#rf2-analytics-crit---cálculo-de-criticidade-e-perdas) | 18 | 1 |
| 2 |  Alta | Como um membro do time comercial/técnico, eu quero visualizar um gráfico de barras ordenado pelos conjuntos elétricos com maior índice SAM, para que eu saiba rapidamente quais regiões têm prioridade máxima de implantação de sensores. | [`RF2-ANALYTICS-CRIT`](../requisitos.md#rf2-analytics-crit---cálculo-de-criticidade-e-perdas) | 10 | 1 |
| 3 |  Alta | Como um membro do time comercial/técnico, eu quero visualizar um gráfico de barras empilhadas que compare o volume absoluto (em MWh) das Perdas Técnicas (PT) e Não Técnicas (PNT) de cada conjunto elétrico, para evidenciar a magnitude das falhas estruturais da rede.| [`RF2-ANALYTICS-CRIT`](../requisitos.md#rf2-analytics-crit---cálculo-de-criticidade-e-perdas) | 10 | 1 |
| 4 |  Alta | Como um consultor comercial/técnico da Tecsys, eu quero visualizar um ranking com os 10 conjuntos elétricos com maior extensão de média tensão (TAM), para demonstrar os pontos de maior vulnerabilidade operacional.| [`RF1-DATA-INGEST`](../requisitos.md#rf1-data-ingest---ingestão-de-dados-regulatórios), [`RF2-ANALYTICS-TAM`](../requisitos.md#rf2-analytics-tam---dimensionamento-físico-tam) | 12 | 1 |
| 5 |  Média | Como um consultor comercial/técnico da Tecsys, eu quero visualizar um mapa de calor georreferenciado indicando os circuitos mais críticos com base no Índice de Criticidade, para justificar investimentos em sensores inteligentes. | [`RF4-MAPS-HEATMAP`](../requisitos.md#rf4-maps-heatmap---mapas-de-calor-e-polígonos) | 8 | 2 |

## Metas da sprint

| **Capacidade estimada da Equipe por Sprint:** | 58 Story Points |
|-----------------------------------------------|-----------------|
| **Meta da Sprint:**                           | User Stories de rank 1, rank 2, rank 3, rank 4 (total de *50 Story Points*) |
| **Previsão da Sprint (extras, sem compromisso de entrega):** | User Story de rank 5 (*8 Story Points*) |
