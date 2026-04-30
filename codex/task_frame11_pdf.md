# Instruction para Codex - Task Frame 11 (Graficos + PDF no fim da pipeline)

---

## Objetivo

Implementar a geracao automatica dos graficos do Frame 11 ao final da pipeline disparada por `POST /pipeline/trigger`, com consolidacao em um PDF final.

O fluxo deve rodar de forma assincrona no Celery, sem bloquear requests HTTP. Utilizando o mesmo job_id. 

---

## Contexto Atual

- A rota `POST /pipeline/trigger` apenas enfileira o job ETL.
- O processamento principal termina na task `etl.finalizar` em `backend/tasks/task_process_layers.py`.
- Dados consolidados por `job_id` ja sao persistidos no MongoDB em colecoes como:
  - `circuitos_mt`
  - `segmentos_mt_tabular`
  - `segmentos_mt_geo`
  - `conjuntos`
  - `unsemt`
  - `jobs`
- Ja existem funcoes de calculo para PT/PNT, TAM e criticidade:
  - `backend/core/calculate_pt_and_pnt.py`
  - `backend/core/calculo_tam.py`
  - `backend/services/criticidade.py`

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
- Gerar os graficos em arquivo PNG.
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

No final da `etl.finalizar` (`backend/tasks/task_process_layers.py`):

- Manter o comportamento atual de concluir ETL.
- Disparar `etl.gerar_frame11` apenas quando o ETL finalizar com sucesso.
- Nao quebrar contrato de retorno atual da task `etl.finalizar`.

### 4) Endpoint para consulta/download

Adicionar rota para obter status e link/caminho do PDF, por exemplo:

- `GET /pipeline/report/{job_id}`

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

- `backend/services/frame11_report.py` (novo)
- `backend/tasks/task_frame11_report.py` (novo)
- `backend/tasks/task_process_layers.py` (alterar para encadear task)
- `backend/routes/pipeline.py` (alterar para endpoint de status/download do relatorio)
- `backend/core/schemas.py` (schemas de resposta do relatorio)
- `backend/tests/test_task_report.py` (novo)
- `backend/tests/test_route_pipeline_trigger.py` (ajustes para novo fluxo, se necessario)

---

## Criterios de Aceite

1. Ao concluir `POST /pipeline/trigger` + pipeline ETL, existe tentativa automatica de gerar o Frame 11.
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
- Nao bloquear o callback principal do ETL por operacoes longas de rendering.

---

## Observacoes

- O endpoint de criticidade atual usa funcao assincrona e precisa de ajuste de `await` para evitar inconsistencias quando reutilizado no relatorio.
- Caso o Frame 11 exija layout fixo, usar template de coordenadas no ReportLab para manter padrao visual estavel.

---

## Formato Esperado da Resposta do Codex

1. Resumo do que foi implementado.
2. Arquivos criados/alterados.
3. Evidencias de validacao (testes executados).
4. Pendencias/riscos conhecidos.
