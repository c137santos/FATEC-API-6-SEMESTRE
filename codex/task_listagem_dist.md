# Instruction para Codex - Task CTMT

---

## Objetivo

O objetivo da aplicação é consumir metadados paginados de uma API do ArcGIS Hub (formato GeoJSON) e salvar as informações em um banco de dados PostgreSQL. Faça a cobertura de testes com pytest.

1. Stack Tecnológica Obrigatória:

Framework Web: FastAPI

Cliente HTTP: para chamadas assíncronas no lugar do requests

ORM e Banco: SQLAlchemy (com asyncpg) e PostgreSQL

Validação: Pydantic

2. O Script de Prova de Conceito (Regra de Negócio):
Abaixo está o script síncrono que já valida a paginação via "links" (padrão HATEOAS), a extração dos dados (id, nome, data) e o tratamento de erros.
Melhore e simplifique no que for necessário.
Utilize a lógica dele como base para o seu código assíncrono:

```

from datetime import datetime
import requests

INITIAL_URL = "https://hub.arcgis.com/api/search/v1/collections/all/items?q=BDGD&type=File%20Geodatabase&limit=100"

def extract_resources():
    all_resources = []
    next_url = INITIAL_URL

    while next_url:
        try:
            response = requests.get(next_url)
            response.raise_for_status()
            payload = response.json()

            data = payload.get("features", [])

            for r in data:
                tags = r.get('properties', {}).get('tags', [])

                if tags and len(tags) >= 2:
                    dist_name = tags[-2]
                    data_string = tags[-1]
                    try:
                        data_formatada = datetime.strptime(data_string, "%Y-%m-%d").date()
                    except ValueError:
                        data_formatada = None
                else:
                    dist_name = "NÃO ENCONTRADO"
                    data_formatada = None

                all_resources.append({
                    "id": r.get("id"),
                    "nome": dist_name,
                    "data": data_formatada
                })

            links = payload.get("links", [])
            next_url = None
            for link in links:
                if link.get("rel") == "next":
                    next_url = link.get("href")
                    break

        except Exception as e:
            break

    return all_resources

```

3. Requisitos de Persistência (PostgreSQL + SQLAlchemy):

Crie o model para uma tabela chamada distribuidoras.

Constraint de Chave: A tabela deve ter uma Chave Primária Composta (Composite Primary Key) formada pelas colunas id e data (nome da coluna no banco: date_gdb).

Idempotência e Upsert: O endpoint pode ser acionado várias vezes. Ao salvar no banco, você PODE, ou algo que julgar melhor, utilizar uma instrução de Upsert nativa do PostgreSQL (from sqlalchemy.dialects.postgresql import insert). Se houver conflito na Primary Key, atualize o dist_name (ON CONFLICT DO UPDATE).

4. Entregáveis Esperados:

Por favor, forneça o código estruturado dividindo as responsabilidades:

models.py: Modelagem do SQLAlchemy. com campo de update

schemas.py: Schemas Pydantic.

services.py: A lógica do request async iterando a paginação de forma assíncrona. Com a lógica de upsert

router.py: O endpoint FastAPI em si expondo o serviço.
