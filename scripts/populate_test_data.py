import json
from pathlib import Path
from sqlalchemy.orm import Session
from vetbox.db.database import SessionLocal, Base, engine
from vetbox.db.models import Rule, RuleCondition, Symptom, SlotName

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

def main():
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)

    with open(DATA_PATH, "r") as f:
        rules_data = json.load(f)

    session = SessionLocal()

    for rule_data in rules_data:
        # Check if rule already exists (by id or rule_code)
        existing_rule = session.query(Rule).filter(
            (Rule.id == rule_data["id"]) | (Rule.rule_code == rule_data["rule_code"])
        ).first()
        if existing_rule:
            print(f"Rule with id={rule_data['id']} or rule_code={rule_data['rule_code']} already exists. Skipping.")
            continue

        rule = Rule(
            id=rule_data["id"],
            rule_code=rule_data["rule_code"],
            priority=rule_data["priority"],
            rationale=rule_data["rationale"]
        )
        session.add(rule)
        session.flush()  # Get rule.id if autoincrement

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
            else:
                continue  # Unknown type, skip

            session.add(condition)

    session.commit()
    session.close()
    print("Rules and conditions populated successfully.")

if __name__ == "__main__":
    main()
