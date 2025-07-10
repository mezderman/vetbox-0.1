import os
import json
from pydantic import BaseModel
from pydantic_ai import Agent
from vetbox.agents.conditions_extractor_agent import ConditionsExtractorAgent
from vetbox.agents.follow_up_question_generator import FollowUpQuestionGenerator
from vetbox.models.case_data import CaseData
from vetbox.models.rule_engine import RuleEngine
from typing import Dict, Any, List, Optional, Tuple
from colorama import Fore, init

# Initialize colorama
init()

class TriageInput(BaseModel):
    symptoms: str

class TriageOutput(BaseModel):
    follow_up_question: Optional[str] = None
    rule_checking_logs: List[str] = []

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
        # Connect RuleEngine to TriageAgent for logging
        self.rule_engine.triage_agent = self
        self.follow_up_generator = FollowUpQuestionGenerator()
        # Track the current question context for precise condition extraction
        self.current_question_context = None
        # Track rule checking logs
        self.rule_checking_logs = []

    async def run_async(self, user_response: str) -> TriageOutput:
        # Reset rule checking logs for new request
        self.rule_checking_logs = []
        
        # Extract conditions from user response
        conditions_extractor_agent = ConditionsExtractorAgent()
        
        # Log user's response in blue
        print(f"{Fore.BLUE}[User Answer]{Fore.RESET}", user_response)
        
        # Pass the current question context to help with precise extraction
        conditions = await conditions_extractor_agent.run_async(
            question="What symptoms is your pet experiencing?",
            answer=user_response,
            question_context=self.current_question_context
        )
        print("[Conditions]", conditions)

        # Update case data with new conditions
        self.case_data.merge_extraction(conditions)
        current_case = self.case_data.to_dict()
        print(f"{Fore.GREEN}[Case Data]{Fore.RESET}", current_case)

        follow_up_question = None
        # Reset question context for the next iteration
        self.current_question_context = None

        # First, try to find a best matching rule (all conditions satisfied)
        best_rule = await self.rule_engine.find_best_matching_rule(current_case)
        if best_rule:
            print("[Best Matching Rule]", best_rule.get('rule_code'), best_rule.get('rationale'))
            
            # Check if there are still missing conditions (e.g., slot conditions)
            missing_conditions = await self.rule_engine.get_missing_conditions_async(best_rule, current_case)
            if missing_conditions:
                # Still has missing conditions - treat as candidate rule
                self.rule_checking_logs.append("[Status] Best matching rule found but has missing conditions")
                self.rule_checking_logs.append(f"[Candidate Rule] {best_rule.get('rule_code')} - {best_rule.get('rationale')}")
                next_condition = missing_conditions[0]
                self.rule_checking_logs.append(f"[Next Condition to Ask]\n{json.dumps(next_condition, indent=2)}")
                # Store the context for the next question
                self.current_question_context = next_condition
                # Generate follow-up question for the first missing condition
                follow_up_question = await self.follow_up_generator.run_async(
                    case_data=current_case,
                    missing_condition=next_condition
                )
                print("[Follow-up Question]", follow_up_question)
            else:
                # All conditions satisfied - we have a complete match
                priority = best_rule.get('priority', 'Routine')
                self.rule_checking_logs.append("[Status] Complete rule match found!")
                self.rule_checking_logs.append(f"[Matched Rule]\n{json.dumps(best_rule, indent=2)}")
                self.rule_checking_logs.append(f"[Case Data]\n{json.dumps(current_case, indent=2)}")
                
                # Provide clean triage recommendation without JSON
                follow_up_question = (
                    f"Based on your pet's symptoms, this appears to be a {priority.lower()} case.\n"
                    f"Matched rule: {best_rule.get('rule_code')} - {best_rule.get('rationale')}"
                )

        else:
            # No best matching rule found, but check for candidate rules
            print("[No Best Matching Rule] Checking candidate rules...")
            self.rule_checking_logs.append("[Status] No best matching rule found, checking candidate rules...")
            
            candidate_rules = await self.rule_engine.find_candidate_rules(current_case)
            
            if candidate_rules:
                # Use the highest priority candidate rule for follow-up questions
                candidate_rule = candidate_rules[0]  # Rules are sorted by priority
                print("[Candidate Rule]", candidate_rule.get('rule_code'), candidate_rule.get('rationale'))
                self.rule_checking_logs.append(f"[Candidate Rule] {candidate_rule.get('rule_code')} - {candidate_rule.get('rationale')}")
                self.rule_checking_logs.append(f"[Available Candidates] {len(candidate_rules)} rules with no definitive mismatches")
                
                # Find missing conditions to ask about
                missing_conditions = await self.rule_engine.get_missing_conditions_async(candidate_rule, current_case)
                if missing_conditions:
                    print("[Missing Conditions for Candidate Rule]", missing_conditions)
                    # Only show the next condition to ask about (not all missing conditions)
                    next_condition = missing_conditions[0]
                    self.rule_checking_logs.append(f"[Next Condition to Ask]\n{json.dumps(next_condition, indent=2)}")
                    # Store the context for the next question
                    self.current_question_context = next_condition
                    # Generate follow-up question for the first missing condition
                    follow_up_question = await self.follow_up_generator.run_async(
                        case_data=current_case,
                        missing_condition=next_condition
                    )
                    print("[Follow-up Question]", follow_up_question)
                else:
                    # This shouldn't happen, but handle it gracefully
                    follow_up_question = "Please provide more details about your pet's symptoms."
            else:
                # No matching rules at all
                self.rule_checking_logs.append("[Status] No viable candidate rules found. All rules have definitive mismatches.")
                follow_up_question = "Based on the current symptoms, this appears to be a routine case. Please consult with a veterinarian for a proper assessment."

        # Create output with collected logs
        output = TriageOutput(
            follow_up_question=follow_up_question,
            rule_checking_logs=self.rule_checking_logs
        )
        print("[Rule Checking Logs]", self.rule_checking_logs)  # Debug print
        return output
