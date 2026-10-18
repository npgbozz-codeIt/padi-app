# test_nlu_orchestrator.py
import asyncio
import logging

from src.services.bigisub import bigisub_client
from src.services.nlu_router import handle_user_text_request

logging.basicConfig(level=logging.INFO)


async def run_tests():
    test_prompts = [
        "Send 100 naira airtime to 09131330877",
        "Buy 2000 AEDC electricity for meter 11112222333",
        "Hello my padi",
    ]

    user_id = "test_user_001"

    print("\n================ STARTING NLU & ORCHESTRATOR TESTS ================\n")

    for prompt in test_prompts:
        print(f"💬 User Prompt: '{prompt}'")
        res = await handle_user_text_request(
            user_id=user_id, user_text=prompt, execute=False
        )

        action = res.get("action", "None")
        resp_type = res.get("response_type", "None")
        success = res.get("success", False)

        print(f"Action Detected: {action}")
        print(f"Response Type: {resp_type}")
        print(f"Success: {success}")

        if resp_type == "vending_quote":
            details = res.get("details", {})
            if details.get("success"):
                print(f"Quote Summary: {details.get('quote')}")
                print(f"Metadata: {details.get('metadata')}\n")
            else:
                print(f"Quote Failed: {details.get('error')}\n")
        elif resp_type == "text":
            print(f"Message: {res.get('message')}\n")
        elif resp_type == "missing_param":
            print(
                f"Missing Param: {res.get('missing_param')} -> {res.get('message')}\n"
            )
        else:
            print(f"Raw Result: {res}\n")

    # Close HTTP connection pool cleanly
    await bigisub_client.close()
    print("================ TESTS COMPLETED ================\n")


if __name__ == "__main__":
    asyncio.run(run_tests())