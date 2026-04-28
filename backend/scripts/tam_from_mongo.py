import argparse
import os
from collections import defaultdict
from typing import Iterable

from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError


def _candidate_uris(env_uri: str | None) -> list[str]:
    uris: list[str] = []
    if env_uri:
        uris.append(env_uri)

    # In docker-compose, mongodb is usually reachable by service name.
    uris.extend([
        'mongodb://mongodb:27017',
        'mongodb://localhost:27017',
        'mongodb://127.0.0.1:27017',
    ])

    # Keep order and remove duplicates.
    seen = set()
    ordered: list[str] = []
    for uri in uris:
        if uri not in seen:
            ordered.append(uri)
            seen.add(uri)
    return ordered


def _connect_mongo(
    candidate_uris: Iterable[str], timeout_ms: int = 3000
) -> tuple[MongoClient, str]:
    last_error: Exception | None = None
    for uri in candidate_uris:
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
            client.admin.command('ping')
            return client, uri
        except ServerSelectionTimeoutError as exc:
            last_error = exc

    raise ConnectionError(
        'Nao foi possivel conectar ao MongoDB. '
        f'Tentativas: {list(candidate_uris)}. '
        f'Erro final: {last_error}'
    )


def _to_float(value):
    try:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip().replace(',', '.')
            if value == '':
                return None
        return float(value)
    except TypeError, ValueError:
        return None


def _head(rows: list[dict], size: int = 5) -> list[dict]:
    return rows[:size]


def build_tam_tables(
    db, job_id: str
) -> tuple[list[dict], list[dict], list[dict]]:
    ssdmt_cursor = db.segmentos_mt_tabular.find(
        {'job_id': job_id},
        {'_id': 0, 'COD_ID': 1, 'DIST': 1, 'CTMT': 1, 'CONJ': 1, 'COMP': 1},
    )
    ssdmt_rows = list(ssdmt_cursor)

    ctmt_doc = db.circuitos_mt.find_one(
        {'job_id': job_id},
        {'_id': 0, 'records.COD_ID': 1, 'records.NOME': 1},
    )

    if not ssdmt_rows:
        raise ValueError(
            f"Nenhum dado SSDMT encontrado em segmentos_mt_tabular para job_id='{job_id}'."
        )

    if not ctmt_doc or not ctmt_doc.get('records'):
        raise ValueError(
            f"Nenhum dado CTMT encontrado em circuitos_mt para job_id='{job_id}'."
        )

    # Build lookup COD_ID -> NOME from CTMT embedded records.
    nome_por_ctmt: dict[str, str | None] = {}
    for rec in ctmt_doc['records']:
        cod_id = rec.get('COD_ID')
        if cod_id is not None and cod_id not in nome_por_ctmt:
            nome_por_ctmt[cod_id] = rec.get('NOME')

    soma_por_trecho: dict[tuple, float] = defaultdict(float)
    for row in ssdmt_rows:
        comp = _to_float(row.get('COMP'))
        if comp is None:
            continue

        dist = row.get('DIST')
        conj = row.get('CONJ')
        ctmt = row.get('CTMT')
        nome = nome_por_ctmt.get(ctmt)
        key = (dist, conj, ctmt, nome)
        soma_por_trecho[key] += comp / 1000.0

    calculo_trechos = [
        {
            'DIST': dist,
            'CONJ': conj,
            'CTMT': ctmt,
            'NOME': nome,
            'COMP_KM': comp_km,
        }
        for (dist, conj, ctmt, nome), comp_km in soma_por_trecho.items()
    ]

    soma_por_conjunto: dict[tuple, float] = defaultdict(float)
    for row in calculo_trechos:
        key = (row['CONJ'], row['NOME'])
        soma_por_conjunto[key] += row['COMP_KM']

    ranking_por_conjunto = [
        {'CONJ': conj, 'NOME': nome, 'COMP_KM': comp_km}
        for (conj, nome), comp_km in soma_por_conjunto.items()
    ]
    ranking_top_10_conjunto = sorted(
        ranking_por_conjunto,
        key=lambda item: item['COMP_KM'],
        reverse=True,
    )[:10]

    return calculo_trechos, ranking_por_conjunto, ranking_top_10_conjunto


def _job_exists_in_ssdmt(db, job_id: str) -> bool:
    return (
        db.segmentos_mt_tabular.count_documents({'job_id': job_id}, limit=1)
        > 0
    )


def resolve_job_id(db, requested_job_id: str | None) -> str:
    if requested_job_id and _job_exists_in_ssdmt(db, requested_job_id):
        return requested_job_id

    jobs_col = db.jobs
    latest_job = jobs_col.find_one(
        {
            'status': 'completed',
            'ssdmt_total': {'$gt': 0},
        },
        {'_id': 0, 'job_id': 1},
        sort=[('updated_at', -1)],
    )
    if (
        latest_job
        and latest_job.get('job_id')
        and _job_exists_in_ssdmt(db, latest_job['job_id'])
    ):
        return latest_job['job_id']

    fallback = db.segmentos_mt_tabular.find_one(
        {},
        {'_id': 0, 'job_id': 1},
        sort=[('processed_at', -1)],
    )
    if fallback and fallback.get('job_id'):
        return fallback['job_id']

    raise ValueError(
        'Nenhum job com SSDMT encontrado na colecao segmentos_mt_tabular. '
        'Execute primeiro um ETL completo com persistencia SSDMT.'
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Calcula TAM (extensao de rede MT) a partir do MongoDB.'
    )
    parser.add_argument(
        '--job-id', default=os.getenv('JOB_ID'), help='Job ID a consultar'
    )
    parser.add_argument(
        '--mongo-uri',
        default=os.getenv('MONGO_URI'),
        help='URI do MongoDB (se omitido, tenta hosts padrao)',
    )
    parser.add_argument(
        '--mongo-db',
        default=os.getenv('MONGO_DB', 'fatec_api'),
        help='Database',
    )
    parser.add_argument(
        '--output-csv',
        default=os.getenv('TAM_OUTPUT_CSV'),
        help='Caminho opcional para salvar o Top 10 em CSV',
    )
    args = parser.parse_args()

    uris = _candidate_uris(args.mongo_uri)
    client, connected_uri = _connect_mongo(uris)

    db = client[args.mongo_db]
    selected_job_id = resolve_job_id(db, args.job_id)
    calculo_trechos, _, ranking_top_10 = build_tam_tables(db, selected_job_id)

    print(f'Conectado ao MongoDB: {connected_uri}')
    print(f'Base selecionada: {args.mongo_db}')
    if args.job_id and args.job_id != selected_job_id:
        print(
            f"JOB_ID solicitado '{args.job_id}' nao encontrado. "
            f"Usando '{selected_job_id}'."
        )
    else:
        print(f'JOB_ID selecionado: {selected_job_id}')
    print('\nResumo de Extensao de Rede MT (em Km):')
    print(_head(calculo_trechos, 5))
    print('\nTop 10 por extensao (Km):')
    print(ranking_top_10)

    if args.output_csv:
        import csv

        with open(args.output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['CONJ', 'NOME', 'COMP_KM'])
            writer.writeheader()
            writer.writerows(ranking_top_10)
        print(f'\nCSV salvo em: {args.output_csv}')


if __name__ == '__main__':
    main()
