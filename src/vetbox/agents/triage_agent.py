import os
from pydantic import BaseModel
from pydantic_ai import Agent
from vetbox.agents.conditions_extractor_agent import ConditionsExtractorAgent

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


    async def run_async(self, user_response: str) -> TriageOutput:
        conditions_extractor_agent = ConditionsExtractorAgent()
        conditions = await conditions_extractor_agent.run_async("What are the symptoms?", user_response)
        print("[Conditions]", conditions)

        prompt = f"""
You are a medical triage assistant. Given the following symptoms, provide:
- triage_level: High, Medium, or Low
- advice: Short advice for the patient

Symptoms: {user_response}
"""
        result = await self.agent.run(prompt)
        return result.output

