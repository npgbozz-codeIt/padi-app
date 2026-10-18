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
    Uses batch retrieval to eliminate N+1 database queries.
    """
    logger.info("🔄 Starting background synchronization for Bigisub data plans...")

    # 1. Fetch live plans from vendor API
    api_res = await bigisub_client.fetch_live_data_plans()
    if not api_res.get("success"):
        logger.error(f"❌ Aborted sync task. Vendor error: {api_res.get('error')}")
        return {"success": False, "error": api_res.get("error")}

    raw_plans = api_res.get("plans", [])
    if not raw_plans:
        return {"success": True, "inserted": 0, "updated": 0}

    # 2. Batch fetch existing cached plans to memory (O(1) lookups)
    stmt = select(DataPlan)
    db_result = await db.execute(stmt)
    existing_plans_map = {
        plan.vendor_plan_id: plan for plan in db_result.scalars().all()
    }

    updated_count = 0
    inserted_count = 0

    # 3. Synchronize in memory
    for plan in raw_plans:
        v_id = plan.get("id")
        wholesale_cost = float(plan.get("amount", 0.0))
        calculated_retail = calculate_retail_price(wholesale_cost)

        existing_plan = existing_plans_map.get(v_id)

        if existing_plan:
            existing_plan.wholesale_amount = wholesale_cost
            existing_plan.retail_amount = calculated_retail
            existing_plan.plan_disabled = plan.get("plan_disabled", False)
            existing_plan.size = str(plan.get("size", "N/A"))
            existing_plan.validity = plan.get("validity", "30 days")
            updated_count += 1
        else:
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