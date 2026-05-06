# Application Manual

This guide provides comprehensive instructions on set up, running, testing, and interacting with the application.

## 📋 Prerequisites

Before running the project, ensure you have the following installed on your system:
- **Docker** and **Docker Compose**: Required for running the application and databases in containers easily.
- **Python 3.14+** (if running locally): The project utilizes standard `pyproject.toml` configurations.
- **uv**: An extremely fast Python package manager (this project uses `uv`).

---

## 🚀 Running the Project (Docker - Recommended)

Running the project via Docker is the easiest method and ensures that all services (API, Celery Workers, Redis, Databases) start automatically with the correct configurations.

### 1. Build and Start the Services

To start the application, navigate to the project root in your terminal and run:

```bash
docker-compose up --build
```
*Tip: Add `-d` at the end to run it in detached (background) mode.*

### 2. Services Initialization

Once the containers are spinning up, you will see the following services:
- **db** (PostgreSQL) / **mongodb**
- **redis** (Message broker for Celery)
- **api** (FastAPI backend service)
- **worker** (Celery worker executing background tasks)

To stop the Docker containers, press `Ctrl+C` (if not detached) or run:

```bash
docker-compose down
```

---

## 💻 Running the Project Locally (Development)

If you wish to do active development, you may want to run the project Python environments natively on your machine.

### 1. Install Dependencies

We use standard packaging specifications configured via `pyproject.toml`, paired with `uv`:

```bash
# Using uv (recommended)
uv sync

# Or using standard pip
pip install -e "."
pip install -e ".[dev]"
```

### 2. Run Database Migrations

Apply the latest database migrations via Alembic. Ensure your database containers are running and `.env` is configured correctly:

```bash
uv run alembic upgrade head
```

### 3. Start the FastAPI Server

```bash
uv run fastapi dev backend/main.py
# OR
uv run uvicorn backend.main:app --reload --port 8000
```

### 4. Start the Celery Worker

Open a new terminal to start the background celery worker:

```bash
uv run celery -A backend.tasks.celery_app worker --loglevel=info
```

---

## 🌐 Accessing and Using the Application

### Backend API
Once the application is running, you can access the interactive documentation provided by FastAPI:

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

Use the Swagger UI to explore available endpoints, authenticate (if applicable), and trigger requests directly from your browser.

### Frontend Pages
Various raw HTML views are available inside the `frontend/` folder. You can serve them using a lightweight server:

```bash
cd frontend
python -m http.server 3000
```
Navigate to [http://localhost:3000/login.html](http://localhost:3000/login.html).

---

## 🧪 Testing the Project

This project uses `pytest` for running automated tests.

### Running Tests in Docker

If the services are running, execute tests inside the main API container:

```bash
docker-compose exec api pytest
```
*Note: TestContainers in python requires access to `docker.sock` to start containerized db environments to run tests.*

### Running Tests Locally

To run the test suite locally (uses `pytest` and `testcontainers` which will automatically handle spinning up disposable databases):

```bash
# Run all tests
uv run pytest

# Run tests with coverage report
uv run pytest --cov=backend

# Run tests for a specific suite
uv run pytest tests/test_app.py
```