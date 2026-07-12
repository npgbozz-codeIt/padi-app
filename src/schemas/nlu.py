# src/schemas/nlu.py
from pydantic import Field, BeforeValidator
from typing import Annotated, Optional, Literal
from src.schemas.base import Base
from src.schemas.enums import (
    IntentEnum,
    TelecomProvider,
    CableTvProvider,
    BettingProvider,
    EducationProvider,
    IspProvider,
    Disco,
)


# --- Reusable Coercion Helpers for Instructor/Pydantic ---
def coerce_to_intent_enum(v):
    # Converts incoming string tokens perfectly into your Enum instances
    if isinstance(v, str):
        return IntentEnum(v)
    return v


def coerce_to_telecom_enum(v):
    if isinstance(v, str):
        return TelecomProvider(v)
    return v


def coerce_to_cabletv_enum(v):
    if isinstance(v, str):
        return CableTvProvider(v)
    return v


def coerce_to_betting_enum(v):
    if isinstance(v, str):
        return BettingProvider(v)


def coerce_to_education_enum(v):
    if isinstance(v, str):
        return EducationProvider(v)
    return v


def coerce_to_isp_enum(v):
    if isinstance(v, str):
        return IspProvider(v)
    return v


def coerce_to_disco_enum(v):
    if isinstance(v, str):
        return Disco(v)
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
    telecom_provider: Annotated[
        TelecomProvider, BeforeValidator(coerce_to_telecom_enum)
    ] = Field(
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


# ====================== nlu shemas for intent extraction=======================
class AirtimeExtraction(Base):
    amount: Optional[int] = Field(
        None,
        description="The extracted amount for the airtime purchase.",
    )
    phone_number: Optional[str] = Field(
        None,
        description="The extracted phone number for the airtime purchase.",
    )
    network: Annotated[
        Optional[TelecomProvider], BeforeValidator(coerce_to_telecom_enum)
    ] = Field(
        None,
        description="The extracted telecom provider for the airtime purchase, e.g  mtn, airtel or zain , 9mobile or etisalat, glo",
    )


class DataExtraction(Base):
    amount: Optional[int] = Field(
        None,
        description="The extracted amount for the data purchase.",
    )
    provider: Annotated[
        Optional[TelecomProvider], BeforeValidator(coerce_to_telecom_enum)
    ] = Field(
        None,
        description="The extracted telecom provider for the data purchase.",
    )
    phone_number: Optional[str] = Field(
        None,
        description="The extracted phone number for the data purchase.",
    )
    types: Optional[
        Literal["direct_data", "sme", "nighty", "gifting", "social", "coporate_gifting"]
    ] = Field(
        None,
        description="The extracted category for the data purchase e.g sme ,gifting, coporate_gifting are usually  cheaper than direct_data.",
    )


class CableTvExtraction(Base):
    amount: Optional[int] = Field(
        None,
        description="The extracted amount for the cable TV subscription.",
    )
    provider: Annotated[
        Optional[CableTvProvider], BeforeValidator(coerce_to_cabletv_enum)
    ] = Field(
        None,
        description="The extracted cable TV provider for the subscription.",
    )

    types: Optional[Literal["renewal", "new_subscription"]] = Field(
        None,
        description="The extracted subscription type for the cable TV subscription, either 'renewal' or 'new_subscription'.",
    )


class ElectricityExtraction(Base):
    amount: Optional[int] = Field(
        None,
        description="The extracted amount for the electricity bill payment.",
    )
    company: Annotated[Optional[Disco], BeforeValidator(coerce_to_disco_enum)] = Field(
        None,
        description="The extracted electricity distribution company (DisCo) provider, matching the official code.",
    )
    meter_no: Optional[str] = Field(
        None,
        description="The extracted customer utility meter number isolated from the user message.",
    )
    meter_type: Optional[Literal["prepaid", "postpaid"]] = Field(
        "prepaid",
        description="The extracted electricity account type, either 'prepaid' or 'postpaid'. Defaults to 'prepaid'.",
    )
    phone_number: Optional[str] = Field(
        None,
        description="An optional specific recipient phone number extracted from the message to route the token voucher text message.",
    )


class EducationExtraction(Base):
    amount: Optional[int] = Field(
        None,
        description="The extracted amount for the education fee payment.",
    )
    provider: Annotated[
        Optional[EducationProvider], BeforeValidator(coerce_to_education_enum)
    ] = Field(
        None,
        description="The extracted education provider for the fee payment.",
    )


class BettingExtraction(Base):
    amount: Optional[int] = Field(
        None,
        description="The extracted amount for the betting payment.",
    )
    provider: Annotated[
        Optional[BettingProvider], BeforeValidator(coerce_to_betting_enum)
    ] = Field(
        None,
        description="The extracted betting provider for the payment.",
    )


class IspExtraction(Base):
    amount: Optional[int] = Field(
        None,
        description="The extracted amount for the ISP payment.",
    )
    provider: Annotated[Optional[IspProvider], BeforeValidator(coerce_to_isp_enum)] = (
        Field(
            None,
            description="The extracted ISP provider for the payment.",
        )
    )
