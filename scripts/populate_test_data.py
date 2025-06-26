import json
from pathlib import Path
from sqlalchemy.orm import Session
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
                    symptom = get_or_create_symptom(session, cond["symptom"])
                    condition = RuleCondition(
                        rule_id=rule.id,
                        condition_type="symptom",
                        symptom_id=symptom.id
                    )
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
                else:
                    continue  # Unknown type, skip

                session.add(condition)

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
