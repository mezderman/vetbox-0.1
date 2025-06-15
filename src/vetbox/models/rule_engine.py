from typing import Dict, List, Optional, Any
from .case_data import CaseData
import json

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
    
    def find_candidate_rules(self, case_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:

        candidates = []
        for rule in self.rules:
            # Get all symptom conditions from the rule
            symptom_conditions = [
                cond for cond in rule.get('conditions', [])
                if cond.get('type') == 'symptom'
            ]
            
            # Check if any required symptom is present
            for condition in symptom_conditions:
                symptom_name = condition.get('symptom')
                if symptom_name in case_data:
                    symptom_data = case_data[symptom_name]
                    if symptom_data.get('present') is True:
                        candidates.append(rule)
                        break
        
        return candidates
    
    def get_missing_conditions(self, rule: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:

        missing = []
        for condition in rule.get('conditions', []):
            if not self._is_condition_satisfied(condition, case_data):
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
            symptom_data = case_data.get(parent_symptom, {})
            actual_value = symptom_data.get(slot_name)
            
            if actual_value is None:
                return False
                
            # Handle different operators
            if operator == 'equals':
                return actual_value == expected_value
            elif operator == 'contains':
                return expected_value in actual_value
            elif operator == 'greater_than':
                return float(actual_value) > float(expected_value)
            elif operator == 'less_than':
                return float(actual_value) < float(expected_value)
            
        return False
    
    def _is_symptom_present(self, symptom_name: str, case_data: Dict[str, Dict[str, Any]]) -> bool:

        symptom_data = case_data.get(symptom_name, {})
        return symptom_data.get('present', False) is True