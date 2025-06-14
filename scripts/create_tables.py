from vetbox.db.database import engine, Base
from vetbox.db.models import Symptom, SlotName, Rule, RuleCondition, SuspiciousCode

def create_all_tables():
    Base.metadata.create_all(bind=engine)
    print("All tables created.")

if __name__ == "__main__":
    create_all_tables()