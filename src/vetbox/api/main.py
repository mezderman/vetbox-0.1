from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.vetbox.agents.triage_agent import TriageAgent
from dotenv import load_dotenv
import os
import logging
# Add imports for DB access
from vetbox.db.database import SessionLocal
from vetbox.db.models import Rule, RuleCondition
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
    triage_level: str
    advice: str

def get_rules_from_db():
    """Load rules from the database and create a RuleEngine instance."""
    session = SessionLocal()
    rules = session.query(Rule).all()
    # Eager load conditions and related fields
    for rule in rules:
        rule.conditions
        for cond in rule.conditions:
            cond.symptom
            cond.slot_name
            cond.parent_symptom
    
    # Create RuleEngine instance from DB rules
    rule_engine = RuleEngine.from_db_rules(rules)
    session.close()
    return rule_engine.rules

# Initialize the agent with rules
rules = get_rules_from_db()
agent = TriageAgent(rules=rules)

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    result = await agent.run_async(request.user_answer)
    return ChatResponse(
        triage_level=result.triage_level,
        advice=result.advice
    )
