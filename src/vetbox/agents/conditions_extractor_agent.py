import os
import json
from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent


class ConditionsExtractorAgent:
    def __init__(self, model: str = None):
        model = 'openai:gpt-4o'
        self.system_prompt = (
            """
            You are a veterinary triage assistant.
Your job is to extract structured information from pet owner conversations, using the veterinary triage schema.

Instructions:

You will be given the last question asked and the user's answer.

Extract all relevant symptoms and slots (fields and values) based on the schema.

Output your extraction as a valid JSON object using the canonical field and slot names.

Extraction rules:

For each symptom, extract an object with "present" set to true if the symptom is confirmed, false if explicitly denied, or null if uncertain or not addressed.

Example: "coughing": {"present": true}

For any slots (modifiers or attributes), include them as keys within the symptom object, using the canonical slot names.

Example: "hives": {"present": true, "location": ["neck"]}

If multiple symptoms/slots are mentioned, extract each explicitly.

If a symptom/slot is not addressed, do not include it in the output.

Do not infer or guess; only extract what is stated or directly confirmed.

Respond with ONLY a single valid JSON object, and do NOT include any code block, markdown, or commentary.

Example output:
{
  "vomiting": { "present": true, "frequency": "2_per_day" },
  "hives": { "present": false },
  "coughing": { "present": true }
}
            """
        )
        self.agent = Agent(
            model,
            system_prompt=self.system_prompt,
        )

    async def run_async(self, question: str, answer: str) -> dict:
        prompt = f"""
        Extract and output only the relevant symptoms and slots as a JSON object from the following Q&A.
        
        Question: {question}
        Answer: {answer}
        """
        result = await self.agent.run(prompt)
        
        try:
            # Extract the output string from AgentRunResult
            result_str = result.output if hasattr(result, 'output') else str(result)
            # Parse the output string as JSON
            output = json.loads(result_str)
            print("[Extracted Condition from user message]", output)
            return output
        except (json.JSONDecodeError, AttributeError) as e:
            print("[Error] Failed to parse LLM output as JSON:", str(result))
            print("[Error] Specific error:", str(e))
            return {}

    # def run(self, question: str, answer: str) -> dict:
    #     prompt = f"Q: {question}\nA: {answer}"
    #     result = self.agent.run_sync(prompt)
    #     output = result.output.model_dump()
    #     print("[Raw LLM Output]", output)  # Add this debug line
    #     return output