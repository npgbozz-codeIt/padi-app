# src/config/electricity_pricing.py
import os


class ElectricityPricingConfig:
    """
    Independent configuration namespace for handling utility billing markups.
    """
    # Options: 'fixed' (flat fee added) or 'percentage' (additional percentage)
    FEE_TYPE: str = os.getenv("ELECT_FEE_TYPE", "fixed")
    
    # The actual cost applied to the retail transaction
    FEE_VALUE: float = float(os.getenv("ELECT_FEE_VALUE", "100.00"))


electricity_pricing_config = ElectricityPricingConfig()