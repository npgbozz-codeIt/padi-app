import asyncio
from unittest.mock import AsyncMock, patch
from src.services.orchestrator import process_user_vending_intent
from src.services.bigisub import bigisub_client


async def run_tests():
    print("==========================================")
    print("🧪 TESTING MYPADI CONVERSION STRATEGIES")
    print("==========================================")

    # 1. Test Airtime Quote & Execution
    print("\n[1/3] Testing Airtime Strategy...")
    with patch.object(
        bigisub_client,
        "vend_airtime",
        new=AsyncMock(
            return_value={
                "success": True,
                "transaction_id": "TX_AIRTIME_123",
                "message": "Airtime purchase successful",
            }
        ),
    ):
        airtime_res = await process_user_vending_intent(
            conversion_type="airtime",
            user_id="user_001",
            amount=200.0,
            destination="08031234567",
        )
        print("  Summary Quote:", airtime_res["quote"].summary_text)
        print("  Status Success:", airtime_res["success"])
        assert airtime_res["success"] is True

    # 2. Test Data Quote & Execution
    print("\n[2/3] Testing Data Strategy...")
    with patch.object(
        bigisub_client,
        "vend_data",
        new=AsyncMock(
            return_value={
                "success": True,
                "transaction_id": "TX_DATA_456",
                "message": "Data purchase successful",
            }
        ),
    ):
        data_res = await process_user_vending_intent(
            conversion_type="data",
            user_id="user_001",
            amount=500.0,
            destination="08031234567",
            plan_id=12,
            plan_name="1GB SME",
        )
        print("  Summary Quote:", data_res["quote"].summary_text)
        print("  Status Success:", data_res["success"])
        assert data_res["success"] is True

    # 3. Test Electricity Meter Verification & Quote
    print("\n[3/3] Testing Electricity Strategy...")
    with patch.object(
        bigisub_client,
        "verify_electricity_meter",
        new=AsyncMock(
            return_value={
                "success": True,
                "customer_name": "JOHN DOE",
                "address": "123 TEST ST",
                "error": None,
            }
        ),
    ), patch.object(
        bigisub_client,
        "vend_electricity",
        new=AsyncMock(
            return_value={
                "success": True,
                "transaction_id": "TX_ELEC_789",
                "token": "1234-5678-9012-3456",
                "units": "45.2 kWh",
            }
        ),
    ):
        elec_res = await process_user_vending_intent(
            conversion_type="electricity",
            user_id="user_001",
            amount=2000.0,
            destination="11112222333",
            disco="aedc",
        )
        print("  Summary Quote:", elec_res["quote"].summary_text)
        print("  Status Success:", elec_res["success"])
        assert elec_res["success"] is True

    print("\n✅ All conversion strategies passed verification successfully!")


if __name__ == "__main__":
    asyncio.run(run_tests())