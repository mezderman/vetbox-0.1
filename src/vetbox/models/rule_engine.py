from typing import Dict, List, Optional, Any
import json
from .case_data import CaseData
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
            # Check if this uses the new OR logic (symptom_ids array)
            if condition.symptom_ids and len(condition.symptom_ids) > 0:
                # Load symptom codes from the database for the IDs
                from vetbox.db.database import SessionLocal
                from vetbox.db.models import Symptom
                
                session = SessionLocal()
                try:
                    symptoms = session.query(Symptom).filter(Symptom.id.in_(condition.symptom_ids)).all()
                    symptom_codes = [s.code for s in symptoms]
                    return {
                        "type": "symptom",
                        "symptom": symptom_codes,  # Array for OR logic
                        "logic_type": condition.logic_type or "OR"
                    }
                finally:
                    session.close()
            else:
                # Legacy single symptom
                return {
                    "type": "symptom",
                    "symptom": [condition.symptom.code] if condition.symptom else None  # Convert to array for consistency
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
        elif condition.condition_type == "attribute":
            # Parse value as JSON if possible
            try:
                value = json.loads(condition.value) if condition.value and condition.value.startswith("[") else condition.value
            except Exception:
                value = condition.value
            return {
                "type": "attribute",
                "attribute": condition.attribute.code if condition.attribute else None,
                "operator": condition.operator,
                "value": value
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
                    cond.attribute
                    cond.parent_symptom
            return cls.from_db_rules(rules)
        finally:
            session.close()
    
    def find_candidate_rules(self, case_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find rules where some symptoms match and no conditions are explicitly violated."""
        candidates = []
        
        for rule in self.rules:
            # Skip rule if any condition is explicitly violated
            if self._rule_has_violated_conditions(rule, case_data):
                continue
                
            # Include rule if it has any matching symptoms
            if self._rule_has_matching_symptoms(rule, case_data):
                candidates.append(rule)
        
        return candidates
    
    def _rule_has_violated_conditions(self, rule: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if rule has any conditions that are explicitly violated by case data."""
        for condition in rule.get('conditions', []):
            if self._is_condition_violated(condition, case_data):
                return True
        return False
    
    def _is_condition_violated(self, condition: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if a specific condition is violated (explicitly false or doesn't match)."""
        condition_type = condition.get('type')
        
        if condition_type == 'symptom':
            return self._is_symptom_condition_violated(condition, case_data)
        elif condition_type == 'attribute':
            return self._is_attribute_condition_violated(condition, case_data)
        
        return False
    
    def _is_symptom_condition_violated(self, condition: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if symptom condition is explicitly violated."""
        symptom_names = condition.get('symptom', [])
        if not isinstance(symptom_names, list):
            symptom_names = [symptom_names]
        
        case_data_lower = {k.lower(): v for k, v in case_data.items()}
        
        for symptom_name in symptom_names:
            if symptom_name:
                symptom_data = case_data_lower.get(symptom_name.lower(), {})
                if symptom_data.get('present') is False:
                    return True
        return False
    
    def _is_attribute_condition_violated(self, condition: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if attribute condition is violated (we have the attribute but it doesn't match)."""
        attribute_name = condition.get('attribute')
        operator = condition.get('operator')
        expected_value = condition.get('value')
        
        # Get actual attribute value (case insensitive)
        patient_data = case_data.get('patient', {})
        actual_value = None
        for key, value in patient_data.items():
            if key.upper() == attribute_name.upper():
                actual_value = value
                break
        
        # Only check violation if we have the attribute value
        if actual_value is None:
            return False
        
        # Special handling for age comparisons
        if attribute_name.upper() == 'AGE':
            actual_age = self._normalize_age_value(actual_value)
            expected_age = self._normalize_age_value(expected_value)
            
            if operator == '<' and actual_age >= expected_age:
                return True
            elif operator == '>' and actual_age <= expected_age:
                return True
            elif operator == '==' and actual_age != expected_age:
                return True
        
        return False
    
    def _rule_has_matching_symptoms(self, rule: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if rule has any symptoms that match the case data."""
        symptom_conditions = [
            cond for cond in rule.get('conditions', [])
            if cond.get('type') == 'symptom'
        ]
        
        for condition in symptom_conditions:
            symptom_names = condition.get('symptom')
            if symptom_names and self._is_symptom_present(symptom_names, case_data):
                return True
        
        return False
    
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
        """Find the highest priority rule where all conditions are satisfied."""
        # Rules are already sorted by priority
        for rule in self.rules:
            # Check if all conditions are satisfied
            all_conditions_satisfied = True
            for condition in rule.get('conditions', []):
                if not self._is_condition_satisfied(condition, case_data):
                    all_conditions_satisfied = False
                    break
            
            if all_conditions_satisfied:
                print(f"\n[DEBUG] Found matching rule: {rule.get('rule_code')}")
                print(f"[DEBUG] Case data that matched:")
                print(json.dumps(case_data, indent=2))
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
    
    def _normalize_age_value(self, value: Any) -> float:
        """
        Normalize age values to a common format (numeric years).
        Handles both numeric values and strings with units.
        """
        if isinstance(value, (int, float)):
            return float(value)
        
        # Handle string values like "1 year" or "1 years"
        try:
            if isinstance(value, str):
                # Extract numeric part
                numeric_part = float(''.join(c for c in value if c.isdigit() or c == '.'))
                # For now we assume all ages in rules are in years
                return numeric_part
            elif isinstance(value, list):
                # If it's a list (like from rules.json), take first value
                return self._normalize_age_value(value[0])
        except (ValueError, IndexError):
            print(f"[DEBUG] Failed to normalize age value: {value}")
            return 0
        return 0

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
                
        elif condition_type == 'attribute':
            attribute_name = condition.get('attribute')
            operator = condition.get('operator')
            expected_value = condition.get('value')
            
            # Get patient/case attributes
            patient_data = case_data.get('patient', {})
            # Handle case insensitive attribute lookup
            actual_value = None
            for key, value in patient_data.items():
                if key.upper() == attribute_name.upper():
                    actual_value = value
                    break
            
            if actual_value is None:
                return False
                
            print(f"[DEBUG] Checking attribute condition: {attribute_name} = '{actual_value}' against expected '{expected_value}' with operator '{operator}'")
            
            # Special handling for age comparisons
            if attribute_name.upper() == 'AGE':
                actual_age = self._normalize_age_value(actual_value)
                expected_age = self._normalize_age_value(expected_value)
                
                print(f"[DEBUG] Comparing ages: {actual_age} {operator} {expected_age}")
                
                if operator == '==' or operator == 'equals':
                    return actual_age == expected_age
                elif operator == 'contains':
                    return str(expected_age) in str(actual_age)
                elif operator == 'greater_than' or operator == '>':
                    return actual_age > expected_age
                elif operator == 'less_than' or operator == '<':
                    return actual_age < expected_age
            else:
                # Handle non-age attributes
                if operator == '==' or operator == 'equals':
                    return self._exact_match_condition(actual_value, expected_value)
                elif operator == 'contains':
                    return expected_value in actual_value
                elif operator == 'greater_than':
                    return float(actual_value) > float(expected_value)
                elif operator == 'less_than':
                    return float(actual_value) < float(expected_value)
            
        return False
    
    def _is_symptom_present(self, symptom_names, case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if any symptom in the array is present in the case data (case-insensitive)."""
        if not symptom_names:  # Add null check
            return False
            
        # Always expect an array of symptoms (OR logic)
        if not isinstance(symptom_names, list):
            # Handle legacy single symptom strings by converting to array
            symptom_names = [symptom_names]
            
        print(f"[DEBUG] Checking symptoms: {symptom_names}")
        return any(self._is_single_symptom_present(s, case_data) for s in symptom_names)

    def _is_single_symptom_present(self, symptom_name: str, case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if a single symptom is present in the case data (case-insensitive)."""
        if not symptom_name:  # Add null check
            return False
        # Convert both the symptom name and case data keys to lowercase
        symptom_name_lower = symptom_name.lower()
        case_data_lower = {k.lower(): v for k, v in case_data.items()}
        symptom_data = case_data_lower.get(symptom_name_lower, {})
        is_present = symptom_data.get('present', False) is True
        print(f"[DEBUG] Single symptom '{symptom_name}' present: {is_present}")
        return is_present

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
                
            # Handle different operators.
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
                
        elif condition_type == 'attribute':
            attribute_name = condition.get('attribute')
            operator = condition.get('operator')
            expected_value = condition.get('value')
            
            # Get patient/case attributes
            patient_data = case_data.get('patient', {})
            # Handle case insensitive attribute lookup
            actual_value = None
            for key, value in patient_data.items():
                if key.upper() == attribute_name.upper():
                    actual_value = value
                    break
            
            if actual_value is None:
                return False
                
            print(f"[DEBUG] Checking attribute condition: {attribute_name} = '{actual_value}' against expected '{expected_value}' with operator '{operator}'")
            
            # Special handling for age comparisons
            if attribute_name.upper() == 'AGE':
                actual_age = self._normalize_age_value(actual_value)
                expected_age = self._normalize_age_value(expected_value)
                
                print(f"[DEBUG] Comparing ages: {actual_age} {operator} {expected_age}")
                
                if operator == '==' or operator == 'equals':
                    return actual_age == expected_age
                elif operator == 'contains':
                    return str(expected_age) in str(actual_age)
                elif operator == 'greater_than' or operator == '>':
                    return actual_age > expected_age
                elif operator == 'less_than' or operator == '<':
                    return actual_age < expected_age
            else:
                # Handle non-age attributes with semantic validation
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
