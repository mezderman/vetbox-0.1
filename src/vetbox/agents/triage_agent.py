import os
from pydantic import BaseModel
from pydantic_ai import Agent

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

    def run(self, symptoms: str) -> TriageOutput:
        prompt = f"Symptoms: {symptoms}"
        result = self.agent.run_sync(prompt)
        return result.output

    async def run_async(self, symptoms: str) -> TriageOutput:
        prompt = f"""
You are a medical triage assistant. Given the following symptoms, provide:
- triage_level: High, Medium, or Low
- advice: Short advice for the patient

Symptoms: {symptoms}
"""
        result = await self.agent.run(prompt)
        return result.output

