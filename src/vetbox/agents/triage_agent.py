import os
from pydantic import BaseModel
from pydantic_ai import Agent
from vetbox.agents.conditions_extractor_agent import ConditionsExtractorAgent
from vetbox.models.case_data import CaseData
from vetbox.models.rule_engine import RuleEngine
from typing import Dict, Any, List

class TriageInput(BaseModel):
    symptoms: str

class TriageOutput(BaseModel):
    triage_level: str
    advice: str

class TriageAgent:
    def __init__(self, rules: List[Dict[str, Any]] = None, model: str = None):
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
        self.rule_engine = RuleEngine(rules or [])

    async def run_async(self, user_response: str) -> TriageOutput:
        # Extract conditions from user response
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
        
        # Update case data with new conditions
        self.case_data.merge_extraction(conditions)
        current_case = self.case_data.to_dict()
        print("[Case Data]", current_case)

        # Find best matching rule based on current case
        best_rule = self.rule_engine.find_best_matching_rule(current_case)
        if best_rule:
            print("[Best Matching Rule]", best_rule.get('rule_code'), best_rule.get('rationale'))
            # Use the rule's priority to determine triage level
            priority = best_rule.get('priority', 0)
            triage_level = "High" if priority >= 3 else "Medium" if priority >= 2 else "Low"
            advice = best_rule.get('rationale', "Please consult with a veterinarian.")
        else:
            triage_level = "Low"
            advice = "Based on the current symptoms, this appears to be a routine case. Please consult with a veterinarian."

        return TriageOutput(triage_level=triage_level, advice=advice)

