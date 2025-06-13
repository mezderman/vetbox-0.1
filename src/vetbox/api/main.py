from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.vetbox.agents.triage_agent import TriageAgent
from dotenv import load_dotenv
import os
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
    symptoms: str

class ChatResponse(BaseModel):
    triage_level: str
    advice: str

agent = TriageAgent()





@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    result = await agent.run_async(request.symptoms)
    return ChatResponse(
        triage_level=result.triage_level,
        advice=result.advice
    )
