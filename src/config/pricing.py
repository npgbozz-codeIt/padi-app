# src/config/pricing.py
from pydantic_settings import BaseSettings


class PricingSettings(BaseSettings):
    # Tier 1: Micro bundles (Cost below ₦1,500)
    TIER_1_MAX: float = 1500.0
    TIER_1_MARGIN_TYPE: str = "fixed"  # 'fixed' or 'percentage'
    TIER_1_MARGIN: float = 35.0  # Add flat ₦35

    # Tier 2: Mid-range bundles (Cost between ₦1,500 and ₦4,999)
    TIER_2_MAX: float = 5000.0
    TIER_2_MARGIN_TYPE: str = "percentage"  # 'fixed' or 'percentage'
    TIER_2_MARGIN: float = 0.05  # Add 5% profit markup

    # Tier 3: Premium bundles (Cost ₦5,000 and above)
    TIER_3_MARGIN_TYPE: str = "percentage"
    TIER_3_MARGIN: float = 0.08  # Add 8% profit markup


pricing_config = PricingSettings()
