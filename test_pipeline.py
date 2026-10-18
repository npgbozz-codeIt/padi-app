# test_pipeline.py
import asyncio
import logging
from src.services.bigisub import bigisub_client
from src.services.pipeline import handle_incoming_user_message
from src.services.state_manager import state_manager

logging.basicConfig(level=logging.INFO)


async def run_pipeline_tests():
    user_id = "telegram_test_user_777"

    print("\n================ STARTING MULTI-TURN PIPELINE TESTS ================\n")

    # -------------------------------------------------------------------------
    # TEST CASE 1: Airtime Quote -> Confirmation (YES)
    # -------------------------------------------------------------------------
    print("--- Test 1: Request Quote -> Send YES ---")

    # Step 1A: Prompt for quote
    msg_1 = "Send 100 naira airtime to 09131330877"
    print(f"💬 User: '{msg_1}'")
    res_1 = await handle_incoming_user_message(user_id, msg_1)
    print(f"🤖 Bot Status: {res_1.get('status')}")
    print(f"🤖 Bot Message:\n{res_1.get('message')}\n")

    # Inspect Redis State
    session = await state_manager.get_session(user_id)
    print(f"🔍 Redis Session State: {session.get('state') if session else 'None'}\n")

    # Step 1B: Send Confirmation 'YES'
    msg_2 = "YES"
    print(f"💬 User: '{msg_2}'")
    res_2 = await handle_incoming_user_message(user_id, msg_2)
    print(f"🤖 Bot Status: {res_2.get('status')}")
    print(f"🤖 Bot Message:\n{res_2.get('message')}\n")

    # Inspect Redis State (Should be cleared)
    session_after = await state_manager.get_session(user_id)
    print(
        f"🔍 Redis Session After Confirm: {session_after.get('state') if session_after else 'Cleared'}\n"
    )

    # -------------------------------------------------------------------------
    # TEST CASE 2: Electricity Quote -> Cancellation (NO)
    # -------------------------------------------------------------------------
    print("--- Test 2: Electricity Quote -> Send NO ---")

    # Step 2A: Prompt for quote
    msg_3 = "Buy 1000 AEDC electricity for meter 11112222333"
    print(f"💬 User: '{msg_3}'")
    res_3 = await handle_incoming_user_message(user_id, msg_3)
    print(f"🤖 Bot Status: {res_3.get('status')}")
    print(f"🤖 Bot Message:\n{res_3.get('message')}\n")

    # Step 2B: Send Cancellation 'NO'
    msg_4 = "NO"
    print(f"💬 User: '{msg_4}'")
    res_4 = await handle_incoming_user_message(user_id, msg_4)
    print(f"🤖 Bot Status: {res_4.get('status')}")
    print(f"🤖 Bot Message:\n{res_4.get('message')}\n")

    # -------------------------------------------------------------------------
    # CLEANUP CONNECTIONS
    # -------------------------------------------------------------------------
    await state_manager.close()
    await bigisub_client.close()
    print("================ TESTS COMPLETED ================\n")


if __name__ == "__main__":
    asyncio.run(run_pipeline_tests())