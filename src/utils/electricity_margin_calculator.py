# src/utils/electricity_margin_calculator.py
import math
from src.config.electricity_pricing import electricity_pricing_config


def calculate_electricity_retail_cost(user_requested_amount: float) -> float:
    """
    Calculates the final retail cost the user must pay for a transaction.
    If a user wants ₦1,000 of power, and fee is ₦100, they are charged ₦1,100.
    """
    fee_type = electricity_pricing_config.FEE_TYPE.lower()
    fee_value = electricity_pricing_config.FEE_VALUE

    if fee_type == "fixed":
        final_cost = user_requested_amount + fee_value
    else:  # percentage markup rule execution
        final_cost = user_requested_amount + (user_requested_amount * fee_value)

    return float(math.ceil(final_cost))


def calculate_convenience_fee(user_requested_amount: float) -> float:
    """
    Isolates and returns only the calculated fee (convenience fee) for ledger auditing.
    """
    fee_type = electricity_pricing_config.FEE_TYPE.lower()
    fee_value = electricity_pricing_config.FEE_VALUE

    if fee_type == "fixed":
        return float(fee_value)
    else:
        return float(math.ceil(user_requested_amount * fee_value))