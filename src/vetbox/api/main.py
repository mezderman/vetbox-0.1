from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.vetbox.agents.triage_agent import TriageAgent
from dotenv import load_dotenv
import os
# Add imports for DB access
from vetbox.db.database import SessionLocal
from vetbox.db.models import Rule, RuleCondition
import json as pyjson

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

agent = TriageAgent()


def serialize_rule(rule: Rule):
    # Serialize a Rule and its conditions to match the test data format
    return {
        "id": rule.id,
        "rule_code": rule.rule_code,
        "priority": rule.priority,
        "rationale": rule.rationale,
        "conditions": [serialize_condition(cond) for cond in rule.conditions]
    }

def serialize_condition(cond: RuleCondition):
    if cond.condition_type == "symptom":
        return {
            "type": "symptom",
            "symptom": cond.symptom.code if cond.symptom else None
        }
    elif cond.condition_type == "slot":
        # Parse value as JSON if possible
        import json
        try:
            value = json.loads(cond.value) if cond.value and cond.value.startswith("[") else cond.value
        except Exception:
            value = cond.value
        return {
            "type": "slot",
            "slot": cond.slot_name.code if cond.slot_name else None,
            "operator": cond.operator,
            "value": value,
            "parent_symptom": cond.parent_symptom.code if cond.parent_symptom else None
        }
    else:
        return {}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # Query all rules and log them as JSON
    
    session = SessionLocal()
    rules = session.query(Rule).all()
    # Eager load conditions and related fields
    for rule in rules:
        rule.conditions
        for cond in rule.conditions:
            cond.symptom
            cond.slot_name
            cond.parent_symptom
    rules_json = [serialize_rule(rule) for rule in rules]
    session.close()
    print("[Rules in DB]", pyjson.dumps(rules_json, indent=2))

    # Call the triage agent as before
    result = await agent.run_async(request.user_answer)
    return ChatResponse(
        triage_level=result.triage_level,
        advice=result.advice
    )
