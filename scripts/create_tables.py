import os
import sys

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from vetbox.db.database import engine, Base
from vetbox.db.models import User, Symptom, SlotName, PatientAttribute, Rule, RuleCondition, SuspiciousCode

def create_tables():
    """Create all tables in the database."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")

if __name__ == "__main__":
    create_tables()