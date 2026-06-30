# scr/schemas/enums
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
