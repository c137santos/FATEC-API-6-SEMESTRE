<h1 align="center">
6th Semester Database API
<br/>
Thunderstone
</h1>


<h3 align="center">
  <img src="docs/img/logo-pokemon.png" alt="logo" width="30" style="vertical-align: middle;"> Pokémon Team
</h3>


<p align="center">
  | <a href ="#desafio"> Challenge</a> |
  <a href ="#solucao"> Solution</a> |
  <a href ="#backlog"> Product Backlog</a> |
  <a href ="#dor">DoR</a> |
  <a href ="#dod">DoD</a> |
  <a href ="#padroes"> Project Standards</a> |
  <a href ="#sprint"> Sprint Schedule</a> |
  <a href ="#tecnologias">Technologies</a> |
  <a href ="#equipe"> Team</a> |
</p>


> Project Status: In progress
>
> Documentation Folder: [docs](docs)
>
> Project Video: 🚧


## 🏅 Challenge <a id="desafio"></a>


Dimension the power distribution system to enable the expansion of Tecsys telemetry technologies. The main obstacle to be overcome is the standardization of calculations and the high complexity of handling ANEEL’s vast data volume.


## 🏅 Solution <a id="solucao"></a>


The solution consists of developing a platform capable of processing ANEEL’s massive and unstructured data and standardizing the loss calculation. The system translates this data into strategic visualizations, such as heatmaps and rankings, which geographically highlight the most critical sections of the power grid.


---


## 📋 Product Backlog <a id="backlog"></a>


| Rank | Priority | User Story | Story Points | Sprint | Client Requirement | Status |
| :--: | :------: | ---------- | :----------: | :----: | :----------------: | :----: |
| 1 | High | As a Tecsys sales/technical consultant, I want to view a ranking table that calculates the Criticality Index (percentage deviation of DEC and FEC based on ANEEL limits) for each electrical set, so that I can quickly identify and prioritize which regions have the worst structural efficiency. | 18 | 1 | [`RF1-DATA-INGEST`](process/requisitos.md#rf1-data-ingest---ingestão-de-dados-regulatórios)<br>[`RF2-ANALYTICS-CRIT`](process/requisitos.md#rf2-analytics-crit---cálculo-de-criticidade-e-perdas) | ✅|
| 2 | High | As a member of the sales/technical team, I want to view a bar chart ordered by the electrical sets with the highest SAM score, so that I can quickly know which regions have the highest priority for sensor deployment. | 10 | 1 | [`RF1-DATA-INGEST`](process/requisitos.md#rf1-data-ingest---ingestão-de-dados-regulatórios)<br>[`RF2-ANALYTICS-CRIT`](process/requisitos.md#rf2-analytics-crit---cálculo-de-criticidade-e-perdas) | ✅ |
| 3 | High | As a member of the sales/technical team, I want to view a stacked bar chart comparing the absolute volume (in MWh) of Technical Losses (PT) and Non-Technical Losses (PNT) for each electrical set, in order to show the magnitude of the grid’s structural issues. | 10 | 1 | [`RF1-DATA-INGEST`](process/requisitos.md#rf1-data-ingest---ingestão-de-dados-regulatórios)<br>[`RF2-ANALYTICS-CRIT`](process/requisitos.md#rf2-analytics-crit---cálculo-de-criticidade-e-perdas) | ✅ |
| 4 | High | As a Tecsys sales/technical consultant, I want to view a ranking of the 10 electrical sets with the greatest medium-voltage extension (TAM), to demonstrate the points with the highest operational vulnerability. | 12 | 1 | [`RF1-DATA-INGEST`](process/requisitos.md#rf1-data-ingest---ingestão-de-dados-regulatórios)<br>[`RF2-ANALYTICS-TAM`](process/requisitos.md#rf2-analytics-tam---dimensionamento-físico-tam) | ✅ |
| 5 | Medium | As a Tecsys sales/technical consultant, I want to view a georeferenced heatmap indicating the most critical circuits based on the Criticality Index, in order to justify investments in smart sensors. | 8 | 2 | [`RF4-MAPS-HEATMAP`](process/requisitos.md#rf4-maps-heatmap---mapas-de-calor-e-polígonos) | ✅|
| 6 | Medium | As a Tecsys sales consultant, I want to automatically generate the complete analysis of a selected distribution company, so that I can prepare and deliver sales presentations autonomously, without needing to understand or interact with any technical step of the process. |  | 2 | [`RF1-DATA-INGEST`](process/requisitos.md#rf1-data-ingest---ingestão-de-dados-regulatórios)<br>[`RF2-ANALYTICS-CRIT`](process/requisitos.md#rf2-analytics-crit---cálculo-de-criticidade-e-perdas) |  |
| 7 | Medium | As a Tecsys sales consultant, I want the system to automatically generate a PDF report consolidating the SAM, PT/PNT, TAM, Criticality Index, and Heatmap charts as soon as calculations are completed, so that I have the presentation material ready with no manual action, allowing me to focus on the commercial approach with the utility’s engineer. |  | 2 | [`RF6-EXPORT-PDF`](process/requisitos.md#rf6-export-pdf---geração-de-proposta-comercial-em-pdf) |  |
| 8 | Medium | As a Tecsys sales consultant, I want exclusive and secure access to the platform using my corporate credentials, so that only authenticated team members can view strategic analyses and reports, and I can manage my account with full autonomy, without depending on technical support. |  | 2 | [`RF5-AUTH-CRUD`](process/requisitos.md#rf5-auth-crud---criação-de-conta-e-login) |  |
| 9 | Medium | As a Tecsys sales consultant, I want to send the PDF report generated by the platform directly to an email address of my choice with my corporate address already suggested, so that I can easily access the presentation material. |  | 2 | [`RF6-EXPORT-PDF`](process/requisitos.md#rf6-export-pdf---geração-de-proposta-comercial-em-pdf) |  |
| 10 | Low | As a registered consultant, I want to have clarity and assurance that my personal information is fully protected and will be used solely and exclusively for the platform’s operation, so that I feel confident that my privacy is being fully respected. |  | 3 | [`RNF3-SEC-LGPD`](process/requisitos.md#rnf3-sec-lgpd---privacidade-e-anonimização) |  |
| 11 | Low | As a Tecsys manager, I want to have a clear history of who accessed, generated, changed, or deleted information within the platform, so that I can understand exactly what happened in case of errors, audits, or suspicious behavior, ensuring protection of our business. |  | 3 | [`RNF3-SEC-AUDIT`](process/requisitos.md#rnf3-sec-audit---rastreabilidade-logs) |  |
| 12 | Low | As a Tecsys technical consultant, I want the platform to identify trends and predict which sections are most likely to face higher risk of outages and fines in the future, so that I can sell sensors as a preventive solution, helping the client act before problems and financial losses occur. |  | 3 | [`RF3-PREDICT-API`](process/requisitos.md#rf3-predict-api---api-de-aconselhamento-machine-learning) |  |

---


## 🏃‍ DoR - Definition of Ready
<a id="dor"></a>


A User Story will be considered **ready for development** when it meets the following criteria:


- The story has its narrative structured in the standard format (“As a... I want... So that...”).
- Task size is feasible, and it can be coded, tested, and delivered within a single Sprint cycle.
- Usage scenarios (Happy Path) are described step by step.
- The non-functional requirements specific to that delivery, such as LGPD rules, audit log generation, or response time, are explicitly stated in the criteria.
- If the story impacts the UI, the prototype, wireframe, or screen sketch is attached.
> All acceptance criteria and User Story details can be found in Confluence: [Access US's in Confluence](https://jeanroodrigues.atlassian.net/wiki/spaces/~611d654d4016870069296c0d/folder/20742146?atlOrigin=eyJpIjoiOGRhY2I4NzRjMWVlNDEyYzk0YTc1ZDg0OGE5MDFhYWQiLCJwIjoiYyJ9)



## 🏆 DoD - Definition of Done <a id="dod"></a>


* [User Manual](docs/guides/user-guide.md)
* [Application Manual](docs/guides/application-manual.md)
* API Documentation (Application Programming Interface)
* Complete source code
* Videos for each delivery stage


---
## 📖 Project Standards <a id="padroes"></a>


Our versioning standards — including **commit standards, Pull Requests (PR), and branch naming convention** — are centralized in our Confluence workspace. To check the guides, rules, or align with team practices, access the link:


> 🔗 **[Access Commit, PR and Branch Standards in Confluence](https://jeanroodrigues.atlassian.net/wiki/x/BID5)**


---


## 📅 Sprint Schedule <a id="sprint"></a>


| Sprint          |   Period    | Documentation                                     | Delivery Video                                      |
| --------------- | :---------: | ------------------------------------------------- | --------------------------------------------------- |
| 🔖 **SPRINT 1** | 16/03 - 05/04 |[doc](docs/process/sprints-backlog/sprint-1.md)| [video](https://drive.google.com/file/d/14Rk7tpzycikkkxXpeZZ4nF5BHbvCanvW/view?usp=drive_link)
| 🔖 **SPRINT 2** | 13/04 - 03/05 |[doc](docs/process/sprints-backlog/sprint-2.md)|🚧|
| 🔖 **SPRINT 3** | 11/05 - 31/05 |🚧 | 🚧 |

---


## 💻 Technologies <a id="tecnologias"></a>


<div align="">
  <img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Vue.js-35495E?style=for-the-badge&logo=vuedotjs&logoColor=4FC08D" alt="Vue.js" />
  <img src="https://img.shields.io/badge/MongoDB-4EA94B?style=for-the-badge&logo=mongodb&logoColor=white" alt="MongoDB" />
  <img src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/DBeaver-382923?style=for-the-badge&logo=dbeaver&logoColor=white" alt="DBeaver" />
  <img src="https://img.shields.io/badge/Google_Colab-F9AB00?style=for-the-badge&logo=googlecolab&color=525252" alt="Google Colab" />
</div>


---


## 🎓 Team <a id="equipe"></a>


<div align="center">
  <table>
    <tr>
      <th>Member</th>
      <th>Role</th>
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
      <td>Developer</td>
      <td><a href="https://github.com/Isaque-BD"><img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white"></a></td>
      <td><a href="https://www.linkedin.com/in/isaque-souza-6760b8270/"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white"></a></td>
    </tr>
    <tr>
      <td>Marília Moraes</td>
      <td>Developer</td>
      <td><a href="https://github.com/marilia-borgo"><img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white"></a></td>
      <td><a href="https://www.linkedin.com/in/mariliaborgo/"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white"></a></td>
    </tr>
    <tr>
      <td>Maria Clara Santos</td>
      <td>Developer</td>
      <td><a href="https://github.com/c137santos"><img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white"></a></td>
      <td><a href="https://www.linkedin.com/in/c137santos/"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white"></a></td>
    </tr>
    <tr>
      <td>Yan Yamim</td>
      <td>Developer</td>
      <td><a href="https://github.com/YanYamim"><img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white"></a></td>
      <td><a href="https://www.linkedin.com/in/yan-yamim-185220278/"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white"></a></td>
    </tr>
  </table>
</div>


---