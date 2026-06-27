#scr/schemas/enums
from enum import StrEnum

class IntentEnum(StrEnum):
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

class UserLang(StrEnum):
    ENGLISH = "english"
    PIDGIN = "pidgin"
    HAUSA = "hausa"


#================ENUMS FOR BIGSUB AND THIRDPARTY PROVIDER============
class TelecomProvider(StrEnum):
    AIRTEL = "airtel"
    ETISALAT = "9mobile"
    GLO = "glo"
    MTN = "mtn"

class CableTvProvider(StrEnum):
    STARTIME = "startime"
    GOTV = "gotv"
    DSTV = "dstv"

class BettingProvider(StrEnum):
    BET9JA = "bet9ja"
    SPORTYBET = "sportybet"

class EducationProvider(StrEnum):
    JAMB = "jamb"
    WAEC = "waec"
    NECO = "neco"

class IspProvider(StrEnum):
    SMILE = "smile"
    SPECTRANET = "spectranet"


    


