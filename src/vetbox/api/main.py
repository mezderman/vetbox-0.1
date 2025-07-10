from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.vetbox.agents.triage_agent import TriageAgent
from dotenv import load_dotenv
import os
import logging
from vetbox.models.rule_engine import RuleEngine
import json as pyjson

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s'
)
# Reduce specific loggers' verbosity
logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('asyncio').setLevel(logging.ERROR)
logging.getLogger('openai').setLevel(logging.ERROR)

load_dotenv()
app = FastAPI()

# Allow CORS for your React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    user_answer: str

class ChatResponse(BaseModel):
    follow_up_question: str | None = None
    extracted_conditions: dict | None = None

# Initialize the agent with rules from the database
rule_engine = RuleEngine.get_all_rules()
agent = TriageAgent(rules=rule_engine.rules)

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        result = await agent.run_async(request.user_answer)
        # Get the extracted conditions from the agent's case data
        extracted_conditions = agent.case_data.to_dict()
        return ChatResponse(
            follow_up_question=result.follow_up_question,
            extracted_conditions=extracted_conditions
        )
    except Exception as e:
        return ChatResponse(
            follow_up_question=str(e),
            extracted_conditions=None
        )

@app.post("/clear")
async def clear_chat():
    """Clear the current chat session and start fresh."""
    global agent
    # Reinitialize the agent with fresh state
    agent = TriageAgent(rules=rule_engine.rules)
    return {
        "message": "Chat session cleared",
        "follow_up_question": "Hello! I'm your veterinary triage assistant. Please describe your pet's symptoms and I'll help assess the situation."
    }
