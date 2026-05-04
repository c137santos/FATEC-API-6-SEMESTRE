# Instruction Task criação de pdf com gráficos = report (Graficos + PDF no fim da pipeline)

---

## Objetivo

Implementar a geracao automatica dos graficos ao final da pipeline disparada por `POST /pipeline/trigger`, com consolidacao em um PDF final.
Exemplo : ./Frame 11.pdf

O fluxo deve rodar de forma assincrona no Celery, sem bloquear requests HTTP. Utilizando o mesmo job_id. 

---

## Contexto Atual

Prevenção de duplicidade: No disparo da pipeline (POST /pipeline/trigger), o sistema verifica na tabela PostgreSQL de distribuidoras se já existe um job_id correlacionado para a combinação de distribuidora_id e ano. Se existir, a pipeline longa não roda duas vezes, pois os resultados são sempre os mesmos.

- A rota `POST /pipeline/trigger` enfileira o job ETL.
- O processamento de DOWNLOAD de dados importante termina na task `etl.finalizar` em `backend/tasks/task_process_layers.py`. Ingestão de Dados: O fluxo se inicia com a task_download_gdb, que baixa os dados e salva no banco rastreado pelo job_id.
- Dados consolidados por `job_id` ja sao persistidos no MongoDB em colecoes como:
  - `circuitos_mt`
  - `segmentos_mt_tabular`
  - `segmentos_mt_geo`
  - `conjuntos`
  - `unsemt`
  - `jobs`
- A partir disso funcoes de calculos para PT/PNT, TAM e criticidade ocorrem. Eles são importantes para o relatório:
  - `backend/services/calculate_pt_and_pnt.py`
  - `backend/services/calculo_tam.py`
  - `backend/services/criticidade.py`
  - `backend/tasks/task_calculate_sam.py`
  - `backend/tasks/task_criticidade.py`

- Renderização para o report é individual plotam imagens:
  - task_render_pt_pnt
  - task_render_grafico_tam
  - task_render_tabela_score
  - task_render_mapa_calor 

Essas imagens devem ser consolidadas dentro do report PDF que será entregue ao cliente no final da pipeline.

---

## Stack Recomendada

Usar bibliotecas ja alinhadas com os notebooks e com o backend:

1. `matplotlib` + `seaborn` para gerar imagens PNG
2. `reportlab` para montar PDF final

Observacao:
- `reportlab` ja esta em `pyproject.toml`.
- Se necessario, adicionar `matplotlib` e `seaborn` nas dependencias do projeto.

---

## Escopo da Implementacao

### 1) Servico de geracao de graficos

Criar modulo dedicado, por exemplo:

- `backend/services/report.py`

Responsabilidades:

- Carregar dados por `job_id` a partir das funcoes existentes (reutilizar calculos).
- Gerar os graficos em arquivo PNG. Aproveidno as funções (task_render_pt_pnt, task_render_grafico_tam, task_render_tabela_score, task_render_mapa_calor )
- Montar PDF com os graficos e metadados do job.
- Salvar artefatos em path de saida (ex: `/data/reports/{job_id}/`).
- Retornar caminhos dos arquivos gerados.
- Task futura pretende implementar disparo de email com esse relatório
- Após envio do email, apagar o arquivo de relatório

Graficos minimos:

1. Top 10 TAM (barra)
2. PT x PNT por conjunto (barra horizontal empilhada)
3. Score de Criticidade com mapa de calor 

### 2) Task Celery de relatorio

Criar task nova, por exemplo:

- nome Celery: `etl.gerar_report`
- arquivo sugerido: `backend/tasks/task_report.py`

Responsabilidades:

- Receber `job_id`.
- Executar servico de geracao de graficos/PDF.
- Atualizar colecao `jobs` com status do relatorio:
  - `report_status`: `completed` ou `failed`
  - `report_pdf_path`
  - `report_generated_at`
  - `report_error` (quando falhar)

### 3) Encadear no fim da pipeline

No final da dos calculos deve haver o mantimento do comportamento atual de concluir ETL.
- Disparar `etl.gerar_report` apenas quando o ETL finalizar com sucesso.
- Adequar os retornos dos geradores de imagens, os renders, para servir melhor ao gerar_report

### 4) Endpoint para consulta/download

Adicionar rota para obter status e link/caminho do PDF, por exemplo:

- `GET /pipeline/report/{distribuidora_id)`

Resposta sugerida:

```json
{
  "job_id": "...",
  "etl_status": "completed",
  "report_status": "completed",
  "report_pdf_path": "/data/reports/<job_id>/frame11.pdf"
}
```

Opcional:

- endpoint de download direto do arquivo PDF.

---

## Regras Tecnicas

1. Nao executar renderizacao de grafico dentro da thread HTTP.
2. Rodar graficos com backend nao interativo (`Agg`) para ambiente Docker/Celery.
3. Garantir criacao de diretorios com `mkdir(parents=True, exist_ok=True)`.
4. Tratar ausencias de dados sem quebrar o job inteiro:
   - gerar grafico substituto com mensagem de "dados insuficientes" quando aplicavel.
5. Logging estruturado com `job_id` em todas as etapas.
6. Nao alterar contratos existentes de endpoints sem necessidade.

---

## Estrutura Sugerida de Arquivos

Criar/alterar:

- `backend/services/report.py` (novo)
- `backend/tasks/task_report.py` (novo)
- `backend/routes/pipeline.py` (alterar para endpoint de status/download do relatorio)
- `backend/core/schemas.py` (schemas de resposta do relatorio)
- `backend/tests/test_task_report.py` (novo)
- `backend/tests/test_route_pipeline_trigger.py` (ajustes para novo fluxo, se necessario)

---

## Criterios de Aceite

1. Ao concluir `POST /pipeline/trigger` + pipeline ETL, existe tentativa automatica de gerar o report.
2. PDF final e salvo por `job_id` em pasta de artefatos.
3. Endpoint de status do relatorio retorna estado coerente (`pending`, `completed`, `failed`).
4. Falha na geracao do PDF nao deve apagar dados ETL ja persistidos.
5. Logs permitem rastrear claramente: inicio, sucesso, falha e caminhos de arquivo.
6. Testes cobrindo:
   - sucesso na geracao
   - dados insuficientes
   - falha de escrita em disco
   - consulta de status do relatorio

---

## Cenarios de Teste Minimos

1. `job_id` valido com dados completos -> gera 3 PNG + `report.pdf`.
2. `job_id` inexistente -> task marca `report_status=failed` com erro claro.
3. Sem dados de uma das visoes (ex: criticidade) -> PDF ainda e gerado com placeholder.
4. Endpoint `GET /pipeline/report/{job_id}` retorna `404` quando job nao existe.
5. Endpoint retorna `completed` e caminho do PDF quando relatorio pronto.

---

## Restricoes

- Nao mover regra de negocio dos calculos para duplicacao de codigo; reutilizar funcoes existentes.
- Nao acoplar dependencias de frontend na geracao de PDF backend.
- Nao bloquear o callback principal do ETL por operacoes longas de rendering. Usar celery e redis no que couber na estrutura atual

---

## Refatoracoes Necessarias

As alteracoes abaixo sao pre-requisitos para que `etl.gerar_report` consiga montar o PDF. Devem ser executadas junto com a implementacao desta task.

### RF-1 — Persistir caminho de imagem no MongoDB ao fim de cada render task

**Problema:** As render tasks salvam PNGs com convencoes de nome inconsistentes:

| Task | Arquivo gerado |
|---|---|
| `task_render_grafico_tam` | `grafico_tam_{job_id}.png` |
| `task_render_pt_pnt` | `pt_pnt_{sig_agente}_{ano}.png` |
| `task_render_tabela_score` | `tabela_score_{sig}_{ano}.png` |
| `task_render_mapa_calor` | `mapa_calor_{sig}_{ano}.png` |

`etl.gerar_report` nao tem como localizar as imagens dado apenas um `job_id`.

**Solucao:** Ao salvar o PNG, cada render task deve persistir o caminho gerado na colecao `jobs` via `update_one`. Exemplo:

```python
db['jobs'].update_one(
    {'job_id': job_id},
    {'$set': {'render_paths.grafico_tam': str(out_path)}}
)
```

Campos a adicionar em `jobs.render_paths`:

- `render_paths.grafico_tam`
- `render_paths.pt_pnt`
- `render_paths.tabela_score`
- `render_paths.mapa_calor`

`etl.gerar_report` consulta `jobs.render_paths` para montar o PDF, sem depender do nome do arquivo nem dos parametros de cada render task.

Render tasks que retornam `status: skipped` (sem dados suficientes) devem registrar o campo como `null`, para que o report service saiba que deve gerar um placeholder naquele grafico.

### RF-2 — Manutencao do `.si()` no chain: nao alterar assinaturas existentes

**Problema:** O chain em `pipeline_trigger.py` usa `.si()` (immutable signature) em todas as tasks. O retorno de cada task e descartado e nao e passado para a proxima. `etl.gerar_report` nao pode receber os paths via parametro de cadeia Celery.

**Solucao:** Nao alterar o `.si()`. A persistencia no MongoDB definida no RF-1 resolve este ponto como efeito colateral: `etl.gerar_report` consulta `jobs.render_paths` ao iniciar, sem nenhuma dependencia de valores propagados pelo chain. A adicao no chain continua com `.si()`:

```python
task_render_mapa_calor.si(job_id, dist_name, ano),
task_gerar_report.si(job_id),   # novo — recebe apenas job_id
```

Nao e necessario refatorar o chain existente.

---
## Formato Esperado da Resposta

1. Resumo do que foi implementado.
2. Arquivos criados/alterados.
3. Evidencias de validacao (testes executados).
4. Pendencias/riscos conhecidos.
