# Estrutura de Branches

---

## Visão Geral

Este documento descreve a estratégia de branches utilizando Git Flow, adaptado para integração com GitHub Projects.

---

## Estrutura de Branches

### main
- Representa o código pronto para produção
- Deve conter apenas commits estáveis

---

### dev
- Branch de integração das novas funcionalidades
- Contém o histórico completo do projeto
- Pode incluir features ainda não publicadas

---

### feature branches
- Criadas a partir da branch `dev`
- Utilizadas para desenvolvimento de novas funcionalidades
- Após conclusão, devem ser mergeadas novamente na `dev`

---

## Regras de Nomenclatura

O nome da branch deve obrigatoriamente referenciar o ID da tarefa (ticket/issue), garantindo rastreabilidade.

---

### Padrão Geral

`[ticket-id]-[short-task-title]`

**Exemplos:**
- `pk-32-download-gdb`
- `pk-15-create-user-auth`

---

### Branches de Estudo/Pesquisa (Spike)

`spike-[us-id]-[us-title]`

**Exemplo:**
- `spike-us-01-download-pdf`

---

## Diretrizes

- Substituir espaços por hífens (`-`)
- Não utilizar letras maiúsculas
- Evitar caracteres especiais
- Sempre incluir o ID da tarefa na branch
