# test_webhook.py
import asyncio
import random
from httpx import AsyncClient, ASGITransport
from dotenv import load_dotenv

load_dotenv()

from src.main import app


async def test_padi_chatbot_flow():
    print("\n🚀 Starting Stage 2.5 Async Multi-Step Onboarding Test Cycle...")

    # Generate a unique mock platform ID for this lifecycle run
    mock_telegram_id = random.randint(100000000, 999999999)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:

        # ----------------------------------------------------
        # STEP 1: INITIAL HIT (UNREGISTERED -> AWAITING_LANGUAGE)
        # ----------------------------------------------------
        print(
            f"\n[Step 1] Posting initial message from new user ({mock_telegram_id})..."
        )
        payload = {
            "update_id": 100001,
            "message": {
                "message_id": 5001,
                "from": {
                    "id": mock_telegram_id,
                    "is_bot": False,
                    "first_name": "IdreezTest",
                    "username": "tester_padi",
                },
                "date": 1719504000,
                "text": "Hello",
            },
        }
        res = await client.post("/webhook/telegram", json=payload)
        print(f"Response: {res.json()}")
        # Change this line in Step 1 of test_webhook.py:
        assert (
            res.status_code == 200
        )  # HTTP status wrapper code enforced by FastAPI decorator
        assert res.json()["success"] == 201  # Inner transactional dictionary code
        assert res.json()["status"] == "user created successfully"

        # ----------------------------------------------------
        # STEP 2: SELECT LANGUAGE (AWAITING_LANGUAGE -> AWAITING_PHONE)
        # ----------------------------------------------------
        print("\n[Step 2] Sending preferred language selection ('pidgin')...")
        payload["message"]["text"] = "pidgin"
        payload["message"]["message_id"] += 1

        res = await client.post("/webhook/telegram", json=payload)
        print(f"Response: {res.json()}")
        assert res.json()["status"] == "onboarding_progress"
        assert res.json()["steps"] == "phone_number_request"

        # ----------------------------------------------------
        # STEP 3: SHARE PHONE NUMBER (AWAITING_PHONE -> AWAITING_BVN)
        # ----------------------------------------------------
        print("\n[Step 3] Simulating contact card phone number sharing...")
        payload["message"]["text"] = None
        payload["message"]["message_id"] += 1
        payload["message"]["contact"] = {
            "phone_number": "+2348031234567",
            "first_name": "IdreezTest",
            "user_id": mock_telegram_id,
        }

        res = await client.post("/webhook/telegram", json=payload)
        print(f"Response: {res.json()}")
        assert res.json()["status"] == "onboarding_progress"
        assert res.json()["steps"] == "bvn_verification"

        # ----------------------------------------------------
        # STEP 4: PROVIDE BVN (AWAITING_BVN -> AWAITING_PIN)
        # ----------------------------------------------------
        print("\n[Step 4] Sending 11-digit BVN verification text...")
        payload["message"]["contact"] = None  # Clear contact card
        payload["message"]["text"] = "22233344455"
        payload["message"]["message_id"] += 1

        res = await client.post("/webhook/telegram", json=payload)
        print(f"Response: {res.json()}")
        assert res.json()["status"] == "onboarding_progress"
        assert res.json()["steps"] == "transaction_pin_creation"

        # ----------------------------------------------------
        # STEP 5: CREATE PIN (AWAITING_PIN -> AWAITING_PIN_CONFIRMATION)
        # ----------------------------------------------------
        print("\n[Step 5] Sending initial 4-digit transaction PIN setup...")
        payload["message"]["text"] = "1234"
        payload["message"]["message_id"] += 1

        res = await client.post("/webhook/telegram", json=payload)
        print(f"Response: {res.json()}")
        assert res.json()["status"] == "onboarding_progress"
        assert res.json()["steps"] == "transaction_pin_confirmation"

        # ----------------------------------------------------
        # STEP 6: CONFIRM PIN (AWAITING_PIN_CONFIRMATION -> COMPLETED)
        # ----------------------------------------------------
        print("\n[Step 6] Confirming the matching 4-digit transaction PIN...")
        payload["message"]["text"] = "1234"
        payload["message"]["message_id"] += 1

        res = await client.post("/webhook/telegram", json=payload)
        print(f"Response: {res.json()}")
        assert res.json()["status"] == "onboarding_complete"

        # ----------------------------------------------------
        # STEP 7: FULL TRANSACTION NLU ENGINE (COMPLETED STATE)
        # ----------------------------------------------------
        print(
            "\n[Step 7] Testing fully onboarded transactional NLU airtime intent & slot path..."
        )
        payload["message"]["text"] = "I wan buy MTN 500 airtime"
        payload["message"]["message_id"] += 1

        res = await client.post("/webhook/telegram", json=payload)
        print(f"Response: {res.json()}")
        assert res.status_code == 200
        assert res.json()["status"] == "user is verified and active"
        assert "intent_analysis" in res.json()
        assert "extracted_slots" in res.json()

        print(
            "\n🏆 ALL STEPS PASSED! The onboarding state machine and slot engine are fully operational."
        )


if __name__ == "__main__":
    asyncio.run(test_padi_chatbot_flow())
