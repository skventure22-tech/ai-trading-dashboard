#!/usr/bin/env python3
"""
Render Background Worker – Option Chain Publisher (FINAL)

- Posts option-chain snapshots to PHP API
- Compatible with Hostinger + LiteSpeed
- Uses X-API-KEY header (validated ✅)
- No open ports (Background Worker safe)
"""

import os
import time
import json
import math
import logging
import requests
from typing import List, Dict

# ===================== LOGGING =====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
LOG = logging.getLogger("option_chain_worker")

# ===================== CONFIG =====================
SERVER_API = os.getenv(
    "SERVER_API",
    "https://surgialgo.shop/api/receive_oc_snapshot.php"
)

API_WRITE_TOKEN = os.getenv(
    "API_WRITE_TOKEN",
    "REPLACE_ME"
)

SIM_MODE = os.getenv("SIM_MODE", "true").lower() == "true"
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "3"))

UNDERLYING_ID = int(os.getenv("UNDERLYING_ID", "1"))   # NIFTY
EXPIRY_DATE   = os.getenv("EXPIRY_DATE", "2025-12-09")
STRIKE_STEP   = int(os.getenv("STRIKE_STEP", "50"))
STRIKE_RANGE  = int(os.getenv("STRIKE_RANGE", "500"))

HEADERS = {
    "Content-Type": "application/json",
    "X-API-KEY": API_WRITE_TOKEN
}

# ===================== SIM OPTION CHAIN =====================
def fetch_option_chain_sim() -> Dict:
    spot = 26186.45
    atm = round(spot / STRIKE_STEP) * STRIKE_STEP

    rows: List[Dict] = []

    for strike in range(atm - STRIKE_RANGE, atm + STRIKE_RANGE + STRIKE_STEP, STRIKE_STEP):
        premium = max(5.0, abs(spot - strike) * 0.45)

        rows.append({
            "strike_price": strike,
            "option_type": "CE",
            "ltp": round(premium, 2),
            "oi": 100000 + abs(atm - strike) * 10
        })

        rows.append({
            "strike_price": strike,
            "option_type": "PE",
            "ltp": round(premium, 2),
            "oi": 120000 + abs(atm - strike) * 12
        })

    return {
        "underlying_id": UNDERLYING_ID,
        "expiry_date": EXPIRY_DATE,
        "underlying_price": spot,
        "rows": rows
    }

# ===================== POST SNAPSHOT =====================
def post_snapshot(payload: Dict):
    try:
        r = requests.post(
            SERVER_API,
            headers=HEADERS,
            json=payload,
            timeout=10
        )

        if r.status_code != 200:
            LOG.error("HTTP %s | %s", r.status_code, r.text)
            return

        res = r.json()

        if res.get("ok"):
            LOG.info(
                "Snapshot OK | id=%s | rows=%s",
                res.get("snapshot_id"),
                res.get("rows_saved")
            )
        else:
            LOG.error("API ERROR: %s", res)

    except Exception as e:
        LOG.exception("POST FAILED")

# ===================== MAIN LOOP =====================
def main():
    LOG.info("🚀 Option Chain Worker started")
    LOG.info("API = %s", SERVER_API)
    LOG.info("SIM_MODE = %s | POLL = %ss", SIM_MODE, POLL_INTERVAL)

    if API_WRITE_TOKEN in ("", "REPLACE_ME"):
        LOG.error("API_WRITE_TOKEN missing – stopping worker")
        return

    while True:
        payload = fetch_option_chain_sim()
        post_snapshot(payload)
        time.sleep(POLL_INTERVAL)

# ===================== ENTRY =====================
if __name__ == "__main__":
    main()
