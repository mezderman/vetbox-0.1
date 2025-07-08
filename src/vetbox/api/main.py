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

# Allow CORS for your React frontend (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Change to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    user_answer: str  # Expected request body: { "user_answer": "..." }

class ChatResponse(BaseModel):
    follow_up_question: str

# Initialize the agent with rules from the database
rule_engine = RuleEngine.get_all_rules()
agent = TriageAgent(rules=rule_engine.rules)

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    result = await agent.run_async(request.user_answer)
    return ChatResponse(
        follow_up_question=result.follow_up_question
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
