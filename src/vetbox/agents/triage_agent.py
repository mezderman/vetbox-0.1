import os
from pydantic import BaseModel
from pydantic_ai import Agent
from vetbox.agents.conditions_extractor_agent import ConditionsExtractorAgent
from vetbox.models.case_data import CaseData
from typing import Dict, Any

class TriageInput(BaseModel):
    symptoms: str

class TriageOutput(BaseModel):
    triage_level: str
    advice: str

class TriageAgent:
    def __init__(self, model: str = None):
        model = 'openai:gpt-4o'
        self.system_prompt = (
            "You are a medical triage assistant. Given the following symptoms, provide:\n"
            "- triage_level: High, Medium, or Low\n"
            "- advice: Short advice for the patient"
        )
        self.agent = Agent(
            model,
            output_type=TriageOutput,
            system_prompt=self.system_prompt,
        )
        self.case_data = CaseData()

    async def run_async(self, user_response: str) -> TriageOutput:
        conditions_extractor_agent = ConditionsExtractorAgent()
        conditions = await conditions_extractor_agent.run_async(
            question="What symptoms is your pet experiencing?",
            answer=user_response
        )
        print("[Conditions]", conditions)
        
        # If conditions is empty but user_response contains symptom-like words, create a basic condition
        if not conditions and any(word in user_response.lower() for word in ['cough', 'vomit', 'fever', 'lethargic', 'hives']):
            symptom = user_response.lower().strip()
            conditions = {symptom: True}
            print("[Created basic condition]", conditions)
        
        self.case_data.merge_extraction(conditions)
        print("[Case Data]", self.case_data.to_dict())

        prompt = f"""
You are a medical triage assistant. Given the following symptoms, provide:
- triage_level: High, Medium, or Low
- advice: Short advice for the patient

Symptoms: {user_response}
"""
        result = await self.agent.run(prompt)
        return result.output

