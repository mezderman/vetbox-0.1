# Vetbox TriageAgent Skeleton

This project demonstrates a minimal Pydantic AI agent application featuring a single agent called `TriageAgent`.

## Project Structure

```
vetbox-0.1/
├── src/
│   └── vetbox/
│       ├── __init__.py
│       └── agents/
│           ├── __init__.py
│           └── triage_agent.py
├── tests/
│   └── test_triage_agent.py
├── requirements.txt
├── README.md
├── .venv/
```

## Setup

1. Create and activate a virtual environment (if not already done):
   ```sh
   uv venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```sh
   uv pip install -r requirements.txt
   ```

## Running the Backend (FastAPI)

1. Make sure your virtual environment is activated:
   ```sh
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   # or
   uv pip install -r requirements.txt
   ```
3. Set your OpenAI API key in a `.env` file in the project root:
   ```env
   OPENAI_API_KEY=sk-...
   PYDANTIC_AI_MODEL=openai:gpt-4o
   ```
4. Start the backend server from the project root:
   ```sh
   PYTHONPATH=src uvicorn vetbox.api.main:app --reload
   # or with uv
   PYTHONPATH=src uv run -m uvicorn vetbox.api.main:app --reload
   ```
   The API will be available at http://localhost:8000

## Running the Frontend (React)

1. If you haven't already, create the React app:
   ```sh
   npx create-react-app frontend --template typescript
   ```
2. Go into the frontend directory:
   ```sh
   cd frontend
   ```
3. Start the React development server:
   ```sh
   npm start
   ```
   The frontend will be available at http://localhost:3000

## Usage
- The React app will POST user input to the `/chat` endpoint on the FastAPI backend.
- Make sure both servers are running for full-stack functionality.

## Testing

Run tests with pytest:
```sh
pytest tests/
```

## Database Setup & Initialization

### 1. Start the Database (Postgres via Docker)

If you haven't already, start the Postgres database using Docker Compose:

```bash
docker-compose up -d
```

This will launch a Postgres instance as defined in your `docker-compose.yml`.

### 2. Initialize Database Tables

Run the table creation script from your project root:

```bash
PYTHONPATH=src python scripts/create_tables.py
```

This will create all tables in the database according to your SQLAlchemy models.

### 3. Populate Test Data

Make sure your test data file exists at `data/rules.json`.

Run the population script:

```bash
PYTHONPATH=src python scripts/populate_test_data.py
```

This will insert rules and related data into the database, skipping any rules that already exist.

---

**Troubleshooting:**
- Ensure Docker is running and the Postgres container is healthy.
- If you change your database connection settings, update the `DATABASE_URL` in your `.env` file.
- If you modify your models, re-run the table creation script. 