# 🛠️ Guia de Instalação e Configuração

Siga os passos abaixo para preparar o ambiente de desenvolvimento. Este projeto utiliza o **Python 3.14** e o gerenciador de pacotes **uv** para máxima performance.


## 📋 Pré-requisitos

Antes de iniciar, certifique-se de ter instalado:
1. **Python 3.14**: [Download Python](https://www.python.org/downloads/)
2. **Docker**: Necessário para rodar os testes de integração com `Testcontainers`.
3. **uv** (Opcional, mas recomendado): Gerenciador de pacotes rápido.

---

## 🚀 Instalação Rápida (Recomendado via `uv`)

O `uv` sincroniza o ambiente virtual e as dependências em segundos.

1. **Instale o `uv` (caso não tenha):**
   ```bash
   # macOS/Linux
   curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh
   # Windows (PowerShell)
   powershell -c "irm [https://astral.sh/uv/install.ps1](https://astral.sh/uv/install.ps1) | iex"

2. **Sincronize o projeto**

```bash
uv sync
```

3. **Ative o ambiente virtual**
```bash
# Linux/macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 🐢 Instalação via pip (Tradicional)
Caso prefira usar o pip padrão do Python:

1. **Crie o ambiente virtual**
```bash
python3.14 -m venv .venv
```

2. **Ative o ambiente virtual**
```bash
# Linux/macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

3. **Instale as dependẽncias**
```bash
pip install .
pip install ".[dev]"
```

---

### ⚙️ Configuração do Ambiente
Crie um arquivo .env na raiz do projeto para armazenar suas credenciais:

```bash
DATABASE_URL=""
SECRET_KEY=""
ALGORITHM=""
ACCESS_TOKEN_EXPIRE_MINUTES=""
```
