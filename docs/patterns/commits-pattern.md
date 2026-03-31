# Padrão de Commits

Para garantir um histórico de commits limpo, legível e padronizado, utilizamos uma convenção baseada no Conventional Commits, com adaptação para incluir o ID da issue.

---

## Estrutura do Commit

`tipo(id_do_ticket): descrição`

---

## Partes da Mensagem de Commit

### tipo
Obrigatório. Indica a natureza da alteração.

Tipos permitidos:

- `feat`: Nova funcionalidade  
- `fix`: Correção de bug  
- `docs`: Alterações na documentação  
- `style`: Formatação sem alteração de lógica  
- `refactor`: Refatoração sem nova funcionalidade ou correção de bug  
- `test`: Adição ou correção de testes  
- `chore`: Mudanças de build, scripts ou ferramentas auxiliares  
- `ci`: Alterações em arquivos de CI  
- `perf`: Melhorias de performance  
- `build`: Mudanças no sistema de build ou dependências  
- `revert`: Reversão de commit  

---

### id_do_ticket
- Identificador da issue relacionada  
- Deve estar entre parênteses `()`  

---

### descrição
- Breve explicação da alteração  
- Escrita em inglês  
- Utilizar letras minúsculas (exceto nomes próprios)  
- Deve ser clara e objetiva  

---

## Exemplos

### Nova funcionalidade
`feat(#3): add form to create a new user`

### Correção de bug
`fix(#5): fix button alignment on home page`

### Refatoração
`refactor(#12): optimize product search query`

---

## Boas Práticas

- Manter a descrição com no máximo 50 caracteres  
- Utilizar linguagem clara e objetiva  
- Para descrições mais detalhadas:
  - Adicionar uma linha em branco após o título  
  - Incluir um corpo explicativo  
  - Utilizar linhas com até 72 caracteres  