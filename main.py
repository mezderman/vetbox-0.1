from dotenv import load_dotenv
import os
from src.vetbox.agents.triage_agent import TriageAgent

# Load environment variables from .env
load_dotenv()

if __name__ == "__main__":
    agent = TriageAgent()
    user_input = input("Describe your symptoms: ")
    result = agent.run(user_input)
    print(f"Triage Level: {result.triage_level}\nAdvice: {result.advice}") 