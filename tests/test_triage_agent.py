import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from vetbox.agents.triage_agent import TriageAgent, TriageInput

def test_triage_agent_chest_pain():
    agent = TriageAgent()
    result = agent.run(TriageInput(symptoms="chest pain"))
    assert result.triage_level == "High"
    assert "immediate" in result.advice.lower()

def test_triage_agent_fever():
    agent = TriageAgent()
    result = agent.run(TriageInput(symptoms="fever"))
    assert result.triage_level == "Medium"
    assert "monitor" in result.advice.lower()

def test_triage_agent_other():
    agent = TriageAgent()
    result = agent.run(TriageInput(symptoms="headache"))
    assert result.triage_level == "Low"
    assert "rest" in result.advice.lower() 