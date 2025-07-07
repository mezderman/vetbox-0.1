#!/usr/bin/env python3
"""
Migration script to add OR logic support to rule_conditions table.
Adds symptom_ids (integer array) and logic_type columns.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from vetbox.db.database import SessionLocal
from sqlalchemy import text

def migrate_add_or_logic():
    """Add symptom_ids array and logic_type columns to rule_conditions table."""
    
    session = SessionLocal()
    try:
        print("Adding symptom_ids and logic_type columns to rule_conditions table...")
        
        # Add symptom_ids column (integer array)
        session.execute(text("""
            ALTER TABLE rule_conditions 
            ADD COLUMN IF NOT EXISTS symptom_ids INTEGER[];
        """))
        
        # Add logic_type column with default 'AND'
        session.execute(text("""
            ALTER TABLE rule_conditions 
            ADD COLUMN IF NOT EXISTS logic_type VARCHAR(8) DEFAULT 'AND';
        """))
        
        session.commit()
        print("✅ Successfully added OR logic columns to rule_conditions table")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error during migration: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    migrate_add_or_logic() 