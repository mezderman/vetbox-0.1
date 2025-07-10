from typing import Dict, List, Optional, Any
import json
from .case_data import CaseData
from vetbox.db.database import SessionLocal
from vetbox.db.models import Rule
from pydantic_ai import Agent
from colorama import Fore, init

# Initialize colorama
init()

class RuleEngine:
    """
    Engine for processing and matching veterinary triage rules.
    Handles rule loading, serialization, and matching against case data.
    """

    def __init__(self, rules: List[Dict[str, Any]]):
        """Initialize the rule engine with a list of rules."""
        self.rules = rules
        self.triage_agent = None  # Will be set by TriageAgent
        # Priority mapping from string values to numeric levels
        self.priority_map = {
            "Emergency": 4,
            "Urgent": 3,
            "Sick": 2,
            "Routine": 1,
            "": 0  # Default priority
        }
        # Sort rules by priority using the priority map
        self.rules.sort(key=lambda x: self.priority_map.get(x.get('priority', ''), 0), reverse=True)
        
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
    
    async def find_candidate_rules(self, case_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find rules that have no definitive mismatches and could potentially match."""
        candidates = []
        
        for rule in self.rules:
            # Check if this rule has any definitive mismatches
            has_mismatch = False
            for condition in rule.get('conditions', []):
                if await self._has_definitive_mismatch(condition, case_data):
                    print(f"[DEBUG] Rule {rule.get('rule_code')} discarded - definitive mismatch in condition: {condition}")
                    has_mismatch = True
                    break  # Stop checking other conditions in this rule
            
            # Only add rules with no definitive mismatches as candidates
            if not has_mismatch:
                candidates.append(rule)
                print(f"[DEBUG] Rule {rule.get('rule_code')} added as candidate - no definitive mismatches found")
        
        # Sort candidates by priority (highest first)
        candidates.sort(key=lambda x: self.priority_map.get(x.get('priority', ''), 0), reverse=True)
        return candidates

    async def _has_definitive_mismatch(self, condition: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if a condition has a definitive mismatch (not just missing data)."""
        condition_type = condition.get('type')
        
        if condition_type == 'symptom':
            return self._has_symptom_definitive_mismatch(condition, case_data)
        elif condition_type == 'attribute':
            return await self._has_attribute_definitive_mismatch(condition, case_data)
        elif condition_type == 'slot':
            return await self._has_slot_definitive_mismatch(condition, case_data)
        
        return False

    def _has_symptom_definitive_mismatch(self, condition: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if symptom condition has a definitive mismatch (explicitly false)."""
        symptom_names = condition.get('symptom', [])
        if not isinstance(symptom_names, list):
            symptom_names = [symptom_names]
        
        case_data_lower = {k.lower(): v for k, v in case_data.items()}
        
        # For OR logic symptoms, if ANY symptom is explicitly false, it's not a mismatch
        # Only if ALL symptoms are explicitly false, then it's a mismatch
        logic_type = condition.get('logic_type', 'OR')
        
        if logic_type == 'OR':
            # For OR logic, we need ALL symptoms to be explicitly false to call it a mismatch
            all_false = True
            for symptom_name in symptom_names:
                if symptom_name:
                    symptom_data = case_data_lower.get(symptom_name.lower(), {})
                    if symptom_data.get('present') is not False:  # Not explicitly false
                        all_false = False
                        break
            return all_false and len([s for s in symptom_names if s]) > 0  # Only if we actually checked symptoms
        else:  # AND logic
            # For AND logic, if ANY symptom is explicitly false, it's a mismatch
            for symptom_name in symptom_names:
                if symptom_name:
                    symptom_data = case_data_lower.get(symptom_name.lower(), {})
                    if symptom_data.get('present') is False:
                        return True
        
        return False

    async def _has_attribute_definitive_mismatch(self, condition: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if attribute condition has a definitive mismatch."""
        attribute_name = condition.get('attribute')
        operator = condition.get('operator')
        expected_value = condition.get('value')
        
        # Get actual attribute value
        actual_value = self._get_attribute_value(attribute_name, case_data)
        
        # Only check for mismatch if we have the attribute value
        if actual_value is not None:
            # Check if values don't match
            result = await self._compare_values_async(actual_value, expected_value, operator, f"attribute {attribute_name}")
            if not result:
                print(f"[DEBUG] Definitive mismatch for attribute {attribute_name}: '{actual_value}' vs expected '{expected_value}'")
                return True
        
        return False

    async def _has_slot_definitive_mismatch(self, condition: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if slot condition has a definitive mismatch."""
        parent_symptom = condition.get('parent_symptom')
        slot_name = condition.get('slot')
        
        # First check if parent symptom is present (required for slot evaluation)
        if not self._is_symptom_present(parent_symptom, case_data):
            # Parent symptom not present - this could be a mismatch if parent is explicitly false
            if self._has_symptom_definitive_mismatch({'symptom': [parent_symptom], 'logic_type': 'OR'}, case_data):
                return True
            # Otherwise, it's just not provided yet
            return False
        
        # Parent symptom is present, check slot value
        actual_value = self._get_slot_value(slot_name, parent_symptom, case_data)
        
        # Only check for mismatch if we have a slot value
        if actual_value is not None:
            expected_value = condition.get('value')
            operator = condition.get('operator')
            result = await self._compare_values_async(actual_value, expected_value, operator, f"slot {slot_name}")
            if not result:
                print(f"[DEBUG] Definitive mismatch for slot {slot_name}: '{actual_value}' vs expected '{expected_value}'")
                return True
        
        return False
    
    async def _rule_has_violated_conditions(self, rule: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if rule has any conditions that are explicitly violated by case data."""
        for condition in rule.get('conditions', []):
            if await self._is_condition_violated(condition, case_data):
                print(f"[DEBUG] Rule {rule.get('rule_code')} violated by condition: {condition}")
                return True
        return False
    
    async def _is_condition_violated(self, condition: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if a specific condition is violated (explicitly false or doesn't match)."""
        condition_type = condition.get('type')
        
        if condition_type == 'symptom':
            return self._is_symptom_condition_violated(condition, case_data)
        elif condition_type == 'attribute':
            return await self._is_attribute_condition_violated(condition, case_data)
        
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
                    print(f"{Fore.RED}[DEBUG] Symptom {symptom_name} is explicitly false{Fore.RESET}")
                    return True
        return False
    
    async def _is_attribute_condition_violated(self, condition: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:
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
        if actual_value is not None:
            print(f"{Fore.YELLOW}[DEBUG] Checking attribute violation: {attribute_name} = '{actual_value}' against expected '{expected_value}' with operator '{operator}'{Fore.RESET}")
            
            # Handle the new format where actual_value might be a dict with "not" field
            if isinstance(actual_value, dict) and "not" in actual_value:
                # If we're expecting a value that's in the "not" list, that's a violation
                not_values = [str(v).lower() for v in actual_value["not"]]
                if isinstance(expected_value, list):
                    expected_values = [str(v).lower() for v in expected_value]
                    # If any expected value is in the "not" list, that's a violation
                    return any(ev in not_values for ev in expected_values)
                else:
                    return str(expected_value).lower() in not_values
            
            # Compare values based on operator
            result = await self._compare_values_async(actual_value, expected_value, operator, f"attribute {attribute_name}")
            if not result:
                print(f"{Fore.RED}[DEBUG] Attribute {attribute_name} validation failed{Fore.RESET}")
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
        """Get conditions that are not yet satisfied (but not definitively mismatched)."""
        missing = []
        for condition in rule.get('conditions', []):
            # Skip conditions that have definitive mismatches (these rules shouldn't be candidates)
            if await self._has_definitive_mismatch(condition, case_data):
                continue
                
            # Check if condition is satisfied
            if not await self._is_condition_satisfied_async(condition, case_data):
                missing.append(condition)
        return missing
    
    async def find_best_matching_rule(self, case_data: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find the highest priority rule that matches all conditions."""
        for rule in self.rules:
            # Skip rule if any condition is explicitly violated
            if await self._rule_has_violated_conditions(rule, case_data):
                continue
                
            # Check if all conditions are satisfied
            if await self.is_rule_satisfied(rule, case_data):
                return rule
        
        return None

    async def is_rule_satisfied(self, rule: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if all conditions in a rule are satisfied by the case data."""
        for condition in rule.get('conditions', []):
            if not await self._is_condition_satisfied_async(condition, case_data):
                return False
        return True
    
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

    def _compare_values(self, actual_value: Any, expected_value: Any, operator: str, context: str = "") -> bool:
        """Common logic for comparing values with different operators."""
        if actual_value is None:
            return False
            
        print(f"[DEBUG] Comparing values for {context}: '{actual_value}' {operator} '{expected_value}'")
        
        # Handle yes/no answers for IN operator
        if operator == 'IN':
            # Clean up expected values - remove any "string" placeholder
            if isinstance(expected_value, list):
                expected_value = [v for v in expected_value if v != "string"]
            
            # For yes/no answers
            if str(actual_value).lower() == 'yes':
                print(f"[DEBUG] User confirmed {context}, marking IN condition as satisfied")
                return True
            elif str(actual_value).lower() == 'no':
                print(f"[DEBUG] User denied {context}, marking IN condition as not satisfied")
                return False
            else:
                # For specific answers, check if the actual value is in the expected list
                return any(str(actual_value).lower() == str(exp_val).lower() for exp_val in expected_value)
        
        # Handle numeric comparisons
        elif operator in ['greater_than', '>', 'less_than', '<']:
            try:
                actual_num = float(actual_value)
                expected_num = float(expected_value[0] if isinstance(expected_value, list) else expected_value)
                if operator in ['greater_than', '>']:
                    return actual_num > expected_num
                else:
                    return actual_num < expected_num
            except (ValueError, TypeError):
                print(f"[DEBUG] Failed to compare numeric values: {actual_value} {operator} {expected_value}")
                return False
        
        # Handle equality
        elif operator in ['==', 'equals']:
            # Convert both values to lowercase strings for comparison
            actual_str = str(actual_value).lower()
            
            # If expected value is a list, check if actual value matches any item in the list
            if isinstance(expected_value, list):
                expected_strs = [str(v).lower() for v in expected_value]
                return actual_str in expected_strs
            else:
                # Direct string comparison
                return actual_str == str(expected_value).lower()
            
        # Handle contains
        elif operator == 'contains':
            return str(expected_value).lower() in str(actual_value).lower()
            
        return False

    def _get_slot_value(self, slot_name: str, parent_symptom: str, case_data: Dict[str, Dict[str, Any]]) -> Optional[Any]:
        """Extract slot value from case data."""
        case_data_lower = {k.lower(): v for k, v in case_data.items()}
        parent_symptom_lower = parent_symptom.lower() if parent_symptom else ""
        slot_name_upper = slot_name.upper() if slot_name else ""
        
        symptom_data = case_data_lower.get(parent_symptom_lower, {})
        return symptom_data.get(slot_name_upper)

    def _get_attribute_value(self, attribute_name: str, case_data: Dict[str, Dict[str, Any]]) -> Optional[Any]:
        """Extract attribute value from case data."""
        attributes = case_data.get('attributes', {})
        for key, value in attributes.items():
            if key.upper() == attribute_name.upper():
                return value
        return None

    def _is_condition_satisfied(self, condition: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Check if a condition is satisfied by the case data."""
        condition_type = condition.get('type')
        
        if condition_type == 'symptom':
            symptom_name = condition.get('symptom')
            return self._is_symptom_present(symptom_name, case_data)
            
        elif condition_type == 'slot':
            parent_symptom = condition.get('parent_symptom')
            slot_name = condition.get('slot')
            
            # First check if parent symptom exists and is present
            if not self._is_symptom_present(parent_symptom, case_data):
                return False
                
            actual_value = self._get_slot_value(slot_name, parent_symptom, case_data)
            return self._compare_values(
                actual_value,
                condition.get('value'),
                condition.get('operator'),
                f"slot {slot_name}"
            )
                
        elif condition_type == 'attribute':
            attribute_name = condition.get('attribute')
            actual_value = self._get_attribute_value(attribute_name, case_data)
            
            # If attribute value is not provided, condition is not satisfied
            if actual_value is None:
                return False
            
            # Special handling for age comparisons
            if attribute_name.upper() == 'AGE':
                actual_value = self._normalize_age_value(actual_value)
                expected_value = self._normalize_age_value(condition.get('value'))
            else:
                expected_value = condition.get('value')
                
            return self._compare_values(
                actual_value,
                expected_value,
                condition.get('operator'),
                f"attribute {attribute_name}"
            )
            
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

    async def _compare_values_async(self, actual_value: Any, expected_value: Any, operator: str, context: str = "") -> bool:
        """Async version of _compare_values that supports semantic validation."""
        # First try exact matching
        if self._compare_values(actual_value, expected_value, operator, context):
            return True
            
        # Skip semantic validation for species attributes
        if context.startswith("attribute SPECIES"):
            return False
            
        # If exact match fails and we have a list of expected values, try semantic validation
        if operator in ['==', 'equals', 'IN'] and isinstance(expected_value, list):
            # Clean up expected values
            expected_values = [v for v in expected_value if v != "string"]
            if expected_values:
                print(f"[DEBUG] Exact match failed for {context}, trying semantic validation...")
                is_semantic_match = await self._semantic_validate_condition(str(actual_value), [str(v) for v in expected_values])
                print(f"[DEBUG] Semantic validation result: {is_semantic_match}")
                return is_semantic_match
                
        return False

    async def _is_condition_satisfied_async(self, condition: Dict[str, Any], case_data: Dict[str, Dict[str, Any]]) -> bool:
        """Async version of _is_condition_satisfied that supports semantic validation."""
        condition_type = condition.get('type')
        
        if condition_type == 'symptom':
            symptom_name = condition.get('symptom')
            return self._is_symptom_present(symptom_name, case_data)
            
        elif condition_type == 'slot':
            parent_symptom = condition.get('parent_symptom')
            slot_name = condition.get('slot')
            
            # First check if parent symptom exists and is present
            if not self._is_symptom_present(parent_symptom, case_data):
                return False
                
            actual_value = self._get_slot_value(slot_name, parent_symptom, case_data)
            return await self._compare_values_async(
                actual_value,
                condition.get('value'),
                condition.get('operator'),
                f"slot {slot_name}"
            )
                
        elif condition_type == 'attribute':
            attribute_name = condition.get('attribute')
            actual_value = self._get_attribute_value(attribute_name, case_data)
            
            # If attribute value is not provided, condition is not satisfied
            if actual_value is None:
                return False
            
            # Special handling for age comparisons
            if attribute_name.upper() == 'AGE':
                actual_value = self._normalize_age_value(actual_value)
                expected_value = self._normalize_age_value(condition.get('value'))
            else:
                expected_value = condition.get('value')
                
            return await self._compare_values_async(
                actual_value,
                expected_value,
                condition.get('operator'),
                f"attribute {attribute_name}"
            )
            
        return False
