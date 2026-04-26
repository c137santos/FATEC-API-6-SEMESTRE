import json
import requests

# URL inicial (limit=100)
INITIAL_URL = 'https://hub.arcgis.com/api/search/v1/collections/all/items?q=BDGD&type=File%20Geodatabase&limit=100'


def extract_resources():
    all_resources = []

    # A variável next_url começa com a URL original e vai sendo atualizada no loop
    next_url = INITIAL_URL

    # Enquanto existir uma URL para buscar, o loop continua
    while next_url:
        print(f'Buscando lote em: {next_url}')

        try:
            response = requests.get(next_url)
            response.raise_for_status()
            payload = response.json()

            # 1. Extrai as features da página atual
            data = payload.get('features', [])

            for r in data:
                # Usando .get() para evitar erro caso a chave 'properties' não venha
                tags = r.get('properties', {}).get('tags', [])

                if tags and len(tags) >= 2:
                    dist_name = tags[-2]
                    data = tags[-1]
                else:
                    dist_name = 'NÃO ENCONTRADO'

                all_resources.append({
                    'id': r.get('id'),
                    'nome': dist_name,
                    'data': data,
                    'tags_originais': tags,
                })

            # 2. Lógica de Paginação (O "Pulo do Gato")
            links = payload.get('links', [])
            next_url = None  # Reseta a variável. Se não acharmos o "next", o loop acaba.

            for link in links:
                if link.get('rel') == 'next':
                    next_url = link.get('href')
                    break  # Achamos o próximo link, podemos sair do for

        except Exception as e:
            print(f'Erro durante a extração: {e}')
            break  # Em caso de erro na requisição, quebramos o loop para não ficar infinito

    print(
        f'\nExtração concluída! Total geral processado: {len(all_resources)}'
    )
    return all_resources


if __name__ == '__main__':
    resources = extract_resources()
    print('\n--- Primeiros 5 resultados ---')
    for r in resources[:5]:
        print(r)
    print('------------------------------\n')

    # Salva o arquivo completo com TODOS os resultados de todas as páginas
    with open('resources_aneel.json', 'w', encoding='utf-8') as f:
        json.dump(resources, f, ensure_ascii=False, indent=2)

    print("Arquivo 'resources_aneel.json' salvo com sucesso!")
