# src/services/plan_sync.py
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.services.bigisub import bigisub_client
from src.models.data_plan import DataPlan
from src.utils.margin_calculator import calculate_retail_price

logger = logging.getLogger(__name__)


async def sync_data_plans_to_db(db: AsyncSession) -> dict:
    """
    Background worker that updates the data_plans cache table from Bigisub API.
    Calculates retail prices automatically using the dynamic margin calculator matrix.
    """
    logger.info("🔄 Starting background synchronization for Bigisub data plans...")

    # 1. Fetch live plans from vendor API
    api_res = await bigisub_client.fetch_live_data_plans()
    if not api_res.get("success"):
        logger.error(f"❌ Aborted sync task. Vendor error: {api_res.get('error')}")
        return {"success": False, "error": api_res.get("error")}

    raw_plans = api_res.get("plans", [])
    updated_count = 0
    inserted_count = 0

    # 2. Process plans line by line
    for plan in raw_plans:
        v_id = plan.get("id")
        wholesale_cost = float(plan.get("amount", 0.0))

        # Calculate localized retail price via your tiered markup engine
        calculated_retail = calculate_retail_price(wholesale_cost)

        # 3. Look up if the plan is already cached locally
        stmt = select(DataPlan).where(DataPlan.vendor_plan_id == v_id)
        result = await db.execute(stmt)
        existing_plan = result.scalars().first()

        if existing_plan:
            # Update attributes to match upstream status configurations
            existing_plan.wholesale_amount = wholesale_cost
            existing_plan.retail_amount = calculated_retail
            existing_plan.plan_disabled = plan.get("plan_disabled", False)
            existing_plan.size = str(plan.get("size", "N/A"))
            existing_plan.validity = plan.get("validity", "30 days")
            updated_count += 1
        else:
            # Create a brand new caching matrix row
            new_cache_row = DataPlan(
                vendor_plan_id=v_id,
                network_id=int(plan.get("network", 1)),
                network_name=str(plan.get("network_name", "UNKNOWN")),
                plan_type=str(plan.get("plantype", "SME")),
                size=str(plan.get("size", "N/A")),
                validity=plan.get("validity", "30 days"),
                wholesale_amount=wholesale_cost,
                retail_amount=calculated_retail,
                plan_disabled=plan.get("plan_disabled", False),
            )
            db.add(new_cache_row)
            inserted_count += 1

    await db.commit()
    logger.info(
        f"🎉 Sync Complete! Inserted: {inserted_count}, Updated: {updated_count} rows."
    )
    return {"success": True, "inserted": inserted_count, "updated": updated_count}
