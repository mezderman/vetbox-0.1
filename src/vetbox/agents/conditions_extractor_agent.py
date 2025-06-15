import os
from pydantic import BaseModel, RootModel, ConfigDict
from pydantic_ai import Agent

class ConditionsExtractorInput(BaseModel):
    question: str
    answer: str

class ConditionsExtractorOutput(BaseModel):
    model_config = ConfigDict(extra="allow")



class ConditionsExtractorAgent:
    def __init__(self, model: str = None):
        model = 'openai:gpt-4o'
        self.system_prompt = (
            """
            You are a veterinary triage assistant. Your job is to extract structured information from pet owner conversations.  
Given the last question asked and the user's answer, extract all relevant symptoms and slots (fields and values) based on the veterinary triage schema.  
Output your extraction as a valid JSON object using canonical field names.

- For symptoms, return `true` if the symptom is confirmed present, `false` if explicitly denied, or `null` if uncertain or not addressed.
- For slots (like frequency, location, gender, severity), extract the value (e.g., "5_per_hour", "mouth", "female", "severe") or `null` if not addressed.
- Do **not** guess or infer information that was not directly provided in the answer.

Example schema fields:
- vomiting: true/false/null
- lethargic: true/false/null
- hives: true/false/null
- location: "mouth", "nose", etc.
- frequency: "5_per_hour", "1_per_day", etc.
- cannot_hold_down: ["food", "water"]
- gender: "male" or "female"
- reproductive: "spayed", "intact", "not_spayed"
- severity: "mild", "severe", etc.

Return only a JSON object of updated symptoms and slots from this Q&A.

EXAMPLES:

Q: "Is your dog vomiting?"  
A: "Yes, several times today."  
→ {"vomiting": true, "frequency": "several_times_today"}

Q: "Where are the hives located?"  
A: "They're on her mouth and nose."  
→ {"hives": true, "location": ["mouth", "nose"]}

Q: "Can your dog keep any water down?"  
A: "No, she throws up every time she drinks."  
→ {"cannot_hold_down": ["water"]}

Q: "Is your dog male or female?"  
A: "Female."  
→ {"gender": "female"}
            """
        )
        self.agent = Agent(
            model,
            output_type=ConditionsExtractorOutput,
            system_prompt=self.system_prompt,
        )


    async def run_async(self, question: str, answer: str) -> dict[str, object]:
        prompt = f"Q: {question}\nA: {answer}"
        result = await self.agent.run(prompt)
        return result.output.model_dump()

    def run(self, question: str, answer: str) -> dict[str, object]:
        prompt = f"Q: {question}\nA: {answer}"
        result = self.agent.run_sync(prompt)
        return result.output.model_dump()