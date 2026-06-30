# scr/schemas/nlu
from pydantic import Field, BeforeValidator
from typing import Annotated
from src.schemas.base import Base
from src.schemas.enums import IntentEnum, TelecomProvider


def coerce_to_intent_enum(v):
    # Converts incoming string tokens perfectly into your Enum instances
    if isinstance(v, str):
        return IntentEnum(v)
    return v


class IntentClassification(Base):
    action: Annotated[IntentEnum, BeforeValidator(coerce_to_intent_enum)] = Field(
        ...,
        description="The predicted intent of the user input, represented as an enumerated value.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="The confidence score of the predicted intent, ranging from 0.0 to 1.0.",
    )
    reasons: list[str] = Field(
        ...,
        description="A list of reasons or explanations for the predicted intent, providing insights into the model's decision-making process.",
    )


class TelecomClassification(Base):
    telecom_provider: TelecomProvider = Field(
        ..., description="The predicted telecom provider based on the user input."
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="The confidence score of the predicted telecom provider, ranging from 0.0 to 1.0.",
    )
    reasons: list[str] = Field(
        ...,
        description="A list of reasons or explanations for the predicted telecom provider, providing insights into the model's decision-making process.",
    )
