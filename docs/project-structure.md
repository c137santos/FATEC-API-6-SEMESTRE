#  Project Structure - Thunderstone API

> Reference document for future maintenance and system development.

---

##  Architecture Overview

```
FATEC-API-6-SEMESTRE/
├── backend/                 # FastAPI + business logic
├── frontend/                # HTML/CSS interface
├── docs/                    # Project documentation
├── colabs/                  # Jupyter notebooks for analysis
├── codex/                   # Task specifications (legacy)
├── output/                  # Generated artifacts (reports, images)
├── docker-compose.yml       # Container orchestration
├── Dockerfile               # Application Docker image
├── pyproject.toml           # Project dependencies (UV)
└── README.md                # Main documentation
```

---

##  Main Directories

### 1. **`backend/`** - Application Core
Contains all business logic, FastAPI API, and data processing.

#### Internal Structure:
```
backend/
├── __init__.py              # Marks as Python package
├── app.py                   # FastAPI application factory
├── main.py                  # Entry point (can be removed or consolidated)
├── database.py              # Database connection settings
├── security.py              # Authentication and JWT
├── settings.py              # Environment variables and config
├── alembic.ini              # Alembic configuration (migrations)
├── README.md                # Backend-specific documentation
│
├── core/                    # Shared models and schemas
│   ├── __init__.py
│   ├── models.py            # SQLAlchemy ORM (PostgreSQL tables)
│   └── schemas.py           # Pydantic schemas (validation)
│
├── migrations/              # Database versioning (Alembic)
│   ├── env.py               # Environment script
│   ├── README                
│   ├── script.py.mako       # Migration template
│   └── versions/            # Applied migration history
│
├── routes/                  # API endpoints (by domain)
│   ├── __init__.py
│   ├── auth.py              # Login, signup, JWT
│   ├── criticidade.py       # Criticality ranking
│   ├── dist.py              # Distribution utilities
│   ├── etl.py               # ETL (ANEEL data extraction)
│   ├── pipeline.py          # Pipeline orchestration
│   ├── pt_and_pnt.py        # Technical/non-technical losses
│   ├── tam.py               # Medium voltage extension
│   └── users.py             # User management
│
├── schemas/                 # Additional Pydantic schemas
│   └── __init__.py
│
├── services/                # Business logic (separate from routes)
│   ├── calculate_pt_and_pnt.py      # Loss calculation
│   ├── calculate_sam.py             # SAM calculation
│   ├── calculo_tam.py               # TAM calculation
│   ├── criticidade.py               # Criticality logic
│   ├── distribuidoras.py            # Distribution management
│   ├── etl_download.py              # ANEEL data download
│   ├── pipeline_trigger.py          # Pipeline triggering
│   ├── render_criticidade.py        # Visualization generation
│   ├── render_tam.py                # TAM chart generation
│   ├── report.py                    # Report generation
│   └── render_pt_and_pnt.py         # PT/PNT chart generation
│
├── tasks/                   # Celery tasks (async processing)
│   ├── __init__.py
│   ├── celery_app.py        # Celery + Redis configuration
│   ├── task_calculate_pt_pnt.py     # Task: PT/PNT calculation
│   ├── task_calculate_sam.py        # Task: SAM calculation
│   ├── task_cleanup_files.py        # Task: File cleanup
│   ├── task_criticidade.py          # Task: Criticality
│   ├── task_descompact_gdb.py       # Task: GDB decompression
│   ├── task_download_gdb.py         # Task: GDB download
│   ├── task_load_dec_fec.py         # Task: Load indicators
│   ├── task_pipeline_error.py       # Task: Error handling
│   ├── task_process_layers.py       # Task: Process geographic layers
│   ├── task_render_criticidade.py   # Task: Render criticality
│   ├── task_render_pt_and_pnt.py    # Task: Render PT/PNT
│   ├── task_render_sam.py           # Task: Render SAM
│   ├── task_render_tam.py           # Task: Render TAM
│   ├── task_report.py               # Task: Generate report
│   └── task_tam.py                  # Task: TAM
│
├── tests/                   # Unit and integration tests
│   ├── __init__.py
│   ├── conftest.py          # Global pytest fixtures
│   ├── test_app.py          # App tests
│   ├── test_auth.py         # Authentication tests
│   ├── test_calculate_pt_and_pnt.py # PT/PNT tests
│   ├── test_criticidade.py  # Criticality tests
│   ├── test_db.py           # Database tests
│   ├── test_distribuidoras_service.py
│   ├── test_distributors.py
│   ├── test_route_etl.py
│   └── ... (other tests)
│
├── email/                   # Email notifications
│   └── envio_email.py       # SMTP configuration
│
├── scripts/                 # Utility scripts (non-Celery tasks)
│   ├── busca_id_name.py     # Search distributor ID/name
│   ├── pipeline_loop.py     # Pipeline loop (debug?)
│   ├── tam_from_mongo.py    # TAM extraction from MongoDB
│   └── resources_aneel.json # Static ANEEL data
│
└── docs/                    # Backend technical documentation
    ├── celery_app.md        # Celery guide
    ├── celery_redis.md      # Redis configuration
    ├── estrutura_basica.md  # Basic structure
    ├── guia_instalação.md   # Installation guide
    ├── pipeline_trigger_service_di.md
    ├── sessao_mapa_calor_score.md
    └── (other documentation)
```

**Purpose**: REST API implementation, data processing, and business logic.

**Technologies**: FastAPI, SQLAlchemy, Celery, MongoDB, PostgreSQL, GeoPandas.

---

### 2. **`frontend/`** - User Interface
HTML/CSS files for the web interface.

```
frontend/
├── hello.html               # Home page
├── login.html               # Login screen
├── profile.html             # Profile management
├── register.html            # Account creation
├── style.css                # Global CSS styles
└── assets/                  # Additional resources
    └── (images, icons, fonts)
```

**Purpose**: Web interface for user interaction.

**Note**: Vue.js is mentioned in README but no Vue files are present. Possible future migration.

---

### 3. **`docs/`** - Project Documentation
Central documentation hub for reference and onboarding.

```
docs/
├── PROJECT_STRUCTURE.md     # This file
├── guides/                  # Usage guides
│   ├── user-guide.md        # User manual
│   ├── application-manual.md # Technical manual
│   ├── pages-structure.md   # Page structure
│   └── (other guides)
├── patterns/                # Design and code patterns
│   └── (pattern documents)
├── process/                 # Process documentation
│   ├── requirements.md      # Project requirements
│   ├── sprints-backlog/
│   │   ├── sprint-1.md      # Sprint 1 (03/16 - 04/05)
│   │   ├── sprint-2.md      # Sprint 2 (04/13 - 05/03)
│   │   └── sprint-3.md      # Sprint 3 (05/11 - 05/31)
│   └── (other processes)
└── img/                     # Documentation images
    ├── logo-pokemon.png
    ├── home-page.png
    ├── profile.png
    ├── logout.png
    └── (screenshots)
```

**Purpose**: Centralize documentation, requirements, and manuals.

**Maintenance**: Update each sprint with new images and processes.

---

### 4. **`colabs/`** - Jupyter Notebooks for Analysis
Interactive notebooks for exploration and PoC.

```
colabs/
├── Criticality_Score.ipynb      # Criticality analysis
├── DEC.ipynb                    # DEC analysis
├── Heatmap.ipynb                # Heatmap generation
├── PT_And_PNT_Per_Set.ipynb     # PT/PNT analysis with charts
├── PT_And_PNT_Per_Set_Without_Graph.ipynb
├── SAM_Calculation.ipynb        # SAM calculation
├── TAM_Calculation.ipynb        # TAM calculation
└── notebooks_poc.md             # Notebooks index
```

**Purpose**: Algorithm prototyping and validation before production.

**Tool**: Google Colab (notebook + cloud environment).

---

### 5. **`codex/`** - Task Specifications (Legacy)
Documentation of executed tasks (possible code migration).

```
codex/
├── etl-ctmt-extracao.md     # CTMT ETL
├── task_cnpj.md
├── task_ctmt.md
├── task_listagem_dist.md    # Distribution listing
├── task_pipeline_trigger.md # Pipeline triggering
├── task_report.md           # Report generation
├── task_salvar_ctmt.md
├── task_salvar.md
└── task_ssdmt.md
```

**Purpose**: Task documentation (can be consolidated in backend/docs/).

**Status**: Can be discontinued if integrated in docs/process.

---

### 6. **`output/`** - Generated Artifacts
Files generated by the application (reports, images, etc).

```
output/
├── images/                  # Generated images (heatmaps, charts)
│   └── (PNG, SVG, etc)
└── reports/                 # Generated PDF reports
    └── (PDF files)
```

**Purpose**: Store application-generated outputs.

**Note**: Mapped as Docker volume (`./output:/app/output`).

---

### 7. **Configuration Files (Root)**

```
FATEC-API-6-SEMESTRE/
├── docker-compose.yml       # Service orchestration
│                            # - api (FastAPI)
│                            # - worker (Celery)
│                            # - redis (message broker)
│                            # - db (PostgreSQL)
│                            # - mongodb (NoSQL)
│                            # - frontend (Nginx)
│                            # - mongo-express (MongoDB Admin)
│
├── Dockerfile               # Application Docker image
│                            # Python 3.14 + GDAL + dependencies
│
├── pyproject.toml           # UV manager + dependencies
│                            # [project] = main dependencies
│                            # [dependency-groups] = dev/test
│                            # [tool.*] = ruff/pytest/taskipy config
│
└── README.md                # Main project documentation
                            # Challenge, solution, sprint, technologies, team
```

---

## 🔄 Main Data Flow

```
[Frontend HTML/CSS]
        ↓
[FastAPI Routes] ──→ [Services] ──→ [PostgreSQL + MongoDB]
        ↓
[Celery Tasks] ←── [Redis Broker] ←── [Worker Process]
        ↓
[PDF Reports + Images] ──→ [/output/]
```

---

## 📋 Maintenance Rules

### Adding New Features
1. **Create route** in `backend/routes/<domain>.py`
2. **Implement service** in `backend/services/<domain>.py`
3. **Add schema** in `backend/schemas/` or `backend/core/schemas.py`
4. **Create tests** in `backend/tests/test_<domain>.py`
5. **If async**: Create task in `backend/tasks/task_<domain>.py`
6. **Document** in `docs/guides/` or `docs/process/`

### Database Changes
1. Modify `backend/core/models.py`
2. Run: `alembic revision --autogenerate -m "description"`
3. Review migration in `backend/migrations/versions/`
4. Run: `alembic upgrade head`

### Adding Dependencies
1. Update `pyproject.toml`
2. Run: `uv sync`
3. Include in Docker image if necessary

### Testing
```bash
# Locally
pytest --cov=. -vv

# Via taskipy
uv run taskipy test
```

### Linting & Formatting
```bash
uv run taskipy lint    # Ruff check
uv run taskipy format  # Ruff format
```

---

## 🚀 Running Locally

```bash
# Install dependencies
uv sync

# Run in development
uv run fastapi dev backend/app.py

# Run with Docker Compose (complete)
docker-compose up -d

# Celery Worker
uv run celery -A backend.tasks.celery_app worker --loglevel=info
```

---

## 📞 Quick References

| Resource | Location |
|----------|----------|
| API Docs (Swagger) | `http://localhost:8000/docs` |
| MongoDB Admin | `http://localhost:8081` |
| Tests | `backend/tests/` |
| Migrations | `backend/migrations/versions/` |
| Celery Tasks | `backend/tasks/` |
| Documentation | `docs/` |
| Env Config | `.env` (not versioned) |

---

## 📝 Maintenance Notes

- **GeoPandas/GDAL**: Requires libgdal-dev in Dockerfile (heavy compilation)
- **Celery**: Depends on Redis for message broker
- **PostgreSQL vs MongoDB**: PostgreSQL for structured data, MongoDB for flexibility
- **Migrations**: Always review auto-generated migrations before applying
- **Vue.js in README**: Not implemented; consider removing or implementing in future sprint

---

**Last update**: May/2026  
**Responsible**: Pokémon Team (FATEC)
