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

You will be given the last question asked and the user's answer, plus any question context that provides information about what specific symptom/condition the question is about.

Extract ALL relevant symptoms and patient attributes mentioned in the conversation, based on the schema.

CRITICAL: Extract every piece of information mentioned, including:
- Species (dog, cat, bird, etc.) when mentioned as "my dog", "my cat", etc.
- Age when mentioned ("3 year old", "puppy", "kitten", etc.)
- Sex when mentioned ("male", "female", "he", "she", etc.)
- All symptoms described

Output your extraction as a valid JSON object using the canonical field and slot names.

CRITICAL: Output ONLY the raw JSON object. Do NOT wrap it in code blocks, markdown, or any other formatting.
BAD: ```json { "key": "value" }```
GOOD: { "key": "value" }

Extraction rules:

**SYMPTOMS:**
For each symptom, extract an object with "present" set to true if the symptom is confirmed, false if explicitly denied, or null if uncertain or not addressed.

Example: "coughing": {"present": true}

For any slots (modifiers or attributes), include them as keys within the symptom object, using the canonical slot names.

Example: "hives": {"present": true, "location": ["neck"]}

**PATIENT ATTRIBUTES:**
Extract patient attributes into a "attributes" object. Common attributes include:
- sex: "male", "female" 
- age: numeric value (in years)
- species: "dog", "cat", "bird", etc.
- breed: "labrador", "siamese", etc.
- weight: numeric value (in lbs or kg)

Example: "attributes": {"sex": "male", "age": 5, "species": "dog"}

**IMPORTANT: Context-aware extraction for follow-up questions:**

When question_context is provided, it tells you exactly what symptom and slot the question is about.
The context will include:
- "parent_symptom": which symptom this slot belongs to
- "slot": which specific slot/attribute is being asked about
- "type": "slot" for slot questions, "symptom" for symptom questions

For slot questions, ALWAYS associate the answer with the parent_symptom specified in the context.

**HANDLING YES/NO RESPONSES:**
When answering follow-up questions, carefully consider what the user is confirming or denying:

1. For direct questions about attributes or conditions:
   - When the question asks "Is your pet X?" or "Is X true?" and the answer is:
     * "yes" → Extract X as the confirmed value
     * "no" → DO NOT extract X, or extract explicit negation if context requires it
   - When additional information is provided:
     * Extract the additional details provided, not the denied value
   - Examples:
     * Q: "Is your pet male?" A: "yes" → {"attributes": {"sex": "male"}}
     * Q: "Is your pet male?" A: "no" → {} (extract nothing, or wait for clarification)
     * Q: "Is your pet male?" A: "no, she's female" → {"attributes": {"sex": "female"}}
     * Q: "Is your pet a cat?" A: "yes" → {"attributes": {"species": "cat"}}
     * Q: "Is your pet a cat?" A: "no" → {} (extract nothing, species is NOT cat)
     * Q: "Is your pet a cat?" A: "no, it's a dog" → {"attributes": {"species": "dog"}}
     * Q: "Is X symptom present?" A: "yes" → {"X": {"present": true}}
     * Q: "Is X symptom present?" A: "no" → {"X": {"present": false}}

2. For questions about conditions:
   - If the question asks about a positive condition (e.g., "Can your pet keep food down?"):
     * "yes" → the positive condition is true
     * "no" → the positive condition is false
   - If the question asks about a negative condition (e.g., "Is your pet unable to hold food down?"):
     * "yes" → the negative condition is true
     * "no" → the negative condition is false

3. For questions about slot values:
   - When asking about a list of options and the answer is "yes":
     * Extract all options from the question and set them as a list
     * Example Q: "Are any of these colors present: red, blue, green?"
       A: "yes" → Set slot value to ["red", "blue", "green"]
   - When asking about a list of options and the answer is "no":
     * Set slot value to empty list []
   - When the user specifies particular values:
     * Set slot value to list containing only specified values
     * Example Q: "Which medications is your pet taking?"
       A: "just aspirin" → Set slot value to ["aspirin"]

4. CRITICAL RULE FOR ATTRIBUTE QUESTIONS:
   - If the question is "Is your pet a [SPECIES]?" and the answer is "no":
     * Extract the negation to avoid asking again: {"attributes": {"species": {"not": "[SPECIES]"}}}
     * This indicates the pet is NOT that species
   - If the question is "Is your pet [ATTRIBUTE_VALUE]?" and the answer is "no":
     * Extract the negation: {"attributes": {"[attribute_name]": {"not": "[ATTRIBUTE_VALUE]"}}}
     * Only extract positive values when user explicitly provides alternatives

5. Always extract based on what is explicitly stated or confirmed
   - Do not extract denied values
   - Do not make assumptions about alternative values unless explicitly stated
   - Only include information that is directly confirmed by the user
   - If the user provides additional information after "no", extract that instead

Example:
Context: {"type": "slot", "slot": "frequency", "parent_symptom": "sneezing"}
Question: "How often has your pet been sneezing?"
Answer: "frequent"
Output: {"sneezing": {"present": true, "frequency": "frequent"}}

Example:
Context: {"type": "slot", "slot": "location", "parent_symptom": "hives"}  
Question: "Where are the hives located?"
Answer: "on the neck"
Output: {"hives": {"present": true, "location": ["neck"]}}

Example:
Context: {"type": "slot", "slot": "medications", "parent_symptom": "treatment"}
Question: "Is your pet on any of these medications: penicillin, amoxicillin, or tetracycline?"
Answer: "yes"
Output: {"treatment": {"present": true, "medications": ["penicillin", "amoxicillin", "tetracycline"]}}

If no context is provided, extract all symptoms and patient attributes as usual from the conversation.

Common slot names include:
- frequency (how often: frequent, hourly, daily, etc.)
- location (where: mouth, nose, neck, etc.)
- severity (mild, moderate, severe)
- duration (how long: minutes, hours, days)
- discharge_quality (foamy, bloody, clear)
- cough_type (dry, productive)
- cannot_hold_down (food, water)
- history_of_insect_sting (yes, no)

If multiple symptoms/slots are mentioned, extract each explicitly.

If a symptom/slot is not addressed, do not include it in the output.

Do not infer or guess; only extract what is stated or directly confirmed.

Respond with ONLY a single valid JSON object, and do NOT include any code block, markdown, or commentary.

Example outputs:
{
  "vomiting": { "present": true, "frequency": "2_per_day" },
  "hives": { "present": false },
  "coughing": { "present": true },
  "attributes": { "sex": "male", "age": 3 }
}

{
  "sneezing": { "present": true, "frequency": "frequent" }
}

{
  "attributes": { "sex": "female", "species": "cat", "age": 7 }
}

CRITICAL: For initial user messages, extract ALL mentioned information:

User: "my dog is not eating"
Output: {"not_eating": {"present": true}, "attributes": {"species": "dog"}}

User: "my 3 year old cat has been vomiting"
Output: {"vomiting": {"present": true}, "attributes": {"species": "cat", "age": 3}}

User: "my puppy seems lethargic and won't eat"
Output: {"lethargy": {"present": true}, "not_eating": {"present": true}, "attributes": {"species": "dog"}}

User: "my male dog has diarrhea"
Output: {"diarrhea": {"present": true}, "attributes": {"species": "dog", "sex": "male"}}

IMPORTANT EXAMPLES FOR YES/NO ATTRIBUTE QUESTIONS:

Q: "Is your pet a [SPECIES_X]?" A: "yes"
Output: {"attributes": {"species": "[SPECIES_X]"}}

Q: "Is your pet a [SPECIES_X]?" A: "no" 
Output: {"attributes": {"species": {"not": "[SPECIES_X]"}}}

Q: "Is your pet a [SPECIES_X]?" A: "no, it's a [SPECIES_Y]"
Output: {"attributes": {"species": "[SPECIES_Y]"}}

Q: "Is your pet [ATTRIBUTE_VALUE_X]?" A: "no"
Output: {"attributes": {"[attribute_name]": {"not": "[ATTRIBUTE_VALUE_X]"}}}

Q: "Is your pet [ATTRIBUTE_VALUE_X]?" A: "no, it's [ATTRIBUTE_VALUE_Y]"  
Output: {"attributes": {"[attribute_name]": "[ATTRIBUTE_VALUE_Y]"}}
            """
        )
        self.agent = Agent(
            model,
            system_prompt=self.system_prompt,
        )

    async def run_async(self, question: str, answer: str, question_context: dict = None) -> dict:
        # Build context information for the prompt
        context_info = ""
        if question_context:
            context_info = f"\nQuestion context: {json.dumps(question_context)}"
            
            # Add specific guidance based on context type
            if question_context.get("type") == "slot":
                parent_symptom = question_context.get("parent_symptom", "").lower()
                slot_name = question_context.get("slot", "")
                context_info += f"\nThis is a follow-up question about the '{slot_name}' slot for the '{parent_symptom}' symptom."
                context_info += f"\nYour answer should be: {{\"{parent_symptom}\": {{\"present\": true, \"{slot_name}\": \"[extracted_value]\"}}}}"
        
        prompt = f"""
        Extract and output only the relevant symptoms and slots as a JSON object from the following Q&A.
        {context_info}
        
        Question: {question}
        Answer: {answer}
        """
        result = await self.agent.run(prompt)
        
        try:
            # Extract the output string from AgentRunResult
            result_str = result.output if hasattr(result, 'output') else str(result)
            
            # Strip any markdown code blocks if present
            if result_str.startswith('```'):
                # Find the first and last ``` and extract content between them
                start = result_str.find('\n', 3) + 1  # Skip first line with ```json
                end = result_str.rfind('```')
                result_str = result_str[start:end].strip()
            
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
