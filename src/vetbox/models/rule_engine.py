from typing import Dict, List, Optional, Any
from .case_data import CaseData
import json
from vetbox.db.database import SessionLocal
from vetbox.db.models import Rule
from pydantic_ai import Agent

class RuleEngine:
    """
    Engine for processing and matching veterinary triage rules.
    Handles rule loading, serialization, and matching against case data.
    """

    def __init__(self, rules: List[Dict[str, Any]]):
        """Initialize the rule engine with a list of rules."""
        self.rules = rules
        # Sort rules by priority (assuming higher priority number = more urgent)
        self.rules.sort(key=lambda x: x.get('priority', 0), reverse=True)
        
        # Initialize semantic validator agent
        self.semantic_validator = Agent(
            'openai:gpt-4o',
            system_prompt="""
            You are a semantic validator for veterinary triage conditions.
            
            Given an actual value and a list of expected values, determine if the actual value 
            semantically satisfies any of the expected conditions.
            
            Consider:
            - Synonyms and similar meanings
            - Frequency expressions (e.g., "few times" vs "more than a few times")
            - Medical terminology equivalents
            - Common pet owner language vs clinical terms
            
            Respond with ONLY "true" or "false" - no explanation needed.
            
            Examples:
            - Actual: "few_times", Expected: ["more than a few times", "frequent"] → false
            - Actual: "frequent", Expected: ["more than a few times", "frequent"] → true  
            - Actual: "multiple times daily", Expected: ["frequent", "multiple times"] → true
            - Actual: "hourly", Expected: ["every hour", "hourly"] → true
            - Actual: "neck area", Expected: ["neck", "throat"] → true
            """
        )
    
    @staticmethod
    def serialize_condition(condition) -> Dict[str, Any]:

        if condition.condition_type == "symptom":
            return {
                "type": "symptom",
                "symptom": condition.symptom.code if condition.symptom else None
            }
        elif condition.condition_type == "slot":
            # Parse value as JSON if possible
            try:
                value = json.loads(condition.value) if condition.value and condition.value.startswith("[") else condition.value
            except Exception:
                value = condition.value
            return {
                "type": "slot",
                "slot": condition.slot_name.code if condition.slot_name else None,
                "operator": condition.operator,
                "value": value,
                "parent_symptom": condition.parent_symptom.code if condition.parent_symptom else None
            }
        return {}

    @staticmethod
    def serialize_rule(rule) -> Dict[str, Any]:

        return {
            "id": rule.id,
            "rule_code": rule.rule_code,
            "priority": rule.priority,
            "rationale": rule.rationale,
            "conditions": [RuleEngine.serialize_condition(cond) for cond in rule.conditions]
        }

    @classmethod
    def from_db_rules(cls, db_rules: List[Any]) -> 'RuleEngine':
 
        serialized_rules = [cls.serialize_rule(rule) for rule in db_rules]
        return cls(serialized_rules)
    
    @classmethod
    def get_all_rules(cls) -> 'RuleEngine':
        """
        Load all rules from the database and return a RuleEngine instance.
        Handles eager loading of all related data (conditions, symptoms, slots).
        """
        session = SessionLocal()
        try:
            rules = session.query(Rule).all()
            # Eager load conditions and related fields
            for rule in rules:
                rule.conditions
                for cond in rule.conditions:
                    cond.symptom
                    cond.slot_name
                    cond.parent_symptom
            return cls.from_db_rules(rules)
        finally:
            session.close()
    
    def find_candidate_rules(self, case_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find rules where at least one required symptom is present in the case data."""
        candidates = []
        # Convert case_data keys to lowercase for case-insensitive matching
        case_data_lower = {k.lower(): v for k, v in case_data.items()}
        
        print("[DEBUG] Case data (lowercase):", case_data_lower)
        
        for rule in self.rules:
            # Get all symptom conditions from the rule
            symptom_conditions = [
                cond for cond in rule.get('conditions', [])
                if cond.get('type') == 'symptom'
            ]
            
            print(f"[DEBUG] Checking rule {rule.get('rule_code')} with conditions:", 
                  [cond.get('symptom') for cond in symptom_conditions])
            
            # Check if any required symptom is present
            for condition in symptom_conditions:
                symptom_name = condition.get('symptom')
                if symptom_name:  # Add null check
                    symptom_name_lower = symptom_name.lower()
                    print(f"[DEBUG] Checking symptom: {symptom_name_lower}")
                    if symptom_name_lower in case_data_lower:
                        symptom_data = case_data_lower[symptom_name_lower]
                        if symptom_data.get('present') is True:
                            print(f"[DEBUG] Found matching rule: {rule.get('rule_code')}")
                            candidates.append(rule)
                            break
        
        return candidates
    
    def get_missing_conditions(self, rule: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:

        missing = []
        for condition in rule.get('conditions', []):
            if not self._is_condition_satisfied(condition, case_data):
                missing.append(condition)
        return missing

    async def get_missing_conditions_async(self, rule: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Async version of get_missing_conditions that supports semantic validation."""
        missing = []
        for condition in rule.get('conditions', []):
            if not await self._is_condition_satisfied_async(condition, case_data):
                missing.append(condition)
        return missing
    
    def find_best_matching_rule(self, case_data: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:

        # Rules are already sorted by priority
        for rule in self.rules:
            # Check if all required symptoms are present
            symptoms_satisfied = True
            for condition in rule.get('conditions', []):
                if condition.get('type') == 'symptom':
                    symptom_name = condition.get('symptom')
                    if not self._is_symptom_present(symptom_name, case_data):
                        symptoms_satisfied = False
                        break
            
            if symptoms_satisfied:
                return rule
        
        return None
    
    def is_rule_satisfied(self, rule: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:

        return len(self.get_missing_conditions(rule, case_data)) == 0
    
    def get_next_missing_condition(self, rule: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:

        missing = self.get_missing_conditions(rule, case_data)
        # Prioritize symptom conditions over slot conditions
        symptom_conditions = [c for c in missing if c.get('type') == 'symptom']
        if symptom_conditions:
            return symptom_conditions[0]
        return missing[0] if missing else None
    
    def _is_condition_satisfied(self, condition: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:

        condition_type = condition.get('type')
        
        if condition_type == 'symptom':
            symptom_name = condition.get('symptom')
            return self._is_symptom_present(symptom_name, case_data)
            
        elif condition_type == 'slot':
            parent_symptom = condition.get('parent_symptom')
            slot_name = condition.get('slot')
            operator = condition.get('operator')
            expected_value = condition.get('value')
            
            # First check if parent symptom exists and is present
            if not self._is_symptom_present(parent_symptom, case_data):
                return False
                
            # Then check if slot exists and matches
            # Rules use UPPERCASE for symptoms/slots, case data uses lowercase symptoms + UPPERCASE slots
            case_data_lower = {k.lower(): v for k, v in case_data.items()}
            parent_symptom_lower = parent_symptom.lower() if parent_symptom else ""
            slot_name_upper = slot_name.upper() if slot_name else ""
            
            symptom_data = case_data_lower.get(parent_symptom_lower, {})
            actual_value = symptom_data.get(slot_name_upper)
            
            if actual_value is None:
                return False
                
            print(f"[DEBUG] Checking slot condition: {slot_name} = '{actual_value}' against expected '{expected_value}' with operator '{operator}'")
                
            # Handle different operators (sync version - only exact matching)
            if operator == '==' or operator == 'equals':
                return self._exact_match_condition(actual_value, expected_value)
            elif operator == 'contains':
                return expected_value in actual_value
            elif operator == 'greater_than':
                return float(actual_value) > float(expected_value)
            elif operator == 'less_than':
                return float(actual_value) < float(expected_value)
            
        return False
    
    def _is_symptom_present(self, symptom_name: str, case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if a symptom is present in the case data (case-insensitive)."""
        if not symptom_name:  # Add null check
            return False
        # Convert both the symptom name and case data keys to lowercase
        symptom_name_lower = symptom_name.lower()
        case_data_lower = {k.lower(): v for k, v in case_data.items()}
        symptom_data = case_data_lower.get(symptom_name_lower, {})
        return symptom_data.get('present', False) is True

    async def _semantic_validate_condition(self, actual_value: str, expected_values: List[str]) -> bool:
        """
        Use LLM to semantically validate if actual_value satisfies any of the expected_values.
        """
        try:
            prompt = f"Actual: \"{actual_value}\", Expected: {expected_values}"
            result = await self.semantic_validator.run(prompt)
            response = result.output.strip().lower()
            return response == "true"
        except Exception as e:
            print(f"[DEBUG] Semantic validation failed: {e}")
            # Fallback to exact matching
            return actual_value in expected_values

    def _exact_match_condition(self, actual_value: Any, expected_value: Any) -> bool:
        """Check if condition is satisfied using exact matching."""
        if isinstance(expected_value, list):
            return actual_value in expected_value
        else:
            return actual_value == expected_value

    async def _is_condition_satisfied_async(self, condition: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Async version of _is_condition_satisfied that supports semantic validation."""
        condition_type = condition.get('type')
        
        if condition_type == 'symptom':
            symptom_name = condition.get('symptom')
            return self._is_symptom_present(symptom_name, case_data)
            
        elif condition_type == 'slot':
            parent_symptom = condition.get('parent_symptom')
            slot_name = condition.get('slot')
            operator = condition.get('operator')
            expected_value = condition.get('value')
            
            # First check if parent symptom exists and is present
            if not self._is_symptom_present(parent_symptom, case_data):
                return False
                
            # Then check if slot exists and matches
            # Rules use UPPERCASE for symptoms/slots, case data uses lowercase symptoms + UPPERCASE slots
            case_data_lower = {k.lower(): v for k, v in case_data.items()}
            parent_symptom_lower = parent_symptom.lower() if parent_symptom else ""
            slot_name_upper = slot_name.upper() if slot_name else ""
            
            symptom_data = case_data_lower.get(parent_symptom_lower, {})
            actual_value = symptom_data.get(slot_name_upper)
            
            if actual_value is None:
                return False
                
            print(f"[DEBUG] Checking slot condition: {slot_name} = '{actual_value}' against expected '{expected_value}' with operator '{operator}'")
                
            # Handle different operators
            if operator == '==' or operator == 'equals':
                # First try exact matching
                if self._exact_match_condition(actual_value, expected_value):
                    print(f"[DEBUG] Exact match successful")
                    return True
                
                # If exact match fails and we have a list of expected values, try semantic validation
                if isinstance(expected_value, list):
                    print(f"[DEBUG] Exact match failed, trying semantic validation...")
                    is_semantic_match = await self._semantic_validate_condition(str(actual_value), [str(v) for v in expected_value])
                    print(f"[DEBUG] Semantic validation result: {is_semantic_match}")
                    return is_semantic_match
                
                return False
                
            elif operator == 'contains':
                return expected_value in actual_value
            elif operator == 'greater_than':
                return float(actual_value) > float(expected_value)
            elif operator == 'less_than':
                return float(actual_value) < float(expected_value)
            
        return False
