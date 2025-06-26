import os
import sys

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy import text
from vetbox.db.database import engine

def migrate_database():
    """Add patient_attributes table and attribute_id column to rule_conditions."""
    
    with engine.connect() as conn:
        # Create patient_attributes table
        print("Creating patient_attributes table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS patient_attributes (
                id SERIAL PRIMARY KEY,
                code VARCHAR(64) UNIQUE NOT NULL,
                display_name VARCHAR(128) NOT NULL,
                description TEXT,
                data_type VARCHAR(32)
            )
        """))
        
        # Add attribute_id column to rule_conditions table
        print("Adding attribute_id column to rule_conditions...")
        try:
            conn.execute(text("""
                ALTER TABLE rule_conditions 
                ADD COLUMN attribute_id INTEGER REFERENCES patient_attributes(id)
            """))
        except Exception as e:
            if "already exists" in str(e):
                print("Column attribute_id already exists, skipping...")
            else:
                raise e
        
        conn.commit()
        print("Migration completed successfully!")

if __name__ == "__main__":
    migrate_database() 