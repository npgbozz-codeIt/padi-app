import os
import instructor
from groq import AsyncGroq
from google import genai
from src.schemas.nlu import IntentClassification


def get_nlu_client():
    """
    Dynamically initializes and patches the client wrapper based on environment configs.
    Fetching variables INSIDE the function guarantees dotenv has already loaded them.
    """
    # Fetch provider preference inside the execution call scope
    nlu_provider = os.getenv("NLU_PROVIDER", "groq").lower()

    if nlu_provider == "gemini":
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        return instructor.from_genai(client, mode=instructor.Mode.GENAI_TOOLS)
    else:
        # Fetching api_key here ensures it never reads a None value at boot time
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is missing from your .env configuration file!"
            )

        client = AsyncGroq(api_key=api_key)
        return instructor.from_groq(client, mode=instructor.Mode.TOOLS)


# Defend against instant global instantiation crashes by making this a callable helper
async def classify_intent(user_text: str) -> IntentClassification:
    """
    Sends raw chat text to the active LLM engine
    and forces a strictly structured IntentClassification output.
    """
    # Get a fresh or cached instance of the client dynamically
    client_instance = get_nlu_client()
    nlu_provider = os.getenv("NLU_PROVIDER", "groq").lower()

    model_name = (
        "gemini-2.5-flash" if nlu_provider == "gemini" else "llama-3.3-70b-versatile"
    )

    system_prompt = (
        "You are the core NLU routing engine for MyPadi, a financial bills payment bot in Nigeria. "
        "Analyze the input text carefully, determine their intent, and return the structured parameters."
    )

    response_or_coroutine = client_instance.chat.completions.create(
        model=model_name,
        response_model=IntentClassification,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    )
    # 2. Dynamically await ONLY if it's an asynchronous coroutine (like Groq)
    if nlu_provider == "gemini":
        return response_or_coroutine  # Gemini returns the object directly
    else:
        return await response_or_coroutine  # Groq needs to be awaited
