# 🚀 Backend Python 3.14 (FastAPI + SQLAlchemy Async)

Este é um projeto de backend moderno, focado em performance assíncrona, utilizando as tecnologias mais recentes do ecossistema Python.



## 📋 Sobre o Projeto

O projeto utiliza **Python 3.14** e uma arquitetura orientada a performance com **FastAPI**. A persistência de dados é feita de forma assíncrona com **SQLAlchemy 2.0** e **Postgres**, garantindo que a aplicação seja capaz de lidar com alta concorrência sem bloqueios de I/O.




## 📚 Dependências e Tecnologias

### Core (Runtime)
* **FastAPI [standard]**: Framework web de alta performance com validação automática via Pydantic.
* **SQLAlchemy 2.0**: ORM configurado para operações 100% assíncronas.
* **Alembic**: Gerenciamento e versionamento de migrações de banco de dados.
* **asyncpg**: Driver de comunicação assíncrona nativa para PostgreSQL.
* **PyJWT & pwdlib [argon2]**: Suite de segurança para autenticação JWT e hashing de senhas com Argon2id.
* **Motor & PyMongo**: Drivers para integração e suporte a bancos NoSQL (MongoDB).

### Configuração

* **Pydantic-Settings**: Gerenciamento de configurações e variáveis de ambiente via classes Python, garantindo validação de tipos para as chaves de API e strings de conexão.

### Desenvolvimento e Testes (Dev)
* **Pytest & Pytest-Asyncio**: Infraestrutura de testes para código assíncrono.
* **Pytest-Cov**: Gera relatórios de cobertura de código, mostrando quais partes da aplicação ainda não foram testadas.
* **Testcontainers**: Automação de containers Docker (Postgres:16) para testes de integração em ambiente real.
* **Factory Boy**: Usado para criar fábricas de objetos (usuários, registros) para testes, evitando a criação manual de dados.
* **Freezegun**: Permite "congelar" o tempo em testes, essencial para validar se tokens JWT expiram no momento correto.


### Linting e Formatação
* **Ruff**: Um linter e formatador de código extremamente rápido que substitui o Flake8, Isort e Black. Ele garante que o código siga as normas da PEP 8.

### Automação
* **Taskipy**: Gerenciador de tarefas que permite criar comandos curtos para operações complexas.

### 🏎️ Comandos Rápidos (Taskipy)
Os seguintes comandos estão configurados no projeto para agilizar o fluxo de trabalho:
* **task lint**: Executa o Ruff para encontrar erros e problemas de estilo no código.
* **task format**: Formata automaticamente o código seguindo os padrões do projeto.
* **task run**: Inicia o servidor de desenvolvimento do FastAPI.
* **task test**: Executa a suíte completa de testes com detalhes e cobertura.

---

## 🛠️ Guia de Instalação

### Pré-requisitos
* **Python 3.14** ou superior.
* **Docker** instalado e ativo (necessário para rodar a suíte de testes).

### Opção 1: Usando `uv` (Recomendado)
O `uv` é o gerenciador de pacotes mais rápido do ecossistema atual.
```bash
# 1. Instalar dependências e criar venv
uv sync

# 2. Ativar o ambiente virtual
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
