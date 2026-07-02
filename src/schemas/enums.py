# scr/schemas/enums.py
from enum import Enum


class IntentEnum(str, Enum):
    START_ONBOARDING = "onboarding"
    CHECK_BALANCE = "check_balance"
    FUND_WALLET = "fund_wallet"
    BUY_AIRTIME = "buy_airtime"
    BUY_DATA = "buy_data"
    PAY_BETTING = "payfor_betting"
    PAY_CABLETV = "payfor_cabletv"
    PAY_ELECTRICITY = "payfor_electricity"
    PAY_EDUCATION = "payfor_education"
    UNKNOWN = "unknown"


class UserLang(str, Enum):
    ENGLISH = "english"
    PIDGIN = "pidgin"
    HAUSA = "hausa"


# =========================ENUMS FOR USER'S STATES ====================
class OnboardingState(str, Enum):
    AWAITING_LANGUAGE = "awaiting_language"
    AWAITING_PHONE = "awaiting_phone"
    AWAITING_BVN = "awaiting_bvn"
    AWAITING_PIN = "awaiting_pin"
    AWAITING_PIN_CONFIRMATION = "awaiting_pin_confirmation"
    COMPLETED = "completed"


# ================ENUMS FOR BIGSUB AND THIRDPARTY PROVIDER============
class TelecomProvider(str, Enum):
    AIRTEL = "airtel"
    ETISALAT = "9mobile"
    GLO = "glo"
    MTN = "mtn"


class CableTvProvider(str, Enum):
    STARTIME = "startime"
    GOTV = "gotv"
    DSTV = "dstv"


class BettingProvider(str, Enum):
    BET9JA = "bet9ja"
    SPORTYBET = "sportybet"


class EducationProvider(str, Enum):
    JAMB = "jamb"
    WAEC = "waec"
    NECO = "neco"


class IspProvider(str, Enum):
    SMILE = "smile"
    SPECTRANET = "spectranet"


class Disco(str, Enum):
    EEDC = "eedc"
    IBEDC = "ibedc"
    KEDCO = "kedco"


# ======== payment type enum for the payment method used by the user to fund their wallet or make a payment for a service ==============


class PaymentType(str, Enum):
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    USSD = "ussd"
    WALLET = "wallet"
