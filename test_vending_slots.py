# test_vending_slots.py
import asyncio
from dotenv import load_dotenv

load_dotenv()

from src.services.bigisub import bigisub_client


async def run_live_vending_test():
    print("🚀 Triggering dynamic airtime allocation test...")

    # Try passing "Glo" to test our dictionary mapper!
    res = await bigisub_client.vend_airtime(
        phone="07059188019", amount=100, network="Glo"
    )
    print(f"Result: {res}")


if __name__ == "__main__":
    asyncio.run(run_live_vending_test())
