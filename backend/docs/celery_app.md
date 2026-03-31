# Celery App: Fluxo Atual do ETL

Este documento descreve o fluxo orquestrado pelo `backend/tasks/celery_app.py`.

## Tasks registradas

O worker registra as tasks via `include`:

- `backend.tasks.task_download_gdb`
- `backend.tasks.task_descompact_gdb`
- `backend.tasks.task_process_layers`

Com isso, os nomes de task disponiveis sao:

- `etl.download_gdb`
- `etl.extrair_gdb`
- `etl.processar_ctmt`
- `etl.processar_ssdmt`
- `etl.processar_conj`
- `etl.finalizar`

## Fluxo

1. A API chama `task_download_gdb.delay(job_id, url)`.
2. `etl.download_gdb` baixa e valida o ZIP.
3. Em sucesso, dispara `etl.extrair_gdb` com:

```python
signature('etl.extrair_gdb', args=(job_id, str(zip_path))).delay()
```

4. `etl.extrair_gdb` extrai o ZIP, encontra o `.gdb`, valida schema de `CTMT`, `SSDMT` e `CONJ`.
5. Em sucesso, dispara um `chord`:

```python
chord(
    [
        signature('etl.processar_ctmt', args=(job_id, gdb_path)),
        signature('etl.processar_ssdmt', args=(job_id, gdb_path)),
        signature('etl.processar_conj', args=(job_id, gdb_path)),
    ],
    signature('etl.finalizar', args=(job_id, zip_path, str(tmp_dir))),
).delay()
```

6. O callback `etl.finalizar` recebe os resultados do header do chord e retorna o status final.

## Regras de falha

- Se `etl.download_gdb` falhar, `etl.extrair_gdb` nao e disparada.
- Se a validacao do GDB falhar em `etl.extrair_gdb`, o `chord` nao e disparado.
