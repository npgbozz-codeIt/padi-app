import os
import logging
from typing import Type, TypeVar
import instructor
from instructor.exceptions import InstructorRetryException
from google import genai
from groq import AsyncGroq
from pydantic import BaseModel

from src.schemas.nlu import (
    AirtimeExtraction,
    BettingExtraction,
    CableTvExtraction,
    DataExtraction,
    EducationExtraction,
    ElectricityExtraction,
    IntentClassification,
    IspExtraction,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def get_nlu_client():
    """
    Dynamically initializes and patches the client wrapper based on environment configs.
    Fetching variables INSIDE the function guarantees dotenv has already loaded them.
    """
    nlu_provider = os.getenv("NLU_PROVIDER", "groq").lower()

    if nlu_provider == "gemini":
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        return instructor.from_genai(client, mode=instructor.Mode.GENAI_TOOLS)
    else:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is missing from your .env configuration file!"
            )

        client = AsyncGroq(api_key=api_key)
        return instructor.from_groq(client, mode=instructor.Mode.TOOLS)


def get_model_name() -> str:
    """
    Returns the configured model name based on provider and environment variables.
    Allows changing models via .env without modifying source code.
    """
    nlu_provider = os.getenv("NLU_PROVIDER", "groq").lower()
    if nlu_provider == "gemini":
        return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    else:
        return os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


async def _run_nlu_completion(
    response_model: Type[T], system_prompt: str, user_text: str
) -> T:
    """
    Central helper to execute Instructor queries across Groq and Gemini seamlessly.
    Includes exception handling to catch schema validation/retry failures and return safe fallbacks.
    """
    client_instance = get_nlu_client()
    nlu_provider = os.getenv("NLU_PROVIDER", "groq").lower()
    model_name = get_model_name()

    try:
        response_or_coroutine = client_instance.chat.completions.create(
            model=model_name,
            response_model=response_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            max_retries=2,
        )

        if nlu_provider == "gemini":
            return response_or_coroutine
        else:
            return await response_or_coroutine

    except (InstructorRetryException, Exception) as e:
        logger.error(
            f"⚠ [NLU Engine Error for {response_model.__name__}]: {e}"
        )
        try:
            return response_model()
        except Exception:
            return response_model.model_construct()


async def classify_intent(user_text: str) -> IntentClassification:
    """Sends raw chat text to the active LLM engine
    and forces a strictly structured IntentClassification output.
    """
    system_prompt = (
        "You are the core NLU routing engine for MyPadi, a financial bills payment bot in Nigeria.\n"
        "Analyze the input text carefully, determine their intent, and return structured parameters.\n\n"
        "Allowed action values MUST be strictly lowercase, matching one of:\n"
        "- 'greeting'\n"
        "- 'buy_airtime'\n"
        "- 'buy_data'\n"
        "- 'payfor_electricity'\n"
        "- 'payfor_cabletv'\n"
        "- 'payfor_betting'\n"
        "- 'payfor_education'\n"
        "- 'check_balance'\n"
        "- 'fund_wallet'\n"
        "- 'onboarding'\n"
        "- 'unknown'"
    )
    return await _run_nlu_completion(IntentClassification, system_prompt, user_text)


async def extract_airtime_slots(user_text: str) -> AirtimeExtraction:
    system_prompt = (
        "You are the core NLU routing engine for MyPadi, a financial bills payment bot in Nigeria. "
        "Extract airtime purchase parameters. "
        "Network values MUST be lowercase: 'mtn', 'glo', 'airtel', '9mobile'."
    )
    return await _run_nlu_completion(AirtimeExtraction, system_prompt, user_text)


async def extract_datapurchase_slots(user_text: str) -> DataExtraction:
    system_prompt = (
        "You are the core NLU routing engine for MyPadi, a financial bills payment bot in Nigeria. "
        "Extract data bundle purchase parameters. "
        "Provider values MUST be lowercase: 'mtn', 'glo', 'airtel', '9mobile'."
    )
    return await _run_nlu_completion(DataExtraction, system_prompt, user_text)


async def extract_cabletv_slots(user_text: str) -> CableTvExtraction:
    system_prompt = (
        "You are the core NLU routing engine for MyPadi, a financial bills payment bot in Nigeria. "
        "Extract cable TV subscription parameters. Provider values MUST be lowercase: 'dstv', 'gotv', 'startime'."
    )
    return await _run_nlu_completion(CableTvExtraction, system_prompt, user_text)


async def extract_betting_slots(user_text: str) -> BettingExtraction:
    system_prompt = (
        "You are the core NLU routing engine for MyPadi, a financial bills payment bot in Nigeria. "
        "Extract betting payment parameters. Provider values MUST be lowercase: 'bet9ja', 'sportybet'."
    )
    return await _run_nlu_completion(BettingExtraction, system_prompt, user_text)


async def extract_education_slots(user_text: str) -> EducationExtraction:
    system_prompt = (
        "You are the core NLU routing engine for MyPadi, a financial bills payment bot in Nigeria. "
        "Extract education fee payment parameters. Provider values MUST be lowercase: 'jamb', 'waec', 'neco'."
    )
    return await _run_nlu_completion(EducationExtraction, system_prompt, user_text)


async def extract_isp_slots(user_text: str) -> IspExtraction:
    system_prompt = (
        "You are the core NLU routing engine for MyPadi, a financial bills payment bot in Nigeria. "
        "Extract ISP payment parameters. Provider values MUST be lowercase: 'smile', 'spectranet'."
    )
    return await _run_nlu_completion(IspExtraction, system_prompt, user_text)


async def extract_electricity_slots(user_text: str) -> ElectricityExtraction:
    system_prompt = (
        "You are the core NLU routing engine for MyPadi, a financial bills payment bot in Nigeria. "
        "Extract electricity bill payment parameters. "
        "CRITICAL: The 'company' field MUST be strict lowercase matching one of: "
        "'abedc', 'aedc', 'bedc', 'eedc', 'ekedc', 'ibedc', 'ikedc', 'jed', 'kaedco', 'kedco', 'phed', 'yedc'. "
        "Map city names (Aba->abedc, Abuja->aedc, Benin->bedc, Enugu->eedc, Eko->ekedc, Ibadan->ibedc, "
        "Ikeja->ikedc, Jos->jed, Kaduna->kaedco, Kano->kedco, Port Harcourt->phed, Yola->yedc). "
        "Never output uppercase letters for company."
    )
    return await _run_nlu_completion(ElectricityExtraction, system_prompt, user_text)
