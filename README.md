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

## Usage

You can use the TriageAgent in your code as follows:

```python
from vetbox.agents.triage_agent import TriageAgent, TriageInput

agent = TriageAgent()
result = agent.run(TriageInput(symptoms="chest pain"))
print(result)
```

## Testing

Run tests with pytest:
```sh
pytest tests/
``` 