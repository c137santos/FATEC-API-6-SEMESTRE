import asyncio

from backend.services.criticidade import _col
from backend.services.render_criticidade import (
    render_mapa_calor_criticidade,
    render_tabela_score_criticidade,
)

DISTRIBUIDORA = 'ELETROPAULO'
DISTRIBUIDORA_ID = 'afa54a48397745a2b2fbc550880aa2d7'
ANO = 2024
JOB_ID = 'b7bd3177-2771-45fb-86c9-7a8de442c887'


async def main() -> None:
    await _col('mapa_criticidade').update_one(
        {'distribuidora': DISTRIBUIDORA, 'ano': ANO},
        {
            '$set': {
                'distribuidora': DISTRIBUIDORA,
                'distribuidora_id': DISTRIBUIDORA_ID,
                'ano': ANO,
                'job_id': JOB_ID,
            }
        },
        upsert=True,
    )
    print('job_id salvo.')

    print('Renderizando tabela...')
    path_tabela = await render_tabela_score_criticidade(DISTRIBUIDORA, ANO)
    print(f'Tabela salva em: {path_tabela}')

    print('Renderizando mapa de calor...')
    path_mapa = await render_mapa_calor_criticidade(DISTRIBUIDORA, ANO)
    print(f'Mapa salvo em: {path_mapa}')


asyncio.run(main())
