#!/usr/bin/env python3
"""
Render Background Worker – Option Chain Publisher (FINAL)

- SIM_MODE supported
- Reads all config from Render ENV
- Posts option chain snapshots to PHP API
- Safe infinite loop (no crash)
"""

import os
import time
import json
import math
import logging
import requests

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
LOG = logging.getLogger("option-chain-worker")

# ================= ENV CONFIG =================
PHP_RECEIVE_URL = os.getenv(
    "SNAPSHOT_POST_URL",
    "https://surgialgo.shop/api/receive_oc_snapshot.php"
)

API_WRITE_TOKEN = os.getenv("API_WRITE_TOKEN", "")
SIM_MODE = os.getenv("SIM_MODE", "1") == "1"
POLL_INTERVAL = int(os.getenv("OC_POLL_INTERVAL", "3"))

UNDERLYING_ID = int(os.getenv("UNDERLYING_ID", "1"))  # NIFTY
EXPIRY_DATE = os.getenv("EXPIRY_DATE", "2025-12-09")
STRIKE_STEP = int(os.getenv("STRIKE_STEP", "50"))
STRIKE_RANGE = int(os.getenv("STRIKE_RANGE", "500"))

HEADERS = {
    "Content-Type": "application/json",
    "X-API-KEY": API_WRITE_TOKEN
}

# ================= SIM OPTION CHAIN =================
def fetch_option_chain_sim():
    spot = 26186.45
    atm = round(spot / STRIKE_STEP) * STRIKE_STEP

    rows = []
    for strike in range(atm - STRIKE_RANGE, atm + STRIKE_RANGE + STRIKE_STEP, STRIKE_STEP):
        diff = abs(spot - strike)

        rows.append({
            "strike_price": strike,
            "option_type": "CE",
            "ltp": round(max(5, diff * 0.45), 2),
            "oi": 100000 + diff * 10
        })

        rows.append({
            "strike_price": strike,
            "option_type": "PE",
            "ltp": round(max(5, diff * 0.45), 2),
            "oi": 120000 + diff * 12
        })

    return {
        "underlying_id": UNDERLYING_ID,
        "expiry_date": EXPIRY_DATE,
        "underlying_price": spot,
        "rows": rows
    }

# ================= POST =================
def post_snapshot(payload: dict):
    try:
        r = requests.post(
            PHP_RECEIVE_URL,
            headers=HEADERS,
            json=payload,
            timeout=10
        )

        if r.status_code != 200:
            LOG.error("POST failed %s | %s", r.status_code, r.text)
            return False

        LOG.info("Snapshot saved | %s", r.json())
        return True

    except Exception as e:
        LOG.error("POST exception: %s", e)
        return False

# ================= MAIN LOOP =================
def main():
    LOG.info("Worker started | SIM_MODE=%s | POLL=%ss", SIM_MODE, POLL_INTERVAL)

    if not API_WRITE_TOKEN:
        LOG.error("API_WRITE_TOKEN missing – worker stopped")
        return

    while True:
        payload = fetch_option_chain_sim()
        post_snapshot(payload)
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
