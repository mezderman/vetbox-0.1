import os
from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent

class ConditionsExtractorOutput(BaseModel):
    """A flexible model that can handle any symptoms and slots."""
    model_config = ConfigDict(extra="allow")  # This allows any additional fields

class ConditionsExtractorAgent:
    def __init__(self, model: str = None):
        model = 'openai:gpt-4o'
        self.system_prompt = (
            """
            You are a veterinary triage assistant. Your job is to extract structured information from pet owner conversations.  
            Given the last question asked and the user's answer, extract all relevant symptoms and slots (fields and values).  
            Output your extraction as a valid JSON object.

            Rules:
            - For symptoms, return `true` if the symptom is confirmed present, `false` if explicitly denied, or `null` if uncertain
            - For slots (like frequency, location, severity), extract the value or `null` if not addressed
            - Do **not** guess or infer information that was not directly provided in the answer
            - Use simple, canonical names for symptoms and slots
            - Return an empty object {} if no symptoms or slots are found
            - IMPORTANT: If the answer is a single word or phrase that appears to be a symptom, treat it as a confirmed symptom
            - IMPORTANT: Always return at least one symptom if the answer contains any symptom-related information

            EXAMPLES:

            Q: "What symptoms is your pet experiencing?"
            A: "coughing"
            → {"coughing": true}

            Q: "What symptoms is your pet experiencing?"
            A: "My dog is coughing a lot."
            → {"coughing": true, "frequency": "high"}

            Q: "What symptoms is your pet experiencing?"
            A: "She's been vomiting and seems lethargic."
            → {"vomiting": true, "lethargic": true}

            Q: "What symptoms is your pet experiencing?"
            A: "He has hives on his face."
            → {"hives": true, "location": ["face"]}

            Q: "What symptoms is your pet experiencing?"
            A: "No symptoms right now."
            → {}
            """
        )
        self.agent = Agent(
            model,
            output_type=ConditionsExtractorOutput,
            system_prompt=self.system_prompt,
        )

    async def run_async(self, question: str, answer: str) -> dict:
        prompt = f"Q: {question}\nA: {answer}"
        print("[ConditionsExtractorAgent prompt]", prompt)
        result = await self.agent.run(prompt)
        output = result.output.model_dump()
        print("[Raw LLM Output]", output)  # Add this debug line
        return output

    def run(self, question: str, answer: str) -> dict:
        prompt = f"Q: {question}\nA: {answer}"
        result = self.agent.run_sync(prompt)
        output = result.output.model_dump()
        print("[Raw LLM Output]", output)  # Add this debug line
        return output