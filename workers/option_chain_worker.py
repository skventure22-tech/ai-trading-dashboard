#!/usr/bin/env python3
"""
Render Background Worker – Option Chain Publisher (FINAL)

- SIM_MODE / LIVE_MODE switch
- Posts option-chain snapshots to PHP API
- Zero port binding (Render worker-safe)
"""

import os
import time
import json
import math
import logging
import requests
from typing import List, Dict

# =========================
# ENV CONFIG (Render)
# =========================
SERVER_API = os.getenv(
    "SNAPSHOT_POST_URL",
    "https://surgialgo.shop/api/receive_oc_snapshot.php"
)

API_WRITE_TOKEN = os.getenv("API_WRITE_TOKEN", "")
SIM_MODE = os.getenv("SIM_MODE", "1") == "1"
POLL_INTERVAL = int(os.getenv("OC_POLL_INTERVAL", "2"))

UNDERLYING_ID = int(os.getenv("UNDERLYING_ID", "1"))   # NIFTY
EXPIRY_DATE = os.getenv("EXPIRY_DATE", "2025-12-09")
STRIKE_STEP = int(os.getenv("STRIKE_STEP", "50"))
STRIKE_RANGE = int(os.getenv("STRIKE_RANGE", "500"))

# =========================
# LOGGING
# =========================
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("OC_WORKER")

HEADERS = {
    "Content-Type": "application/json",
    "X-API-KEY": API_WRITE_TOKEN
}

# =========================
# SIM OPTION CHAIN
# =========================
def fetch_option_chain_sim() -> Dict:
    spot = 26186.45
    atm = round(spot / STRIKE_STEP) * STRIKE_STEP

    rows: List[Dict] = []

    for strike in range(atm - STRIKE_RANGE, atm + STRIKE_RANGE + STRIKE_STEP, STRIKE_STEP):
        rows.append({
            "strike_price": strike,
            "option_type": "CE",
            "ltp": round(max(5, abs(spot - strike) * 0.45), 2),
            "oi": 100000 + abs(atm - strike) * 10
        })
        rows.append({
            "strike_price": strike,
            "option_type": "PE",
            "ltp": round(max(5, abs(spot - strike) * 0.45), 2),
            "oi": 120000 + abs(atm - strike) * 12
        })

    return {
        "underlying_id": UNDERLYING_ID,
        "expiry_date": EXPIRY_DATE,
        "underlying_price": spot,
        "rows": rows
    }

# =========================
# MAIN LOOP
# =========================
def main():
    LOG.info("🚀 Option Chain Worker started | SIM_MODE=%s", SIM_MODE)

    while True:
        try:
            payload = fetch_option_chain_sim()

            r = requests.post(
                SERVER_API,
                headers=HEADERS,
                data=json.dumps(payload),
                timeout=10
            )

            LOG.info("POST %s → %s", r.status_code, r.text[:200])

        except Exception as e:
            LOG.error("Worker error: %s", e)

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
