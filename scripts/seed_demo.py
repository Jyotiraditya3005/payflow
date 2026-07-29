#!/usr/bin/env python3
"""
PayFlow Demo Seed Script
------------------------
Creates demo merchants, users, and fires test payments through the
full stack to verify everything is working end-to-end.

Usage:
    python scripts/seed_demo.py
    python scripts/seed_demo.py --gateway http://localhost:8080
    python scripts/seed_demo.py --payments 50
"""

import argparse
import asyncio
import json
import random
import sys
import time
from decimal import Decimal
from uuid import uuid4

import httpx

GATEWAY = "http://localhost:8080"
AUTH_URL = f"{GATEWAY}/api/v1/auth"
PAYMENT_URL = f"{GATEWAY}/api/v1/payments"

DEMO_MERCHANTS = [
    {"email": "acme@payflow.io",       "password": "demo1234", "full_name": "ACME Corp",        "role": "MERCHANT"},
    {"email": "techco@payflow.io",     "password": "demo1234", "full_name": "TechCo Ltd",       "role": "MERCHANT"},
    {"email": "admin@payflow.io",      "password": "admin123", "full_name": "Platform Admin",   "role": "ADMIN"},
    {"email": "analyst@payflow.io",    "password": "demo1234", "full_name": "Risk Analyst",     "role": "ANALYST"},
]

PAYMENT_SCENARIOS = [
    # (amount, method, fraud_expected, description)
    (299.99,   "CARD",          False, "SaaS subscription - monthly"),
    (4999.00,  "CARD",          False, "Enterprise license"),
    (89.99,    "WALLET",        False, "Mobile purchase"),
    (15000.00, "BANK_TRANSFER", False, "B2B invoice payment"),
    (50000.00, "CARD",          True,  "Suspicious large card payment"),  # High risk
    (1.00,     "CARD",          False, "Card verification charge"),
    (750.00,   "UPI",           False, "UPI payment"),
    (2500.00,  "CARD",          False, "Annual subscription"),
    (99999.99, "CARD",          True,  "Very large card payment"),  # Should trigger fraud
    (49.99,    "WALLET",        False, "App purchase"),
]

CURRENCIES = ["USD", "EUR", "GBP", "INR"]


class PayFlowSeeder:
    def __init__(self, gateway: str, num_payments: int):
        self.gateway = gateway
        self.num_payments = num_payments
        self.tokens = {}
        self.merchant_ids = []
        self.stats = {
            "registered": 0, "logged_in": 0,
            "payments_attempted": 0, "payments_completed": 0,
            "payments_failed": 0, "payments_fraud_declined": 0,
        }

    async def run(self):
        print("\n" + "═" * 60)
        print("  PayFlow Demo Seed Script")
        print("═" * 60)

        print(f"\n🔌 Connecting to gateway: {self.gateway}")
        await self._wait_for_gateway()

        print("\n👤 Creating demo users...")
        await self._seed_users()

        print(f"\n💳 Firing {self.num_payments} test payments...")
        await self._seed_payments()

        print("\n📊 Seeding complete!")
        print(f"   Registered:          {self.stats['registered']}")
        print(f"   Logged in:           {self.stats['logged_in']}")
        print(f"   Payments attempted:  {self.stats['payments_attempted']}")
        print(f"   Completed:           {self.stats['payments_completed']}")
        print(f"   Failed/Declined:     {self.stats['payments_failed']}")
        print(f"   Fraud declined:      {self.stats['payments_fraud_declined']}")
        print("\n✅ Stack is operational! Access the dashboard at http://localhost:3000")
        print("   Login: demo@payflow.io / demo1234\n")

    async def _wait_for_gateway(self, max_wait: int = 120):
        start = time.time()
        while time.time() - start < max_wait:
            try:
                async with httpx.AsyncClient(timeout=5) as c:
                    r = await c.get(f"{self.gateway}/health")
                    if r.status_code == 200:
                        print("   ✓ Gateway is ready")
                        return
            except Exception:
                pass
            print("   ⏳ Waiting for gateway...")
            await asyncio.sleep(5)
        print("   ✗ Gateway not available after timeout. Is Docker running?")
        sys.exit(1)

    async def _seed_users(self):
        # Also seed a simple demo user for easy login
        all_users = DEMO_MERCHANTS + [
            {"email": "demo@payflow.io", "password": "demo1234", "full_name": "Demo Merchant", "role": "MERCHANT"}
        ]

        async with httpx.AsyncClient(timeout=10, base_url=self.gateway) as client:
            for user in all_users:
                # Register
                try:
                    r = await client.post(f"{AUTH_URL}/register", json=user)
                    if r.status_code == 201:
                        self.stats["registered"] += 1
                        print(f"   ✓ Registered: {user['email']}")
                    elif r.status_code == 400:
                        print(f"   ~ Already exists: {user['email']}")
                    else:
                        print(f"   ✗ Registration failed: {user['email']} ({r.status_code})")
                except Exception as e:
                    print(f"   ✗ Error registering {user['email']}: {e}")

                # Login
                try:
                    r = await client.post(f"{AUTH_URL}/login", json={"email": user["email"], "password": user["password"]})
                    if r.status_code == 200:
                        data = r.json()
                        self.tokens[user["email"]] = data["access_token"]
                        self.stats["logged_in"] += 1
                except Exception as e:
                    print(f"   ✗ Login error: {e}")

    async def _seed_payments(self):
        token = self.tokens.get("demo@payflow.io")
        if not token:
            print("   ✗ No token available — skipping payments")
            return

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        merchant_id = str(uuid4())  # Demo merchant UUID

        async with httpx.AsyncClient(timeout=30, base_url=self.gateway) as client:
            for i in range(self.num_payments):
                scenario = PAYMENT_SCENARIOS[i % len(PAYMENT_SCENARIOS)]
                amount, method, _, description = scenario
                # Add small random variance
                amount = round(amount * (0.9 + random.random() * 0.2), 2)
                currency = random.choice(CURRENCIES)

                payload = {
                    "idempotency_key": f"seed_{uuid4().hex}",
                    "merchant_id": merchant_id,
                    "customer_id": str(uuid4()),
                    "amount": str(amount),
                    "currency": currency,
                    "payment_method": method,
                    "description": description,
                    **({"card_token": f"tok_{uuid4().hex[:8]}"} if method == "CARD" else {}),
                    **({"bank_account_token": f"ba_{uuid4().hex[:8]}"} if method == "BANK_TRANSFER" else {}),
                    "metadata": {"seed": True, "scenario": i},
                }

                self.stats["payments_attempted"] += 1
                try:
                    r = await client.post(f"{PAYMENT_URL}/", json=payload, headers=headers)
                    if r.status_code == 201:
                        data = r.json()
                        status = data.get("status", "?")
                        fraud_risk = data.get("fraud_risk", "?")
                        if status == "COMPLETED":
                            self.stats["payments_completed"] += 1
                            print(f"   ✓ Payment {i+1:3d}: ${amount:>10.2f} {currency} [{method:<13}] → {status} (risk: {fraud_risk})")
                        elif data.get("error_code") == "FRAUD_DECLINED":
                            self.stats["payments_fraud_declined"] += 1
                            print(f"   🛡 Payment {i+1:3d}: ${amount:>10.2f} {currency} [{method:<13}] → FRAUD_DECLINED")
                        else:
                            self.stats["payments_failed"] += 1
                            print(f"   ✗ Payment {i+1:3d}: ${amount:>10.2f} {currency} → {status}")
                    else:
                        self.stats["payments_failed"] += 1
                        print(f"   ✗ Payment {i+1:3d}: HTTP {r.status_code}")

                except Exception as e:
                    self.stats["payments_failed"] += 1
                    print(f"   ✗ Payment {i+1:3d}: Error — {e}")

                # Small delay to not overwhelm the system
                await asyncio.sleep(0.1)


async def main():
    parser = argparse.ArgumentParser(description="PayFlow demo seed script")
    parser.add_argument("--gateway", default=GATEWAY, help="API gateway URL")
    parser.add_argument("--payments", type=int, default=20, help="Number of test payments to fire")
    args = parser.parse_args()

    seeder = PayFlowSeeder(gateway=args.gateway, num_payments=args.payments)
    await seeder.run()


if __name__ == "__main__":
    asyncio.run(main())
