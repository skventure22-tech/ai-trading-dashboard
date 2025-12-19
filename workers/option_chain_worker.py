#!/usr/bin/env python3
"""
Render Background Worker – Option Chain Publisher (FINAL)

- Runs as Render Background Worker (NO PORT)
- SIM_MODE / LIVE_MODE switch
- Posts compact option-chain snapshots to PHP API
- Uses X-API-KEY (Hostinger/LiteSpeed safe)
- Never crashes; retries safely
"""

import os
import time
import json
import math
import logging
import requests
from typing import Dict, List

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
LOG = logging.getLogger("option_chain_worker")

# ================= CONFIG (ENV FIRST) =================
SERVER_API = os.getenv(
    "SERVER_API",
    "https://surgialgo.shop/api/receive_oc_snapshot.php"
)

API_WRITE_TOKEN = os.getenv("API_WRITE_TOKEN", "").strip()

SIM_MODE = os.getenv("SIM_MODE", "1") == "1"
POLL_INTERVAL = int(os.getenv("OC_POLL_INTERVAL", "2"))

UNDERLYING_ID = int(os.getenv("UNDERLYING_ID", "1"))      # NIFTY
EXPIRY_DATE = os.getenv("EXPIRY_DATE", "2025-12-09")
STRIKE_STEP = int(os.getenv("STRIKE_STEP", "50"))
STRIKE_RANGE = int(os.getenv("STRIKE_RANGE", "500"))     # +/- points

HEADERS = {
    "Content-Type": "application/json",
    "X-API-KEY": API_WRITE_TOKEN,
}

# ================= VALIDATION =================
if not API_WRITE_TOKEN:
    raise RuntimeError("API_WRITE_TOKEN missing in Render ENV")

# ================= OPTION CHAIN (SIM) =================
def fetch_option_chain_sim() -> Dict:
    spot = 26186.45
    atm = round(spot / STRIKE_STEP) * STRIKE_STEP

    rows: List[Dict] = []

    for strike in range(atm - STRIKE_RANGE, atm + STRIKE_RANGE + STRIKE_STEP, STRIKE_STEP):
        dist = abs(spot - strike)

        rows.append({
            "strike_price": strike,
            "option_type": "CE",
            "ltp": round(max(5, dist * 0.45), 2),
            "oi": 100000 + int(dist * 10),
        })
        rows.append({
            "strike_price": strike,
            "option_type": "PE",
            "ltp": round(max(5, dist * 0.45), 2),
            "oi": 120000 + int(dist * 12),
        })

    return {
        "underlying_id": UNDERLYING_ID,
        "expiry_date": EXPIRY_DATE,
        "underlying_price": spot,
        "rows": rows,
    }

# ================= POST SNAPSHOT =================
def post_snapshot(payload: Dict):
    try:
        r = requests.post(
            SERVER_API,
            headers=HEADERS,
            json=payload,
            timeout=10,
        )

        if r.status_code != 200:
            LOG.error("HTTP %s | %s", r.status_code, r.text)
            return

        res = r.json()
        if not res.get("ok"):
            LOG.error("API ERROR: %s", res)
        else:
            LOG.info(
                "Snapshot %s | rows=%s",
                res.get("snapshot_id"),
                res.get("rows_saved"),
            )

    except Exception as e:
        LOG.exception("Post failed")

# ================= MAIN LOOP =================
def main():
    LOG.info("Worker started | SIM_MODE=%s | Poll=%ss", SIM_MODE, POLL_INTERVAL)

    while True:
        try:
            payload = fetch_option_chain_sim() if SIM_MODE else None
            if payload:
                post_snapshot(payload)
        except Exception:
            LOG.exception("Loop error")

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
