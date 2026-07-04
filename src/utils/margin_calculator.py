# src/utils/margin_calculator.py
import math
from src.config.pricing import pricing_config


def calculate_retail_price(wholesale_price: float) -> int:
    """
    Applies the tiered fintech markup strategy to an upstream cost.
    Returns a clean, ceiling-rounded integer for retail display.
    """
    # Determine the active tier rule set
    if wholesale_price < pricing_config.TIER_1_MAX:
        margin_type = pricing_config.TIER_1_MARGIN_TYPE
        margin_value = pricing_config.TIER_1_MARGIN
    elif wholesale_price < pricing_config.TIER_2_MAX:
        margin_type = pricing_config.TIER_2_MARGIN_TYPE
        margin_value = pricing_config.TIER_2_MARGIN
    else:
        margin_type = pricing_config.TIER_3_MARGIN_TYPE
        margin_value = pricing_config.TIER_3_MARGIN

    # Compute the final retail cost
    if margin_type == "fixed":
        retail_price = wholesale_price + margin_value
    else:  # percentage markup rule execution
        retail_price = wholesale_price + (wholesale_price * margin_value)

    return math.ceil(retail_price)
