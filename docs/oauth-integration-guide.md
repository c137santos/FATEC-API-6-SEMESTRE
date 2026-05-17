# Guia de Integração OAuth 2.0 + OIDC

Este projeto funciona como um **Authorization Server** OAuth 2.0 com suporte a OpenID Connect (OIDC). Outras aplicações internas podem delegar o login dos seus usuários para cá — o padrão "Login com X".

---

## Glossário

| Termo | Significado |
|---|---|
| **Authorization Server** | Este projeto. Servidor responsável por autenticar o usuário e emitir tokens. |
| **Client / App Cliente** | A aplicação que quer usar o login do usuário (ex: outro sistema interno). |
| **Resource Owner** | O usuário final que possui a conta e aprova o acesso. |
| **Authorization Code** | Código de uso único e curta duração (60 s) gerado após o consentimento. Trocado por tokens. |
| **Access Token** | Token de acesso opaco que a app cliente usa para chamar APIs protegidas. Expira em 1 hora. |
| **Refresh Token** | Token de longa duração usado para obter novos access tokens sem re-autenticar o usuário. |
| **ID Token** | JWT assinado (HS256) contendo a identidade do usuário (`sub`, `email`, `username`). |
| **PKCE** | Proof Key for Code Exchange (RFC 7636). Proteção contra interceptação do authorization code. Obrigatório neste servidor. |
| **code_verifier** | String aleatória de 43–128 caracteres gerada pela app cliente antes de iniciar o fluxo. |
| **code_challenge** | SHA-256 do `code_verifier`, codificado em base64url. Enviado na requisição de autorização. |
| **scope** | Conjunto de permissões solicitadas. Neste servidor: `openid`, `email`, `profile`. |
| **sub** | Subject identifier — identificador único e imutável do usuário neste servidor. |
| **OIDC** | OpenID Connect. Camada de identidade sobre OAuth 2.0 que adiciona o ID Token e o endpoint `/userinfo`. |
| **Discovery Document** | JSON em `/.well-known/openid-configuration` que descreve todos os endpoints e capacidades do servidor. |
| **redirect_uri** | URL da app cliente para onde o servidor redireciona após o consentimento. Deve ser pré-registrada. |
| **state** | String aleatória gerada pela app cliente para proteção CSRF. Deve ser validada no callback. |

---

## O que é esse fluxo?

Quando uma aplicação cliente quer autenticar um usuário, ela **não pede a senha diretamente**. Em vez disso, redireciona o usuário para este servidor, que faz o login e devolve um código seguro. A aplicação troca esse código por tokens.

O fluxo implementado é **Authorization Code + PKCE** (RFC 7636), que é o padrão recomendado para aplicações web e mobile. O PKCE protege contra interceptação do código de autorização.

```
Usuário         App Cliente          Este servidor (Authorization Server)
   |                  |                           |
   |  Clica "Login"   |                           |
   |----------------> |                           |
   |                  |--- GET /oauth/authorize -->|
   |                  |                           | valida client_id, redirect_uri
   |<----- redireciona para tela de login --------|
   |                  |                           |
   | faz login        |                           |
   |------------------------------------------>  |
   |<-------- tela de consentimento --------------|
   |                  |                           |
   | clica "Permitir" |                           |
   |------------------------------------------>  |
   |<----- redireciona com ?code=XXX -------------|
   |----------------> |                           |
   |                  |--- POST /oauth/token ----> |
   |                  |<-- access_token           |
   |                  |    refresh_token          |
   |                  |    id_token               |
```

---

## Passo a Passo para Integrar

### 1. Registrar sua aplicação

Faça uma chamada ao endpoint de registro para obter as credenciais da sua aplicação. Isso só precisa ser feito uma vez.

**`POST /oauth/clients`**

```http
POST http://localhost:8000/oauth/clients
Content-Type: application/json

{
  "client_name": "Minha Aplicação",
  "redirect_uris": ["http://minha-app.com/callback"],
  "allowed_scopes": ["openid", "email", "profile"]
}
```

**Resposta:**

```json
{
  "client_id": "a3f9e2b1c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3",
  "client_secret": "guarde-isso-com-segurança-não-será-exibido-novamente"
}
```

> **Importante:** o `client_secret` é exibido **apenas uma vez**. Guarde em local seguro.

Os escopos disponíveis são:

| Escopo    | O que libera                        |
|-----------|-------------------------------------|
| `openid`  | Identificador único do usuário (sub) |
| `email`   | Endereço de e-mail                  |
| `profile` | Nome de usuário                     |

---

### 2. Gerar o par PKCE

Antes de iniciar o fluxo, gere um `code_verifier` (string aleatória de 43–128 caracteres) e o `code_challenge` correspondente (SHA-256 do verifier, em base64url).

**Python:**

```python
import secrets
import hashlib
import base64

code_verifier = secrets.token_urlsafe(64)  # 43–128 chars

digest = hashlib.sha256(code_verifier.encode()).digest()
code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
```

**JavaScript:**

```js
const array = new Uint8Array(64);
crypto.getRandomValues(array);
const verifier = btoa(String.fromCharCode(...array))
  .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');

const encoder = new TextEncoder();
const data = encoder.encode(verifier);
const digest = await crypto.subtle.digest('SHA-256', data);
const challenge = btoa(String.fromCharCode(...new Uint8Array(digest)))
  .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
```

Guarde o `code_verifier` — ele será usado na etapa 4.

---

### 3. Redirecionar o usuário para a tela de autorização

Monte a URL e redirecione o navegador do usuário:

```
GET http://localhost:8000/oauth/authorize
  ?client_id=<seu_client_id>
  &redirect_uri=http://minha-app.com/callback
  &response_type=code
  &scope=openid email profile
  &state=<string_aleatória_para_csrf>
  &code_challenge=<code_challenge>
  &code_challenge_method=S256
```

**Parâmetros:**

| Parâmetro              | Descrição                                                  |
|------------------------|------------------------------------------------------------|
| `client_id`            | O ID recebido no registro                                  |
| `redirect_uri`         | Deve ser idêntico ao registrado                            |
| `response_type`        | Sempre `code`                                              |
| `scope`                | Escopos desejados, separados por espaço                    |
| `state`                | String aleatória; será devolvida no callback para validação CSRF |
| `code_challenge`       | Gerado no passo 2                                          |
| `code_challenge_method`| Sempre `S256`                                              |

O que acontece a seguir:
- Se o usuário **não estiver logado** → será redirecionado para a tela de login e voltará ao fluxo automaticamente.
- Se estiver logado → verá a tela de consentimento com as permissões solicitadas.

---

### 4. Receber o código no callback

Após o usuário aprovar, o servidor redireciona para a `redirect_uri` com:

```
http://minha-app.com/callback?code=XXXXXXXXXXXX&state=<estado>
```

Extraia o `code` e valide que o `state` bate com o que você gerou no passo 3.

---

### 5. Trocar o código por tokens

**`POST /oauth/token`**

```http
POST http://localhost:8000/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=XXXXXXXXXXXX
&code_verifier=<code_verifier_do_passo_2>
&client_id=<seu_client_id>
&redirect_uri=http://minha-app.com/callback
```

**Resposta:**

```json
{
  "access_token": "Dd2f2ozLYLZU8DXD...",
  "refresh_token": "7t8P0SvpTgwMObjax...",
  "id_token": "eyJhbGciOiJIUzI1NiJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "openid email profile"
}
```

| Token           | Para que serve                                          |
|-----------------|---------------------------------------------------------|
| `access_token`  | Chamar APIs protegidas (ex: `/oauth/userinfo`)          |
| `refresh_token` | Obter novo `access_token` sem re-autenticar o usuário   |
| `id_token`      | JWT com identidade do usuário — decodifique para obter os claims |

---

### 6. Ler a identidade do usuário

#### Opção A — Decodificar o ID Token (sem chamada extra)

O `id_token` é um JWT assinado com HS256. Decodifique o payload (parte do meio, base64url):

```python
import base64, json

parts = id_token.split('.')
payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))
# payload = {"sub": "42", "email": "user@example.com", "username": "alice", ...}
```

> Valide a assinatura em produção usando o `SECRET_KEY` compartilhado ou via `/oauth/userinfo`.

#### Opção B — Chamar `/oauth/userinfo`

```http
GET http://localhost:8000/oauth/userinfo
Authorization: Bearer <access_token>
```

**Resposta:**

```json
{
  "sub": "42",
  "email": "user@example.com",
  "username": "alice"
}
```

Os campos retornados dependem dos escopos concedidos:

| Escopo    | Campo retornado |
|-----------|-----------------|
| `openid`  | `sub`           |
| `email`   | `email`         |
| `profile` | `username`      |

---

### 7. Renovar o access token (Refresh)

Quando o `access_token` expirar (após 3600 segundos), use o `refresh_token`:

```http
POST http://localhost:8000/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&refresh_token=<seu_refresh_token>
&client_id=<seu_client_id>
```

A resposta inclui um novo `access_token`. O token anterior é invalidado imediatamente (rotação de tokens).

---

## Referência dos Endpoints

| Método | Endpoint                              | Descrição                              |
|--------|---------------------------------------|----------------------------------------|
| `POST` | `/oauth/clients`                      | Registrar nova aplicação cliente       |
| `GET`  | `/oauth/authorize`                    | Iniciar fluxo de autorização           |
| `POST` | `/oauth/authorize`                    | Submeter consentimento (interno)       |
| `POST` | `/oauth/token`                        | Trocar código ou refresh por tokens    |
| `GET`  | `/oauth/userinfo`                     | Buscar claims do usuário autenticado   |
| `GET`  | `/.well-known/openid-configuration`   | Discovery document (endpoints e config)|

---

## Discovery Document

A URL `/.well-known/openid-configuration` retorna um JSON com todos os endpoints e configurações:

```http
GET http://localhost:8000/.well-known/openid-configuration
```

```json
{
  "issuer": "http://localhost:8000",
  "authorization_endpoint": "http://localhost:8000/oauth/authorize",
  "token_endpoint": "http://localhost:8000/oauth/token",
  "userinfo_endpoint": "http://localhost:8000/oauth/userinfo",
  "scopes_supported": ["openid", "email", "profile"],
  "response_types_supported": ["code"],
  "id_token_signing_alg_values_supported": ["HS256"]
}
```

Bibliotecas compatíveis com OIDC podem usar essa URL para auto-configuração.

---

## Fora do escopo (não implementado)

- RS256 / JWKS endpoint
- Revogação de tokens (`/oauth/revoke`)
- Client Credentials grant (machine-to-machine)
- Registro dinâmico de clientes (RFC 7591)
