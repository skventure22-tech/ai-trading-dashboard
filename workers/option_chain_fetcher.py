#!/usr/bin/env python3
"""
Option Chain Background Worker
- SIM MODE (safe)
- Posts option chain snapshots to PHP API
- Designed for Railway / Render / VM / cron
"""

import time
import json
import os
import requests
from datetime import datetime

# ================= CONFIG =================

PHP_RECEIVE_URL = os.getenv(
    "SNAPSHOT_POST_URL",
    "https://surgialgo.shop/api/receive_oc_snapshot.php"
)

API_WRITE_TOKEN = os.getenv("API_WRITE_TOKEN")

if not API_WRITE_TOKEN:
    raise RuntimeError("❌ API_WRITE_TOKEN not set in environment")

SIM_MODE = os.getenv("SIM_MODE", "1") == "1"
POLL_INTERVAL = int(os.getenv("OC_POLL_INTERVAL", "3"))

UNDERLYING_ID = int(os.getenv("UNDERLYING_ID", "1"))   # 1 = NIFTY
EXPIRY_DATE = os.getenv("EXPIRY_DATE", "2025-12-09")
STRIKE_STEP = int(os.getenv("STRIKE_STEP", "50"))

# ================= SIM OPTION CHAIN =================

def fetch_option_chain_sim():
    spot = 26186.45
    atm = round(spot / STRIKE_STEP) * STRIKE_STEP
    rows = []

    for strike in range(atm - 150, atm + 200, STRIKE_STEP):
        ce_ltp = round(max(5, abs(spot - strike) * 0.45), 2)
        pe_ltp = round(max(5, abs(spot - strike) * 0.45), 2)

        rows.append({
            "strike_price": strike,
            "option_type": "CE",
            "ltp": ce_ltp,
            "oi": 100000 + abs(atm - strike) * 10
        })

        rows.append({
            "strike_price": strike,
            "option_type": "PE",
            "ltp": pe_ltp,
            "oi": 120000 + abs(atm - strike) * 12
        })

    return {
        "underlying_id": UNDERLYING_ID,
        "expiry_date": EXPIRY_DATE,
        "underlying_price": spot,
        "rows": rows
    }

# ================= MAIN LOOP =================

def main():
    print("🚀 Option Chain Worker STARTED")
    print("📡 Posting to:", PHP_RECEIVE_URL)
    print("⏱ Poll interval:", POLL_INTERVAL, "seconds")

    headers = {
        "X-API-KEY": API_WRITE_TOKEN,
        "Content-Type": "application/json"
    }

    while True:
        try:
            if SIM_MODE:
                payload = fetch_option_chain_sim()
            else:
                # Future: Angel One LIVE fetch
                continue

            r = requests.post(
                PHP_RECEIVE_URL,
                headers=headers,
                data=json.dumps(payload),
                timeout=15
            )

            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] POST {r.status_code} → {r.text}")

        except Exception as e:
            print("❌ ERROR:", str(e))

        time.sleep(POLL_INTERVAL)

# ================= ENTRY =================

if __name__ == "__main__":
    main()
