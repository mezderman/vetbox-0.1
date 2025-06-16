import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent

class FollowUpQuestionOutput(BaseModel):
    """Output model for follow-up question generation."""
    question: str

class FollowUpQuestionGenerator:
    def __init__(self, model: str = None):
        model = 'openai:gpt-4o'
        self.system_prompt = (
            """
            You are a veterinary triage assistant. Your job is to generate natural, clear follow-up questions 
            for pet owners based on the current case data and missing information needed.

            Given:
            1. The current case data (symptoms and their details)
            2. The specific missing information we need (a condition or slot value)

            Generate a clear, concise follow-up question that will help gather the missing information.

            Rules:
            - Be specific and direct in your questions
            - Reference the relevant symptom/condition in the question
            - For slots, ask about the specific attribute (frequency, severity, location, etc.)
            - Keep questions natural and conversational
            - Don't ask about information we already have
            - Format output as a simple string with just the question

            EXAMPLES:

            Case: {"vomiting": {"present": true}}
            Missing: {"type": "slot", "slot": "frequency", "parent_symptom": "vomiting"}
            → "How often has your pet been vomiting?"

            Case: {"hives": {"present": true}}
            Missing: {"type": "slot", "slot": "location", "parent_symptom": "hives"}
            → "Where on your pet's body are the hives located?"

            Case: {}
            Missing: {"type": "symptom", "symptom": "lethargic"}
            → "Has your pet been showing signs of lethargy or decreased energy?"

            Case: {"vomiting": {"present": true, "frequency": "daily"}}
            Missing: {"type": "slot", "slot": "cannot_hold_down", "parent_symptom": "vomiting"}
            → "Is your pet able to keep any food or water down when vomiting?"
            """
        )
        self.agent = Agent(
            model,
            output_type=FollowUpQuestionOutput,
            system_prompt=self.system_prompt,
        )

    async def run_async(self, case_data: Dict[str, Any], missing_condition: Dict[str, Any]) -> str:
        # Format the input data for the prompt
        prompt = f"""
            Current Case Data:
            {case_data}

            Missing Information:
            {missing_condition}
            """
        print("[FollowUpQuestionGenerator prompt]", prompt)
        result = await self.agent.run(prompt)
        return result.output.question

    # def run(self, case_data: Dict[str, Any], missing_condition: Dict[str, Any]) -> str:
    #     """Synchronous version of run_async."""
    #     prompt = f"""
    #         Current Case Data:
    #         {case_data}

    #         Missing Information:
    #         {missing_condition}
    #         """
    #     result = self.agent.run_sync(prompt)
    #     return result.output.question

    def generate(self, case_data: Dict[str, Any], missing_condition: Dict[str, Any]) -> str:
        return self.run_async(case_data, missing_condition) 