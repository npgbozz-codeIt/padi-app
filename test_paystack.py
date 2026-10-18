# test_paystack.py
import os
import asyncio
import httpx
from dotenv import load_dotenv

# Explicitly load .env from the src directory
load_dotenv("src/.env")

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "").strip().strip('"').strip("'")
BASE_URL = "https://api.paystack.co"

print(f"DEBUG: RAW_KEY from env -> {repr(os.getenv('PAYSTACK_SECRET_KEY'))}")
print(f"DEBUG: CLEANED_KEY -> {repr(PAYSTACK_SECRET_KEY[:10])}... (Length: {len(PAYSTACK_SECRET_KEY)})")

headers = {
    "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
    "Content-Type": "application/json",
}

async def run_paystack_diagnostics():
    print("=" * 60)
    print("🧪 PAYSTACK API DIAGNOSTIC SUITE")
    print("=" * 60)

    if not PAYSTACK_SECRET_KEY:
        print("❌ ERROR: PAYSTACK_SECRET_KEY is empty! Check src/.env formatting.")
        return

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Test 1: Balance / Key Validation Endpoint
        print("\n1️⃣ Testing Key Validity (/balance)...")
        try:
            res = await client.get(f"{BASE_URL}/balance", headers=headers)
            print(f"   Status Code: {res.status_code}")
            print(f"   Response: {res.json()}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 2: Initialize Checkout Transaction Link
        print("\n2️⃣ Testing Payment Link Generation (/transaction/initialize)...")
        try:
            payload = {"email": "test_padi@mypadi.app", "amount": 100000}  # ₦1,000.00
            res = await client.post(f"{BASE_URL}/transaction/initialize", json=payload, headers=headers)
            print(f"   Status Code: {res.status_code}")
            data = res.json()
            if data.get("status"):
                print(f"   ✅ Authorization URL: {data['data']['authorization_url']}")
            else:
                print(f"   ❌ Message: {data.get('message')}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test 3: BVN Verification Endpoint
        print("\n3️⃣ Testing BVN Verification (/bank/resolve_bvn/22515737611)...")
        try:
            res = await client.get(f"{BASE_URL}/bank/resolve_bvn/22515737611", headers=headers)
            print(f"   Status Code: {res.status_code}")
            print(f"   Response: {res.json()}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(run_paystack_diagnostics())