# test_bigisub.py
import asyncio
from dotenv import load_dotenv

load_dotenv()

from src.services.bigisub import bigisub_client


async def verify_connection():
    print("🔄 Initializing authentication request loop to Bigisub API v2...")
    balance = await bigisub_client.get_merchant_balance()

    if balance is not None:
        print(
            f"✅ Connection Established! Your Current API Merchant Balance is: ₦{balance}"
        )
    else:
        print(
            "❌ Auth link failed. Double-check username/password configs inside .env file."
        )


if __name__ == "__main__":
    asyncio.run(verify_connection())
