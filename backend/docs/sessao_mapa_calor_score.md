# Mapa de Calor e Score de Criticidade: do Trigger à Renderização

Este documento descreve como foi implementado o cálculo do score de criticidade
e a geração do mapa de calor, desde o disparo via HTTP até as imagens salvas em
disco. Cobre o fluxo completo: trigger → chain Celery → cálculo → renderização.

---

## Visão geral do fluxo

```
POST /pipeline/trigger
        │
        ▼
trigger_pipeline_flow          (service: valida, resolve URL, cria job_id)
        │
        ▼
chain(                          (Celery: execução sequencial garantida)
  etl.download_gdb              ← baixa e extrai o GDB da ANEEL
  etl.score_criticidade         ← calcula score por conjunto (DEC/FEC)
  etl.mapa_criticidade          ← monta documento de mapa por conjunto
  etl.render_tabela_score       ← gera imagem da tabela score (dark design)
  etl.render_mapa_calor         ← gera imagem do mapa de calor geográfico
).delay()
```

O mesmo `job_id` percorre toda a cadeia. As tasks pós-download aguardam
`job.status == 'completed'` no MongoDB antes de executar, via retry com
countdown de 30 segundos (máximo 60 tentativas ≈ 30 minutos).

---

## 1. Trigger: `POST /pipeline/trigger`

**Rota:** `backend/routes/pipeline.py`
**Service:** `backend/services/pipeline_trigger.py` → `trigger_pipeline_flow`

O orquestrador realiza três verificações antes de disparar qualquer task:

1. **Idempotência** — verifica se `job_id` já existe na tabela `distribuidoras`
   (campo `job_id` não-nulo). Se sim, retorna 409.
2. **Resolução do nome** — busca `dist_name` no PostgreSQL pela chave
   `(distribuidora_id, ano)`. Esse nome é usado para consultar o MongoDB.
3. **Validação na ANEEL** — consulta a API ArcGIS Hub para confirmar que o item
   existe e é do tipo `File Geodatabase` ou `Feature Service`.

```python
# backend/services/pipeline_trigger.py

job_id = str(uuid.uuid4())          # nasce aqui, segue em todas as tasks

result = chain(
    task_download_gdb.si(job_id, download_url, distribuidora_id),
    task_score_criticidade.si(job_id, dist_name, ano),
    task_mapa_criticidade.si(job_id, distribuidora_id, dist_name, ano),
    task_render_tabela_score.si(job_id, dist_name, ano),
    task_render_mapa_calor.si(job_id, dist_name, ano),
).delay()
```

O uso de `.si()` (immutable signature) garante que o resultado de cada task
**não é injetado como argumento** na próxima — cada uma recebe exatamente os
argumentos definidos acima.

Após o `.delay()`, o rastreamento é salvo no PostgreSQL:

```python
await save_distribuidora_job_tracking(session, distribuidora_id, ano, job_id)
```

A resposta HTTP retorna imediatamente com `status: "queued"` — o processamento
acontece de forma assíncrona no worker Celery.

---

## 2. Download e ETL: `etl.download_gdb`

**Arquivo:** `backend/tasks/task_download_gdb.py`

O GDB (Geodatabase) é baixado do S3 da ANEEL via redirect do ArcGIS. Após o
download e validação do ZIP, a task encadeia internamente a pipeline ETL:

```python
signature('etl.extrair_gdb', args=(job_id, str(zip_path), distribuidora_id)).delay()
```

A ETL interna segue sua própria cadeia com `chord`:

```
etl.extrair_gdb
  → chord(
      [etl.processar_ctmt, etl.processar_conj,
       etl.processar_unsemt, etl.processar_ssdmt],
      etl.finalizar
    )
```

`etl.finalizar` persiste todos os dados no MongoDB e marca o job com
`status: "completed"` na coleção `jobs`. Esse é o sinal que as tasks seguintes
esperam para começar a executar.

---

## 3. Score de Criticidade: `etl.score_criticidade`

**Arquivo:** `backend/tasks/task_criticidade.py` → `task_score_criticidade`

### Aguarda a ETL

```python
job = db['jobs'].find_one({'job_id': job_id})
if not job or job.get('status') != 'completed':
    raise self.retry(countdown=30)   # reagenda em 30s
```

### Cálculo por conjunto

Para cada conjunto (`ide_conj`) da distribuidora no ano, busca:
- **Realizados** em `dec_fec_realizado` — soma de `vlr_indice` agrupada por conjunto e indicador
- **Limites** em `dec_fec_limite`

O desvio percentual é calculado apenas quando o realizado supera o limite:

```python
desvio = max(0.0, ((realizado - limite) / limite) * 100)
```

O **score do conjunto** é a soma dos desvios de DEC e FEC:

```
score_conjunto = desvio_dec + desvio_fec
```

### Classificação por categoria

| Score          | Categoria | Cor      |
|----------------|-----------|----------|
| `== 0`         | Verde     | #22c55e  |
| `0 < x ≤ 10`  | Laranja   | #f59e0b  |
| `> 10`         | Vermelho  | #ef4444  |

### Documento salvo em `score_criticidade`

O score médio da distribuidora (média dos scores de todos os conjuntos) é salvo
com upsert:

```json
{
  "ano": 2024,
  "distribuidora": "ENEL RJ",
  "score_criticidade": 21.69,
  "desvio_dec": 18.42,
  "desvio_fec": 3.27,
  "cor": "Vermelho",
  "quantidade_conjuntos": 78
}
```

---

## 4. Mapa de Criticidade: `etl.mapa_criticidade`

**Arquivo:** `backend/tasks/task_criticidade.py` → `task_mapa_criticidade`

Também aguarda `job.status == 'completed'`, depois executa o mesmo cálculo de
desvio e score — mas **por conjunto individualmente**, preservando a categoria
de cada um.

Os conjuntos são salvos em `mapa_criticidade` ordenados por `score_criticidade`
decrescente (mais críticos primeiro) e vinculados ao `job_id`, que relaciona
os dados GDB ao documento:

```json
{
  "distribuidora_id": "6d53789f98c74cbb84c070ecb4633b0f",
  "distribuidora": "ENEL RJ",
  "ano": 2024,
  "job_id": "40a68842-...",
  "total_conjuntos": 78,
  "conjuntos": [
    {
      "ide_conj": "13057",
      "desvio_dec": 179.55,
      "desvio_fec": 13.87,
      "score_criticidade": 193.43,
      "categoria": "Vermelho"
    }
  ]
}
```

O `job_id` armazenado aqui é o mesmo usado por `etl.render_mapa_calor` para
recuperar as geometrias da coleção `segmentos_mt_geo`.

---

## 5. Renderização da Tabela: `etl.render_tabela_score`

**Arquivo:** `backend/tasks/task_render_criticidade.py` → `task_render_tabela_score`

Aguarda que `score_criticidade` e `mapa_criticidade` existam no MongoDB (retry
se ausentes). Com os dados disponíveis, gera a imagem com matplotlib via
`_draw_tabela`:

- Fundo escuro (`#0f0f1a`) com linhas alternadas
- Header com nome da distribuidora, ano, score médio e total de conjuntos
- Colunas: RANK, CONJUNTO, DESVIO DEC %, DESVIO FEC %, SCORE CRITICIDADE
- Badges arredondados (`FancyBboxPatch`) coloridos na coluna de score
- Desvios coloridos individualmente por severidade

Imagem salva em:

```
output/images/tabela_score_{DISTRIBUIDORA}_{ANO}.png
```

---

## 6. Renderização do Mapa de Calor: `etl.render_mapa_calor`

**Arquivo:** `backend/tasks/task_render_criticidade.py` → `task_render_mapa_calor`

Fecha o ciclo unindo as geometrias geográficas do GDB com as categorias
calculadas.

### Passo a passo

1. Lê `mapa_criticidade` para obter o `job_id` do GDB e a categoria de cada conjunto
2. Monta `categoria_por_conj: dict[int, str]` — chave é o `ide_conj` inteiro
3. Busca os segmentos elétricos em `segmentos_mt_geo` filtrando pelo `job_id`:

```python
db['segmentos_mt_geo'].find(
    {'job_id': gdb_job_id, 'CONJ': {'$in': list(categoria_por_conj.keys())}},
    {'_id': 0, 'CONJ': 1, 'geometry': 1},
)
```

4. Converte cada geometria de GeoJSON para objeto Shapely:

```python
features.append({
    'geometry': shape(geom_dict),
    'categoria': categoria_por_conj.get(int(conj_id), 'Verde'),
})
```

5. Monta um `GeoDataFrame` com coluna `cor` mapeada da categoria:

```python
gdf = gpd.GeoDataFrame(features, geometry='geometry', crs='EPSG:4326')
gdf['cor'] = gdf['categoria'].map(_CATEGORIA_COR)
```

6. Plota com geopandas e salva com matplotlib:

```python
gdf.plot(color=gdf['cor'], linewidth=0.8, ax=ax, edgecolor='0.8')
plt.savefig(out_path, dpi=150, bbox_inches='tight')
```

Imagem salva em:

```
output/images/mapa_calor_{DISTRIBUIDORA}_{ANO}.png
```

---

## Mecanismo de espera via retry

As tasks pós-download não usam `chord` nem callbacks para aguardar a ETL — elas
se auto-regulam consultando o MongoDB:

```python
WAIT_COUNTDOWN = 30    # segundos entre tentativas
MAX_WAIT_RETRIES = 60  # máximo ~30 minutos de espera

job = db['jobs'].find_one({'job_id': job_id})
if not job or job.get('status') != 'completed':
    raise self.retry(countdown=WAIT_COUNTDOWN)
```

Quando `self.retry()` é chamado dentro de uma `chain`, a task é reescalonada e
a cadeia **permanece pausada** naquela etapa até que ela complete com sucesso.
As etapas seguintes só executam depois.

---

## Coleções MongoDB envolvidas

| Coleção             | Escrita por                      | Lida por                                        |
|---------------------|----------------------------------|-------------------------------------------------|
| `jobs`              | `etl.finalizar`                  | `etl.score_criticidade`, `etl.mapa_criticidade` |
| `dec_fec_realizado` | `etl.load_dec_fec_realizado`     | `etl.score_criticidade`, `etl.mapa_criticidade` |
| `dec_fec_limite`    | `etl.load_dec_fec_limite`        | `etl.score_criticidade`, `etl.mapa_criticidade` |
| `score_criticidade` | `etl.score_criticidade`          | `etl.render_tabela_score`, `etl.render_mapa_calor` |
| `mapa_criticidade`  | `etl.mapa_criticidade`           | `etl.render_tabela_score`, `etl.render_mapa_calor` |
| `segmentos_mt_geo`  | `etl.finalizar`                  | `etl.render_mapa_calor`                         |

---

## Arquivos envolvidos

| Arquivo | Responsabilidade |
|---------|-----------------|
| `backend/routes/pipeline.py` | Recebe o HTTP POST, traduz exceções em status codes |
| `backend/services/pipeline_trigger.py` | Valida, cria `job_id`, monta e dispara o chain |
| `backend/tasks/task_download_gdb.py` | Download do GDB + kickoff da ETL interna |
| `backend/tasks/task_criticidade.py` | Cálculo do score e mapa por conjunto |
| `backend/tasks/task_render_criticidade.py` | Renderização das imagens (tabela e mapa de calor) |
| `backend/tasks/celery_app.py` | Registra todos os módulos de tasks no worker |
