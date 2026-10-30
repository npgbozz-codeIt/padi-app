# src/config/cable_pricing.py
import os


class CablePricingConfig:
    """
    Independent configuration namespace for handling Cable TV subscription markups and convenience fees.
    """
    # Options: 'fixed' (flat fee added) or 'percentage' (additional percentage)
    FEE_TYPE: str = os.getenv("CABLE_FEE_TYPE", "fixed")

    # The actual convenience fee applied to the retail transaction
    FEE_VALUE: float = float(os.getenv("CABLE_FEE_VALUE", "100.00"))


cable_pricing_config = CablePricingConfig()
