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

        follow_up_question = None

        # First, try to find a best matching rule (all conditions satisfied)
        best_rule = self.rule_engine.find_best_matching_rule(current_case)
        if best_rule:
            print("[Best Matching Rule]", best_rule.get('rule_code'), best_rule.get('rationale'))
            
            # Check if there are still missing conditions (e.g., slot conditions)
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
                # All conditions satisfied - provide triage recommendation
                priority = best_rule.get('priority', 'Routine')
                follow_up_question = f"Based on your pet's symptoms, this appears to be a {priority.lower()} case. I recommend: {best_rule.get('rationale')}. Please consult with a veterinarian."
                
        else:
            # No best matching rule found, but check for candidate rules
            print("[No Best Matching Rule] Checking candidate rules...")
            candidate_rules = self.rule_engine.find_candidate_rules(current_case)
            
            if candidate_rules:
                # Use the highest priority candidate rule for follow-up questions
                candidate_rule = candidate_rules[0]  # Rules are sorted by priority
                print("[Candidate Rule]", candidate_rule.get('rule_code'), candidate_rule.get('rationale'))
                
                # Find missing conditions to ask about
                missing_conditions = self.rule_engine.get_missing_conditions(candidate_rule, current_case)
                if missing_conditions:
                    print("[Missing Conditions for Candidate Rule]", missing_conditions)
                    # Generate follow-up question for the first missing condition
                    follow_up_question = await self.follow_up_generator.run_async(
                        case_data=current_case,
                        missing_condition=missing_conditions[0]
                    )
                    print("[Follow-up Question]", follow_up_question)
                else:
                    # This shouldn't happen, but handle it gracefully
                    follow_up_question = "Please provide more details about your pet's symptoms."
            else:
                # No matching rules at all
                follow_up_question = "Based on the current symptoms, this appears to be a routine case. Please consult with a veterinarian for a proper assessment."

        return TriageOutput(
            follow_up_question=follow_up_question
        )
