#!/usr/bin/env python3
"""
Render Background Worker – Option Chain Publisher

- SIM_MODE (safe) / LIVE_MODE switch
- Posts compact option chain snapshots to PHP API
- Graceful retries, no crash loops
- Low CPU / memory (shared hosting friendly)
"""

import os
import time
import json
import math
import logging
import random
from typing import List, Dict

import requests

# ==============================
# CONFIG (via Render ENV vars)
# ==============================
SERVER_API = os.getenv(
    "SERVER_API",
    "https://surgialgo.shop/api/receive_oc_snapshot.php"
)

API_WRITE_TOKEN = os.getenv(
    "API_WRITE_TOKEN",
    "1d0050a2f757a1aa39e252a89076bcdf0a82c7333e62d3c1c1e9c9012b187d80"
)

SIM_MODE = os.getenv("SIM_MODE", "1") == "1"
POLL_INTERVAL = max(2, int(os.getenv("OC_POLL_INTERVAL", "3")))

UNDERLYING_ID = int(os.getenv("UNDERLYING_ID", "1"))  # NIFTY
EXPIRY_DATE   = os.getenv("EXPIRY_DATE", "2025-12-09")
STRIKE_STEP   = int(os.getenv("STRIKE_STEP", "50"))
STRIKE_RANGE  = int(os.getenv("STRIKE_RANGE", "300"))  # ATM ± range

# ==============================
# LOGGING
# ==============================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
LOG = logging.getLogger("oc_worker")

# ==============================
# HEADERS
# ==============================
HEADERS = {
    "X-API-KEY": API_WRITE_TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# ==============================
# SIM OPTION CHAIN (SAFE)
# ==============================
def fetch_option_chain_sim() -> Dict:
    """
    Generate realistic, stable SIM option chain around ATM.
    """
    # Stable-ish spot with tiny noise
    base_spot = 26150.0
    spot = base_spot + random.uniform(-40, 40)

    atm = int(round(spot / STRIKE_STEP) * STRIKE_STEP)

    rows: List[Dict] = []
    for strike in range(atm - STRIKE_RANGE, atm + STRIKE_RANGE + STRIKE_STEP, STRIKE_STEP):
        intrinsic = abs(spot - strike)
        premium = max(5.0, intrinsic * 0.45)

        rows.append({
            "strike_price": strike,
            "option_type": "CE",
            "ltp": round(premium + random.uniform(-2, 2), 2),
            "oi": 100000 + abs(atm - strike) * 12
        })
        rows.append({
            "strike_price": strike,
            "option_type": "PE",
            "ltp": round(premium + random.uniform(-2, 2), 2),
            "oi": 120000 + abs(atm - strike) * 14
        })

    return {
        "underlying_id": UNDERLYING_ID,
        "expiry_date": EXPIRY_DATE,
        "underlying_price": round(spot, 2),
        "rows": rows
    }

# ==============================
# LIVE FETCH (PLACEHOLDER)
# ==============================
def fetch_option_chain_live() -> Dict:
    """
    Placeholder for SmartAPI live fetch.
    Replace internals only when LIVE trading enabled.
    """
    raise NotImplementedError("LIVE_MODE not implemented yet")

# ==============================
# POST TO PHP API
# ==============================
def post_snapshot(payload: Dict) -> bool:
    try:
        r = requests.post(
            SERVER_API,
            headers=HEADERS,
            data=json.dumps(payload),
            timeout=10
        )

        if r.status_code != 200:
            LOG.error("POST failed | HTTP %s | %s", r.status_code, r.text)
            return False

        resp = r.json()
        if not resp.get("ok"):
            LOG.error("API error response: %s", resp)
            return False

        LOG.info(
            "Snapshot OK | id=%s | rows=%s",
            resp.get("snapshot_id"),
            resp.get("rows_saved")
        )
        return True

    except Exception as e:
        LOG.exception("POST exception: %s", e)
        return False

# ==============================
# MAIN LOOP
# ==============================
def main():
    LOG.info(
        "Worker started | SIM_MODE=%s | interval=%ss | endpoint=%s",
        SIM_MODE, POLL_INTERVAL, SERVER_API
    )

    backoff = 2

    while True:
        try:
            if SIM_MODE:
                payload = fetch_option_chain_sim()
            else:
                payload = fetch_option_chain_live()

            ok = post_snapshot(payload)

            # reset backoff on success
            backoff = 2 if ok else min(backoff * 2, 60)

        except Exception as e:
            LOG.exception("Unhandled error: %s", e)
            backoff = min(backoff * 2, 60)

        time.sleep(max(POLL_INTERVAL, backoff))


if __name__ == "__main__":
    main()
