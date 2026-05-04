#!/usr/bin/env python3
"""
Executa a pipeline para todas as distribuidoras em paralelo (concorrência configurável).
Em caso de falha, registra o motivo e passa para a próxima.
Distribuidoras com timeout recebem uma rodada extra de re-polling ao final (--max-retries).

Uso (dentro do Docker):
    docker exec api uv run python backend/scripts/pipeline_loop.py
    docker exec api uv run python backend/scripts/pipeline_loop.py --year 2024
    docker exec api uv run python backend/scripts/pipeline_loop.py --concurrency 5 --max-retries 1

Variáveis de ambiente:
    API_BASE_URL  URL base da API (padrão: http://localhost:8000)
"""

import argparse
import json
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

LOG_FILE = '/tmp/pipeline_loop.log'
FAILURE_LOG_FILE = '/tmp/pipeline_loop_failures.json'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE),
    ],
)
logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {'completed', 'failed'}


def _base_url() -> str:
    return os.getenv('API_BASE_URL', 'http://localhost:8000')


def fetch_distribuidoras(base_url: str, year: int | None) -> list[dict]:
    resp = requests.get(f'{base_url}/dist/distributors', timeout=30)
    resp.raise_for_status()
    distribuidoras = resp.json()

    if year is not None:
        distribuidoras = [d for d in distribuidoras if d['ano'] == year]

    logger.info('Distribuidoras encontradas: %d', len(distribuidoras))
    return distribuidoras


def trigger(base_url: str, dist_id: str, ano: int) -> bool:
    """Dispara a pipeline. Retorna False se deve pular (409) ou erro."""
    try:
        resp = requests.post(
            f'{base_url}/pipeline/trigger',
            json={'distribuidora_id': dist_id, 'ano': ano},
            timeout=30,
        )

        if resp.status_code == 409:
            logger.info('[%s/%d] Já processada anteriormente, pulando.', dist_id, ano)
            return False

        if resp.status_code == 502:
            error_detail = None
            try:
                error_detail = resp.json().get('detail', '')
            except ValueError:
                error_detail = resp.text

            if error_detail and (
                'Nenhum registro encontrado nas coleções do MongoDB' in error_detail
                or 'Nenhum registro encontrado na coleção do MongoDB' in error_detail
            ):
                logger.warning(
                    '[%s/%d] Erro de dados ausentes no MongoDB: %s. Pulando para a próxima.',
                    dist_id,
                    ano,
                    error_detail.strip(),
                )
                return False

        resp.raise_for_status()
        job_id = resp.json().get('job_id', '?')
        logger.info('[%s/%d] Pipeline disparada. job_id=%s', dist_id, ano, job_id)
        return True

    except requests.RequestException as exc:
        logger.error('[%s/%d] Falha ao disparar pipeline: %s', dist_id, ano, exc)
        return False


def poll_until_done(
    base_url: str,
    dist_id: str,
    ano: int,
    poll_interval: int,
    max_attempts: int,
    min_wait: int = 0,
) -> dict:
    """
    Aguarda o pipeline terminar.
    Retorna dict com: status, error, failed_task.
    Se min_wait > 0, aguarda esse tempo antes do primeiro poll (cobre download + descompactação).
    """
    if min_wait > 0:
        logger.info('[%s/%d] Aguardando %ds antes de iniciar polling (min-wait).', dist_id, ano, min_wait)
        time.sleep(min_wait)

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(
                f'{base_url}/pipeline/report/{dist_id}',
                timeout=30,
            )

            if resp.status_code == 404:
                logger.debug(
                    '[%s/%d] #%d job ainda não registrado, aguardando...',
                    dist_id, ano, attempt,
                )
                time.sleep(poll_interval)
                continue

            resp.raise_for_status()
            doc = resp.json()
            etl = doc.get('etl_status', '?')
            report = doc.get('report_status', 'pending')

            logger.info(
                '[%s/%d] #%d etl=%s report=%s',
                dist_id, ano, attempt, etl, report,
            )

            if report in TERMINAL_STATUSES:
                result = {'status': report, 'error': None, 'failed_task': None}
                if report == 'failed':
                    result['error'] = doc.get('error')
                    result['failed_task'] = doc.get('failed_task')
                    logger.error(
                        '[%s/%d] Pipeline falhou. task=%s erro=%s',
                        dist_id, ano,
                        result['failed_task'] or 'desconhecida',
                        result['error'] or 'sem detalhe',
                    )
                return result

        except requests.RequestException as exc:
            logger.warning('[%s/%d] #%d erro ao consultar status: %s', dist_id, ano, attempt, exc)

        time.sleep(poll_interval)

    logger.error(
        '[%s/%d] Timeout após %d tentativas.',
        dist_id, ano, max_attempts,
    )
    return {'status': 'timeout', 'error': 'Timeout excedido no polling', 'failed_task': None}


def _write_failure_log(failures: list[dict]) -> None:
    try:
        with open(FAILURE_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(failures, f, ensure_ascii=False, indent=2, default=str)
        logger.info('Arquivo de falhas gravado em: %s', FAILURE_LOG_FILE)
    except OSError as exc:
        logger.warning('Não foi possível gravar arquivo de falhas: %s', exc)


def _process_one(
    base_url: str,
    dist: dict,
    poll_interval: int,
    max_attempts: int,
    min_wait: int = 0,
    skip_trigger: bool = False,
) -> tuple[dict, dict]:
    """Dispara (se skip_trigger=False) e aguarda conclusão de uma distribuidora."""
    dist_id = dist['id']
    ano = dist['ano']

    if not skip_trigger:
        if not trigger(base_url, dist_id, ano):
            return dist, {'status': 'skipped', 'error': None, 'failed_task': None}

    return dist, poll_until_done(base_url, dist_id, ano, poll_interval, max_attempts, min_wait)


def _run_batch(
    base_url: str,
    distribuidoras: list[dict],
    poll_interval: int,
    max_attempts: int,
    concurrency: int,
    min_wait: int = 0,
    skip_trigger: bool = False,
) -> tuple[dict, list[dict], list[dict]]:
    """
    Processa um lote de distribuidoras em paralelo (até `concurrency` simultâneas).
    Retorna: (counts, failure_log, timed_out_dists)
    """
    counts: dict[str, int] = {'sucesso': 0, 'falha': 0, 'pulada': 0}
    failure_log: list[dict] = []
    timed_out_dists: list[dict] = []
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(
                _process_one, base_url, dist, poll_interval, max_attempts, min_wait, skip_trigger
            ): dist
            for dist in distribuidoras
        }

        for future in as_completed(futures):
            dist = futures[future]
            dist_id = dist['id']
            ano = dist['ano']
            nome = dist['nome']

            try:
                _, result = future.result()
                status = result['status']

                with lock:
                    if status == 'skipped':
                        counts['pulada'] += 1
                    elif status == 'completed':
                        counts['sucesso'] += 1
                        logger.info('[%s/%d] Status final: completed', dist_id, ano)
                    else:
                        counts['falha'] += 1
                        failure_log.append({
                            'nome': nome,
                            'dist_id': dist_id,
                            'ano': ano,
                            'status': status,
                            'error': result.get('error'),
                            'failed_task': result.get('failed_task'),
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                        })
                        if status == 'timeout':
                            timed_out_dists.append(dist)
                        logger.info('[%s/%d] Status final: %s', dist_id, ano, status)

            except Exception:
                with lock:
                    counts['falha'] += 1
                    failure_log.append({
                        'nome': nome,
                        'dist_id': dist_id,
                        'ano': ano,
                        'status': 'exception',
                        'error': 'Exceção inesperada no processamento (ver log)',
                        'failed_task': None,
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                    })
                logger.exception(
                    '[%s/%d] Erro inesperado ao processar esta distribuidora.',
                    dist_id, ano,
                )

    return counts, failure_log, timed_out_dists


def run(
    year: int | None,
    poll_interval: int,
    max_attempts: int,
    concurrency: int,
    max_retries: int,
    min_wait: int,
) -> None:
    base_url = _base_url()
    logger.info(
        '=== Iniciando loop de pipeline. API=%s concorrência=%d min-wait=%ds ===',
        base_url, concurrency, min_wait,
    )

    distribuidoras = fetch_distribuidoras(base_url, year)
    total = len(distribuidoras)

    counts, failure_log, timed_out_dists = _run_batch(
        base_url, distribuidoras, poll_interval, max_attempts, concurrency, min_wait,
    )

    # Re-poll distribuidoras com timeout — o job Celery pode ainda estar rodando.
    # min_wait=0 no retry pois o job já passou pela fase de download.
    for retry_round in range(1, max_retries + 1):
        if not timed_out_dists:
            break
        logger.info(
            '=== Retry #%d: re-polling %d distribuidoras com timeout. ===',
            retry_round, len(timed_out_dists),
        )
        to_retry = timed_out_dists
        retry_counts, retry_failures, timed_out_dists = _run_batch(
            base_url, to_retry, poll_interval, max_attempts, concurrency, skip_trigger=True,
        )
        retried_ids = {d['id'] for d in to_retry}
        failure_log = [f for f in failure_log if f['dist_id'] not in retried_ids]
        failure_log.extend(retry_failures)
        counts['falha'] -= len(to_retry)
        for key in counts:
            counts[key] += retry_counts[key]

    logger.info(
        '=== Loop concluído. Total=%d | Sucesso=%d | Falha=%d | Pulada=%d ===',
        total, counts['sucesso'], counts['falha'], counts['pulada'],
    )

    if failure_log:
        logger.warning('=== FALHAS DETALHADAS (%d) ===', len(failure_log))
        for entry in failure_log:
            logger.warning(
                '  [%s | %s | ano=%s] status=%s | task=%s | erro=%s',
                entry['nome'],
                entry['dist_id'],
                entry['ano'],
                entry['status'],
                entry['failed_task'] or '-',
                entry['error'] or '-',
            )
        _write_failure_log(failure_log)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Roda a pipeline para todas as distribuidoras em paralelo.'
    )
    parser.add_argument(
        '--year', type=int, default=None,
        help='Filtrar por ano (ex: --year 2024). Sem argumento processa todos os anos.',
    )
    parser.add_argument(
        '--poll-interval', type=int, default=30,
        help='Segundos entre cada consulta de status (padrão: 30).',
    )
    parser.add_argument(
        '--max-attempts', type=int, default=30,
        help='Máximo de tentativas de polling por distribuidora (padrão: 30).',
    )
    parser.add_argument(
        '--concurrency', type=int, default=3,
        help='Distribuidoras processadas em paralelo (padrão: 3).',
    )
    parser.add_argument(
        '--max-retries', type=int, default=1,
        help='Rodadas extras de re-polling para distribuidoras com timeout (padrão: 1).',
    )
    parser.add_argument(
        '--min-wait', type=int, default=60,
        help='Segundos de espera após o trigger antes de iniciar o polling (padrão: 60).'
             ' Cobre o tempo de download + descompactação do GDB.',
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    started_at = datetime.now()

    try:
        run(
            year=args.year,
            poll_interval=args.poll_interval,
            max_attempts=args.max_attempts,
            concurrency=args.concurrency,
            max_retries=args.max_retries,
            min_wait=args.min_wait,
        )
    except KeyboardInterrupt:
        logger.info('Interrompido pelo usuário.')
    except Exception:
        logger.exception('Erro inesperado no loop principal.')
        sys.exit(1)
    finally:
        elapsed = datetime.now() - started_at
        logger.info('Tempo total de execução: %s', elapsed)
