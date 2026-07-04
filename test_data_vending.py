# test_data_vending.py
import asyncio
import logging
from src.services.bigisub import bigisub_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_unified_data_test():
    logger.info("📡 1. TESTING GET DATA PLANS LIST...")

    # Fetch only MTN plans (network 1) to keep the terminal output clean
    plan_list_res = await bigisub_client.fetch_live_data_plans(network_id=2)

    if not plan_list_res.get("success"):
        logger.error(f"❌ Failed to fetch plans: {plan_list_res.get('error')}")
        return

    plans = plan_list_res.get("plans", [])
    logger.info(f"🎉 Successfully fetched {len(plans)} MTN data plans from Bigisub!")

    if plans:
        sample_plan = plans[0]
        logger.info(
            f"💡 Sample Plan Details parsed -> ID: {sample_plan.get('id')}, Size: {sample_plan.get('size')}, Cost: ₦{sample_plan.get('amount')}"
        )

        # Grab the real dynamic ID from the top of the list for our next test step
        target_plan_id = sample_plan.get("id")
    else:
        target_plan_id = 135  # Fallback placeholder if no plans return

    logger.info("\n🚀 2. TESTING POST DATA PURCHASE INJECTOR...")
    test_phone = "08012345678"
    test_network = "mtn"

    result = await bigisub_client.vend_data(
        phone=test_phone, plan_id=int(target_plan_id), network=test_network
    )

    logger.info("\n==========================================")
    logger.info("📡 LIVE API PURCHASE RESPONSE:")
    logger.info("==========================================")
    logger.info(f"Success Status: {result.get('success')}")
    logger.info(f"Returned Error: {result.get('error')}")
    logger.info(f"Message: {result.get('message')}")
    logger.info("==========================================\n")


if __name__ == "__main__":
    asyncio.run(run_unified_data_test())
