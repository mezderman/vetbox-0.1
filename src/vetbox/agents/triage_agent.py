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
    follow_up_question: str | None = None

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
            "You are a veterinary triage assistant. Generate follow-up questions for pet symptoms."
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

        # Find best matching rule based on current case
        best_rule = self.rule_engine.find_best_matching_rule(current_case)
        follow_up_question = None

        if best_rule:
            print("[Best Matching Rule]", best_rule.get('rule_code'), best_rule.get('rationale'))

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
            follow_up_question = "Based on the current symptoms, this appears to be a routine case. Please consult with a veterinarian."

        return TriageOutput(
            follow_up_question=follow_up_question
        )

