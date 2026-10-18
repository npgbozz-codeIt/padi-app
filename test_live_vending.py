import asyncio
from src.services.orchestrator import process_user_vending_intent

async def test_live():
    phone_number = "09131330877"  # <--- Replace with your real phone number
    amount = 100.0

    print(f"🚀 Dispatching LIVE Airtime request: ₦{amount} to {phone_number}...")

    result = await process_user_vending_intent(
        conversion_type="airtime",
        user_id="live_test_user",
        amount=amount,
        destination=phone_number,
    )

    print("\n--- RESULT ---")
    print("Success:", result.get("success"))
    print("Stage:", result.get("stage"))
    print("Quote Summary:", result.get("quote").summary_text if result.get("quote") else "N/A")
    print("API Response:", result.get("result"))

if __name__ == "__main__":
    asyncio.run(test_live())