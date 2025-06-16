import os
from pydantic import BaseModel
from pydantic_ai import Agent
from vetbox.agents.conditions_extractor_agent import ConditionsExtractorAgent
from vetbox.agents.follow_up_question_generator import FollowUpQuestionGenerator
from vetbox.models.case_data import CaseData
from vetbox.models.rule_engine import RuleEngine
from typing import Dict, Any, List, Optional, Tuple

class TriageInput(BaseModel):
    symptoms: str

class TriageOutput(BaseModel):
    triage_level: str
    advice: str
    follow_up_question: Optional[str] = None

class TriageAgent:
    def __init__(self, rules: List[Dict[str, Any]] = None, model: str = None):
        model = 'openai:gpt-4o'
        # Priority mapping from string values to numeric levels
        self.priority_map = {
            "Emergency": 3,
            "Urgent": 2,
            "Routine": 1,
            "": 0  # Default priority
        }
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
        self.follow_up_generator = FollowUpQuestionGenerator()

    async def run_async(self, user_response: str) -> TriageOutput:
        # Extract conditions from user response
        conditions_extractor_agent = ConditionsExtractorAgent()
        conditions = await conditions_extractor_agent.run_async(
            question="What symptoms is your pet experiencing?",
            answer=user_response
        )
        print("[Conditions]", conditions)
        
        # Update case data with new conditions
        self.case_data.merge_extraction(conditions)
        current_case = self.case_data.to_dict()
        print("[Case Data]", current_case)

        # Find all candidate rules that match any of the current symptoms
        candidate_rules = self.rule_engine.find_candidate_rules(current_case)
        print("[Candidate Rules]", [
            {
                "code": rule.get('rule_code'),
                "priority": rule.get('priority'),
                "rationale": rule.get('rationale'),
                "missing": self.rule_engine.get_missing_conditions(rule, current_case)
            }
            for rule in candidate_rules
        ])

        # Find best matching rule based on current case
        best_rule = self.rule_engine.find_best_matching_rule(current_case)
        follow_up_question = None

        if best_rule:
            print("[Best Matching Rule]", best_rule.get('rule_code'), best_rule.get('rationale'))
            # Map string priority to numeric level
            priority_str = best_rule.get('priority', '')
            priority_level = self.priority_map.get(priority_str, 0)
            triage_level = "High" if priority_level >= 3 else "Medium" if priority_level >= 2 else "Low"
            advice = best_rule.get('rationale', "Please consult with a veterinarian.")

            # If the best rule has missing conditions, generate a follow-up question
            missing_conditions = self.rule_engine.get_missing_conditions(best_rule, current_case)
            if missing_conditions:
                print("[Missing Conditions for Best Rule]", missing_conditions)
                # Generate follow-up question for the first missing condition
                follow_up_question = await self.follow_up_generator.run_async(
                    case_data=current_case,
                    missing_condition=missing_conditions[0]
                )
                print("[Follow-up Question]", follow_up_question)
        else:
            triage_level = "Low"
            advice = "Based on the current symptoms, this appears to be a routine case. Please consult with a veterinarian."

        return TriageOutput(
            triage_level=triage_level,
            advice=advice,
            follow_up_question=follow_up_question
        )

