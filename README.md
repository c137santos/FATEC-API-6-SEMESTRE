<h1 align="center">
API 6º Semestre Banco de Dados
<br/>
Thunderstone
</h1>

<h3 align="center">
  <img src="docs/img/logo-pokemon.png" alt="logo" width="30" style="vertical-align: middle;"> Equipe Pokémon
</h3>

<p align="center">
  | <a href ="#desafio"> Desafio</a>  |
  <a href ="#solucao"> Solução</a>  |   
  <a href ="#backlog"> Backlog do Produto</a>  |
  <a href ="#dor">DoR</a>  |
  <a href ="#dod">DoD</a>  |
  <a href ="#sprint"> Cronograma de Sprints</a>  |
  <a href ="#tecnologias">Tecnologias</a> |
  <a href ="#equipe"> Equipe</a> |
</p>

> Status do Projeto: Em execução 
>
> Pasta de Documentação: [docs](docs)
> 
> Video do Projeto: 🚧

## 🏅 Desafio <a id="desafio"></a>

O desafio proposto consiste na **identificação do potencial de aplicação de sensores de falta em redes de média e alta tensão**, com foco na melhoria da continuidade e qualidade do fornecimento de energia elétrica.


## 🏅 Solução <a id="solucao"></a>

O objetivo é **dimensionar o tamanho físico e econômico do sistema de distribuição ou subtransmissão de energia**, em uma região específica definida, a fim de avaliar a **potencialidade de mercado da solução da Tecsys**, voltada ao sensoriamento e telemetria das redes elétricas.

---

## 📋 Backlog do Produto <a id="backlog"></a>

| Rank | Prioridade | User Story | Story Points | Sprint | Requisito do Cliente | Status |
| :--: | :--------: | ---------- | :----------: | :----: | :------------------: | :----: |
| 1 |  Alta | Como um consultor comercial/técnico da Tecsys, eu quero visualizar uma tabela de classificação calculando o Índice de Criticidade (desvio percentual de DEC e FEC com base nos limites da ANEEL) de cada conjunto elétrico, para que eu possa identificar e priorizar rapidamente quais regiões possuem a pior eficiência estrutural. | 18 | 1 | [`RF1-DATA-INGEST`](process/requisitos.md#rf1-data-ingest---ingestão-de-dados-regulatórios)<br>[`RF2-ANALYTICS-CRIT`](process/requisitos.md#rf2-analytics-crit---cálculo-de-criticidade-e-perdas) | |
| 2 |  Alta | Como um membro do time comercial/técnico, eu quero visualizar um gráfico de barras ordenado pelos conjuntos elétricos com maior índice SAM, para que eu saiba rapidamente quais regiões têm prioridade máxima de implantação de sensores. | 10 | 1 |  [`RF1-DATA-INGEST`](process/requisitos.md#rf1-data-ingest---ingestão-de-dados-regulatórios)<br>[`RF2-ANALYTICS-CRIT`](process/requisitos.md#rf2-analytics-crit---cálculo-de-criticidade-e-perdas) |  |
| 3 |  Alta | Como um membro do time comercial/técnico, eu quero visualizar um gráfico de barras empilhadas que compare o volume absoluto (em MWh) das Perdas Técnicas (PT) e Não Técnicas (PNT) de cada conjunto elétrico, para evidenciar a magnitude das falhas estruturais da rede. | 10 |1  |  [`RF1-DATA-INGEST`](process/requisitos.md#rf1-data-ingest---ingestão-de-dados-regulatórios)<br>[`RF2-ANALYTICS-CRIT`](process/requisitos.md#rf2-analytics-crit---cálculo-de-criticidade-e-perdas) | |
| 4 |  Alta | Como um consultor comercial/técnico da Tecsys, eu quero visualizar um ranking com os 10 conjuntos elétricos com maior extensão de média tensão (TAM), para demonstrar os pontos de maior vulnerabilidade operacional. | 12 | 1 | [`RF1-DATA-INGEST`](process/requisitos.md#rf1-data-ingest---ingestão-de-dados-regulatórios)<br>[`RF2-ANALYTICS-TAM`](process/requisitos.md#rf2-analytics-tam---dimensionamento-físico-tam) |  |
| 5 |  Média | Como um consultor comercial/técnico da Tecsys, eu quero visualizar um mapa de calor georreferenciado indicando os circuitos mais críticos com base no Índice de Criticidade, para justificar investimentos em sensores inteligentes. | 8 | 2 | [`RF4-MAPS-HEATMAP`](process/requisitos.md#rf4-maps-heatmap---mapas-de-calor-e-polígonos) | |
| 6 |  Média | Como um usuário do sistema, eu quero dar consentimento sobre o uso dos meus dados, garantir anonimização e ser notificado em caso de incidentes, para assegurar conformidade com a LGPD. |  | 2 | [`RNF3-SEC-LGPD`](process/requisitos.md#rnf3-sec-lgpd---privacidade-e-anonimização) |  |
| 7 |  Média | Como gestor de segurança, eu quero que o sistema registre logs detalhados de acesso e manipulação de dados, para garantir auditoria e responsabilização. |  | 2 | [`RNF3-SEC-AUDIT`](process/requisitos.md#rnf3-sec-audit---rastreabilidade-logs) |  |
| 8 |  Baixa | Como um usuário do sistema, eu quero criar conta, fazer login e gerenciar meus dados básicos, para acessar a plataforma com autonomia. |  | 3 | [`RF5-AUTH-CRUD`](process/requisitos.md#rf5-auth-crud---criação-de-conta-e-login) |  |
| 9 |  Baixa | Como um consultor comercial/técnico da Tecsys, eu quero uma análise preditiva que recomende locais com maior risco de falhas e explique o motivo, para embasar propostas técnicas de instalação de sensores. |  | 3  | [`RF3-PREDICT-API`](process/requisitos.md#rf3-predict-api---api-de-aconselhamento-machine-learning) |  |
---

## 🏃‍ DoR - Definition of Ready
<a id="dor"></a>

Uma User Story será considerada **pronta para desenvolvimento** quando atender aos seguintes critérios:

- A história possui a narrativa estruturada no formato padrão ("Como um... Eu quero... Para que...")
- O tamanho da tarefa é viável, podendo ser codificada, testada e entregue dentro de um ciclo único de Sprint.
- Os cenários de uso (Caminho Feliz) estão descritos passo a passo.
- Os requisitos não funcionais específicos daquela entrega, como regras de LGPD, geração de logs de auditoria ou tempo de resposta, estão explícitos nos critérios.
- Caso a história impacte na interface visua, o protótipo, wireframe ou esboço da tela está anexado. 


## 🏆 DoD - Definition of Done <a id="dod"></a>

* Manual de Usuário
* Manual da Aplicação
* Documentação da API (Application Programming Interface)
* Código completo
* Vídeos de cada etapa de entrega

---

## 📅 Cronograma de Sprints <a id="sprint"></a>

| Sprint          |    Período    | Documentação                                     |
| --------------- | :-----------: | ------------------------------------------------ |
| 🔖 **SPRINT 1** | 16/03 - 05/04 |🚧|
| 🔖 **SPRINT 2** | 13/04 - 03/05 |🚧|
| 🔖 **SPRINT 3** | 11/05 - 31/05 |🚧 |

## 💻 Tecnologias <a id="tecnologias"></a>

<div align="">
  <img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Vue.js-35495E?style=for-the-badge&logo=vuedotjs&logoColor=4FC08D" alt="Vue.js" />
  <img src="https://img.shields.io/badge/MongoDB-4EA94B?style=for-the-badge&logo=mongodb&logoColor=white" alt="MongoDB" />
  <img src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/DBeaver-382923?style=for-the-badge&logo=dbeaver&logoColor=white" alt="DBeaver" />
  <img src="https://img.shields.io/badge/Google_Colab-F9AB00?style=for-the-badge&logo=googlecolab&color=525252" alt="Google Colab" />
</div>

## 🎓 Equipe <a id="equipe"></a>

<div align="center">
  <table>
    <tr>
      <th>Membro</th>
      <th>Função</th>
      <th>Github</th>
      <th>Linkedin</th>
    </tr>
    <tr>
      <td>Jean Rodrigues</td>
      <td>Scrum Master</td>
      <td><a href="https://github.com/JeanRodrigues1"><img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white"></a></td>
      <td><a href="https://www.linkedin.com/in/jean-rodrigues-0569a0251/"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white"></a></td>
    </tr>
    <tr>
      <td>Paloma Soares</td>
      <td>Product Owner</td>
      <td><a href="https://github.com/PalomaSoaresR"><img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white"></a></td>
      <td><a href="https://www.linkedin.com/in/paloma-soares-rocha/"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white"></a></td>
    </tr>
    <tr>
      <td>Isaque de Souza</td>
      <td>Desenvolvedor</td>
      <td><a href="https://github.com/Isaque-BD"><img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white"></a></td>
      <td><a href="https://www.linkedin.com/in/isaque-souza-6760b8270/"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white"></a></td>
    </tr>
    <tr>
      <td>Marília Moraes</td>
      <td>Desenvolvedora</td>
      <td><a href="https://github.com/marilia-borgo"><img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white"></a></td>
      <td><a href="https://www.linkedin.com/in/mariliaborgo/"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white"></a></td>
    </tr>
    <tr>
      <td>Maria Clara Santos</td>
      <td>Desenvolvedora</td>
      <td><a href="https://github.com/c137santos"><img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white"></a></td>
      <td><a href="https://www.linkedin.com/in/c137santos/"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white"></a></td>
    </tr>
    <tr>
      <td>Yan Yamim</td>
      <td>Desenvolvedor</td>
      <td><a href="https://github.com/YanYamim"><img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white"></a></td>
      <td><a href="https://www.linkedin.com/in/yan-yamim-185220278/"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white"></a></td>
    </tr>
  </table>
</div>
