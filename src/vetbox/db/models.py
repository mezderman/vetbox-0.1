from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)

class Symptom(Base):
    __tablename__ = "symptoms"
    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True, nullable=False)
    display_name = Column(String(128), nullable=False)
    description = Column(Text)
    active = Column(Boolean, default=True)

class SlotName(Base):
    __tablename__ = "slot_names"
    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True, nullable=False)
    display_name = Column(String(128), nullable=False)
    description = Column(Text)
    unit = Column(String(32))

class PatientAttribute(Base):
    __tablename__ = "patient_attributes"
    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True, nullable=False)
    display_name = Column(String(128), nullable=False)
    description = Column(Text)
    data_type = Column(String(32))  # 'string', 'integer', 'float', 'boolean'

class Rule(Base):
    __tablename__ = "rules"
    id = Column(Integer, primary_key=True)
    rule_code = Column(String(32), unique=True)
    priority = Column(String(32), nullable=False)
    rationale = Column(Text, nullable=False)
    conditions = relationship("RuleCondition", back_populates="rule", cascade="all, delete-orphan")

class RuleCondition(Base):
    __tablename__ = "rule_conditions"
    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey("rules.id", ondelete="CASCADE"), nullable=False)
    condition_type = Column(String(16), nullable=False)  # 'symptom', 'slot', or 'attribute'
    symptom_id = Column(Integer, ForeignKey("symptoms.id"))
    slot_name_id = Column(Integer, ForeignKey("slot_names.id"))
    attribute_id = Column(Integer, ForeignKey("patient_attributes.id"))
    operator = Column(String(8))
    value = Column(String(64))
    parent_symptom_id = Column(Integer, ForeignKey("symptoms.id"))

    rule = relationship("Rule", back_populates="conditions")
    symptom = relationship("Symptom", foreign_keys=[symptom_id])
    slot_name = relationship("SlotName")
    attribute = relationship("PatientAttribute")
    parent_symptom = relationship("Symptom", foreign_keys=[parent_symptom_id])

class SuspiciousCode(Base):
    __tablename__ = "suspicious_codes"
    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True, nullable=False)
    display_name = Column(String(128), nullable=False)
    description = Column(Text)