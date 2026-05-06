Aja como um Arquiteto de Software Sênior implacável e rabugento, focado em resiliência, consistência de dados e performance. Quero que você faça um "roast" (crítica pesada e construtiva) da minha proposta de arquitetura para resolver um problema de relacionamento de dados.

O Contexto e o Problema Atual: Hoje, os dados dec_fec_limite e dec_fec_realizado gravam parâmetros calculados no MongoDB. Para cruzar o ID da distribuidora (que vive no PostgreSQL) com essas coleções do Mongo, estamos usando a chave sig_agente (o nome da distribuidora em string) para recuperar nos calculos de criticidade e outros pontos. O problema: Isso é extremamente frágil. Os nomes vêm com formatação inconsistente, o que quebra o match com frequência.
A Minha Proposta de Solução: Notei que as tabelas do Mongo também possuem o CNPJ. É um dado muito mais assertivo. Descobri um endpoint da API de Dados Abertos da ANEEL que retorna a relação: DatGeracaoConjuntoDados, SigAgente, NumCNPJ.
 
``` 
https://dadosabertos.aneel.gov.br/api/3/action/datastore_search?resource_id=4493985c-baea-429c-9df5-3030422c71d7&limit=100&fields=DatGeracaoConjuntoDados,SigAgente,NumCNPJ&distinct=true
```

Acho necessário correlacionar o CNPJ a distribuidora na tabela do postgresql que existe hoje durante o fluxo de execução do endpoint `/backend/routes/dist.py` em /sync . A ideia é tentar cruzar as informações com Sig_agente com os nomes encontrados na tabela postgresql.
Assim, partir daí, usar o CNPJ como chave de cruzamento entre o PostgreSQL e o MongoDB, abandonando a busca por nome no código.
