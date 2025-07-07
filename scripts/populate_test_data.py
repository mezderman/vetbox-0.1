import json
import sys
import os
from pathlib import Path
from sqlalchemy.orm import Session

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from vetbox.db.database import SessionLocal, Base, engine
from vetbox.db.models import Rule, RuleCondition, Symptom, SlotName, PatientAttribute

# Change this path if you move rules.json elsewhere
DATA_PATH = Path(__file__).parent.parent / "data" / "rules.json"

def get_or_create_symptom(session: Session, code: str):
    symptom = session.query(Symptom).filter_by(code=code).first()
    if not symptom:
        symptom = Symptom(code=code, display_name=code, description="")
        session.add(symptom)
        session.commit()
        session.refresh(symptom)
    return symptom

def get_or_create_slot(session: Session, code: str):
    slot = session.query(SlotName).filter_by(code=code).first()
    if not slot:
        slot = SlotName(code=code, display_name=code, description="")
        session.add(slot)
        session.commit()
        session.refresh(slot)
    return slot

def get_or_create_patient_attribute(session: Session, code: str):
    attribute = session.query(PatientAttribute).filter_by(code=code).first()
    if not attribute:
        attribute = PatientAttribute(code=code, display_name=code, description="", data_type="string")
        session.add(attribute)
        session.commit()
        session.refresh(attribute)
    return attribute

def clear_all_data(session: Session):
    """Delete all data from all tables in the correct order (respecting foreign keys)"""
    print("Clearing all existing data...")
    
    # Delete in order to respect foreign key constraints
    session.query(RuleCondition).delete()
    session.query(Rule).delete() 
    session.query(Symptom).delete()
    session.query(SlotName).delete()
    session.query(PatientAttribute).delete()
    
    session.commit()
    print("All data cleared successfully.")

def main():
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)

    with open(DATA_PATH, "r") as f:
        rules_data = json.load(f)

    session = SessionLocal()

    try:
        # Clear all existing data first
        clear_all_data(session)
        
        print(f"Inserting {len(rules_data)} rules from {DATA_PATH}...")

        for rule_data in rules_data:
            print(f"Creating rule: {rule_data['rule_code']} (ID: {rule_data['id']})")
            
            # Create new rule
            rule = Rule(
                id=rule_data["id"],
                rule_code=rule_data["rule_code"],
                priority=rule_data["priority"],
                rationale=rule_data["rationale"]
            )
            session.add(rule)
            session.flush()  # Get rule.id if needed
            
            # Add conditions
            for cond in rule_data["conditions"]:
                if cond["type"] == "symptom":
                    # Handle symptom arrays using new OR logic
                    symptom_list = cond["symptom"]
                    if not isinstance(symptom_list, list):
                        # Handle legacy single symptom strings
                        symptom_list = [symptom_list]
                    
                    # Create all symptom records first
                    symptom_ids = []
                    for symptom_code in symptom_list:
                        symptom = get_or_create_symptom(session, symptom_code)
                        symptom_ids.append(symptom.id)
                    
                    # Create one condition with symptom_ids array for OR logic
                    logic_type = "OR" if len(symptom_ids) > 1 else "AND"
                    condition = RuleCondition(
                        rule_id=rule.id,
                        condition_type="symptom",
                        symptom_ids=symptom_ids,
                        logic_type=logic_type
                    )
                    session.add(condition)
                        
                elif cond["type"] == "slot":
                    slot = get_or_create_slot(session, cond["slot"])
                    parent_symptom = get_or_create_symptom(session, cond["parent_symptom"])
                    value = cond.get("value")
                    # Store value as string (JSON if list)
                    if isinstance(value, list):
                        value_str = json.dumps(value)
                    else:
                        value_str = str(value) if value is not None else None
                    condition = RuleCondition(
                        rule_id=rule.id,
                        condition_type="slot",
                        slot_name_id=slot.id,
                        parent_symptom_id=parent_symptom.id,
                        operator=cond.get("operator"),
                        value=value_str
                    )
                    session.add(condition)
                    
                elif cond["type"] == "attribute":
                    attribute = get_or_create_patient_attribute(session, cond["attribute"])
                    value = cond.get("value")
                    # Store value as string (JSON if list)
                    if isinstance(value, list):
                        value_str = json.dumps(value)
                    else:
                        value_str = str(value) if value is not None else None
                    condition = RuleCondition(
                        rule_id=rule.id,
                        condition_type="attribute",
                        attribute_id=attribute.id,
                        operator=cond.get("operator"),
                        value=value_str
                    )
                    session.add(condition)
                else:
                    continue  # Unknown type, skip

        session.commit()
        print("All rules and conditions inserted successfully.")
        
    except Exception as e:
        session.rollback()
        print(f"Error occurred: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    main()
