# src/utils/network_detector.py
import re
from typing import Optional


def detect_network(phone_number: str) -> Optional[str]:
    """
    Detects the Nigerian telecom network (mtn, glo, airtel, 9mobile) 
    from a phone number string.
    """
    if not phone_number:
        return None

    # Strip all non-digit characters
    clean_num = re.sub(r"\D", "", str(phone_number))

    # Normalize international formatting (e.g., +234803... or 234803... to 0803...)
    if clean_num.startswith("234") and len(clean_num) == 13:
        clean_num = "0" + clean_num[3:]
    elif len(clean_num) == 10 and not clean_num.startswith("0"):
        clean_num = "0" + clean_num

    if len(clean_num) != 11:
        return None

    prefix = clean_num[:4]

    mtn_prefixes = {
        "0803", "0806", "0703", "0706", "0813", "0816",
        "0810", "0814", "0903", "0906", "0913", "0916", "0704"
    }
    glo_prefixes = {
        "0805", "0807", "0705", "0815", "0811", "0905", "0915"
    }
    airtel_prefixes = {
        "0802", "0808", "0708", "0812", "0701",
        "0902", "0901", "0904", "0907", "0912"
    }
    nine_mobile_prefixes = {
        "0809", "0818", "0817", "0909", "0908"
    }

    if prefix in mtn_prefixes:
        return "mtn"
    if prefix in glo_prefixes:
        return "glo"
    if prefix in airtel_prefixes:
        return "airtel"
    if prefix in nine_mobile_prefixes:
        return "9mobile"

    return None


def normalize_network_name(network_str: str) -> str:
    """Normalizes network string representations consistently across the codebase."""
    if not network_str:
        return ""
    s = str(network_str).strip().lower()
    if "9" in s or "etisalat" in s:
        return "9mobile"
    elif "mtn" in s:
        return "mtn"
    elif "glo" in s:
        return "glo"
    elif "airtel" in s:
        return "airtel"
    return s