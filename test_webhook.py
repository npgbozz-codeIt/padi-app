import asyncio
import random
from httpx import AsyncClient, ASGITransport
from dotenv import load_dotenv

# Load your environment variables first
load_dotenv()

from src.main import app


async def test_padi_chatbot_flow():
    print("\n🚀 Starting Stage 2.5 Async Integration Testing Cycle...")

    # Generate a random mock platform ID for testing
    mock_telegram_id = random.randint(100000000, 999999999)

    # Initialize the correct asynchronous testing client transport layer
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:

        # ----------------------------------------------------
        # TEST 1: SIMULATING AN UNREGISTERED USER SIGNUP
        # ----------------------------------------------------
        print(
            f"\n[Test 1] Posting new user update (ID: {mock_telegram_id}) to webhook..."
        )

        onboarding_payload = {
            "update_id": 111111111,
            "message": {
                "message_id": 4501,
                "from": {
                    "id": mock_telegram_id,
                    "is_bot": False,
                    "first_name": "IdreezTest",
                    "username": "npg_bozz_tester",
                },
                "date": 1719504000,
                "text": "Hello, I want to join",
            },
        }

        response_one = await client.post("/webhook/telegram", json=onboarding_payload)
        print(f"Response Status Code: {response_one.status_code}")
        print(f"Response Content: {response_one.json()}")

        assert response_one.status_code == 200 or response_one.status_code == 201
        assert response_one.json()["status"] == "user created successfully"
        print(
            "✅ Test 1 Passed: Automated profile registration and tag creation successful."
        )

        # ----------------------------------------------------
        # TEST 2: SIMULATING A REGISTERED USER NLU INTENT ROUTING
        # ----------------------------------------------------
        print(f"\n[Test 2] Posting an airtime intent message using the SAME user ID...")

        intent_payload = {
            "update_id": 222222222,
            "message": {
                "message_id": 4502,
                "from": {
                    "id": mock_telegram_id,
                    "is_bot": False,
                    "first_name": "IdreezTest",
                    "username": "npg_bozz_tester",
                },
                "date": 1719504100,
                "text": "I wan buy MTN 500 airtime",  # Multi-lingual Nigerian Pidgin Input
            },
        }

        response_two = await client.post("/webhook/telegram", json=intent_payload)
        print(f"Response Status Code: {response_two.status_code}")
        print(f"Response Content: {response_two.json()}")

        assert response_two.status_code == 200
        assert response_two.json()["status"] == "user is registered"
        assert "intent_analysis" in response_two.json()

        extracted_intent = response_two.json()["intent_analysis"]["action"]
        print(f"🎯 LLM Extracted Action Value: {extracted_intent}")
        print(
            "✅ Test 2 Passed: Conversational routing and structured Pydantic extraction successful."
        )


if __name__ == "__main__":
    # Use standard asyncio runner to keep the event loop alive across both requests
    asyncio.run(test_padi_chatbot_flow())
