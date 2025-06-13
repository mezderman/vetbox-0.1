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