#!/usr/bin/env python3
"""
Render Background Worker – Option Chain Publisher (LIVE SmartAPI)
- Uses Angel One SmartAPI
- Auto login + session reuse
- SIM_MODE fallback
- Pushes data to PHP API
"""

import os
import time
import json
import math
import logging
import requests
import pyotp
from typing import List, Dict

# ================= ENV =================
SERVER_API = os.getenv(
    "SNAPSHOT_POST_URL",
    "https://surgialgo.shop/api/receive_oc_snapshot.php"
)
API_WRITE_TOKEN = os.getenv("API_WRITE_TOKEN")

SMARTAPI_BASE = os.getenv("SMARTAPI_BASE")
SMARTAPI_API_KEY = os.getenv("SMARTAPI_API_KEY")
SMARTAPI_CLIENT_CODE = os.getenv("SMARTAPI_CLIENT_CODE")
SMARTAPI_PIN = os.getenv("SMARTAPI_PIN")
SMARTAPI_TOTP_SECRET = os.getenv("SMARTAPI_TOTP_SECRET")
SMARTAPI_SESSION_FILE = os.getenv(
    "SMARTAPI_SESSION_FILE",
    "/home/u402604302/storage/smartapi_session.json"
)

SIM_MODE = os.getenv("SIM_MODE", "1") == "1"
POLL_INTERVAL = int(os.getenv("OC_POLL_INTERVAL", "2"))

UNDERLYING_ID = 1        # NIFTY
EXPIRY_DATE = "2025-12-09"
STRIKE_STEP = 50
STRIKE_RANGE = 500

# ================= LOG =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
LOG = logging.getLogger("OC_WORKER")

HEADERS = {
    "Content-Type": "application/json",
    "X-API-KEY": API_WRITE_TOKEN
}

# ================= SMARTAPI =================
def smartapi_login() -> str:
    totp = pyotp.TOTP(SMARTAPI_TOTP_SECRET).now()

    r = requests.post(
        f"{SMARTAPI_BASE}/rest/auth/angelbroking/user/v1/loginByPassword",
        headers={
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": SMARTAPI_API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "clientcode": SMARTAPI_CLIENT_CODE,
            "password": SMARTAPI_PIN,
            "totp": totp
        },
        timeout=10
    )
    r.raise_for_status()
    data = r.json()

    token = data["data"]["jwtToken"]
    with open(SMARTAPI_SESSION_FILE, "w") as f:
        json.dump({"jwt": token}, f)

    LOG.info("SmartAPI login success")
    return token


def get_smartapi_token() -> str:
    try:
        if os.path.exists(SMARTAPI_SESSION_FILE):
            with open(SMARTAPI_SESSION_FILE) as f:
                return json.load(f)["jwt"]
    except Exception:
        pass
    return smartapi_login()


# ================= FETCH =================
def fetch_option_chain_live() -> Dict:
    token = get_smartapi_token()

    r = requests.get(
        f"{SMARTAPI_BASE}/rest/secure/angelbroking/market/v1/optionChain",
        headers={
            "Authorization": f"Bearer {token}",
            "X-PrivateKey": SMARTAPI_API_KEY,
            "X-UserType": "USER",
            "X-SourceID": "WEB"
        },
        params={
            "symbol": "NIFTY",
            "expiry": EXPIRY_DATE
        },
        timeout=10
    )

    if r.status_code == 401:
        token = smartapi_login()
        return fetch_option_chain_live()

    r.raise_for_status()
    oc = r.json()["data"]

    rows = []
    spot = float(oc["underlyingValue"])

    for s in oc["options"]:
        rows.append({
            "strike_price": s["strikePrice"],
            "option_type": s["optionType"],
            "ltp": s["ltp"],
            "oi": s.get("openInterest", 0)
        })

    return {
        "underlying_id": UNDERLYING_ID,
        "expiry_date": EXPIRY_DATE,
        "underlying_price": spot,
        "rows": rows
    }


def fetch_option_chain_sim() -> Dict:
    spot = 26186.45
    atm = round(spot / STRIKE_STEP) * STRIKE_STEP
    rows = []

    for strike in range(atm - STRIKE_RANGE, atm + STRIKE_RANGE + STRIKE_STEP, STRIKE_STEP):
        rows.append({
            "strike_price": strike,
            "option_type": "CE",
            "ltp": round(max(5, abs(spot - strike) * 0.45), 2),
            "oi": 100000
        })
        rows.append({
            "strike_price": strike,
            "option_type": "PE",
            "ltp": round(max(5, abs(spot - strike) * 0.45), 2),
            "oi": 120000
        })

    return {
        "underlying_id": UNDERLYING_ID,
        "expiry_date": EXPIRY_DATE,
        "underlying_price": spot,
        "rows": rows
    }


# ================= POST =================
def post_snapshot(payload: Dict):
    r = requests.post(
        SERVER_API,
        headers=HEADERS,
        json=payload,
        timeout=10
    )
    r.raise_for_status()
    return r.json()


# ================= MAIN LOOP =================
def main():
    LOG.info("Option Chain Worker started | SIM_MODE=%s", SIM_MODE)

    while True:
        try:
            payload = (
                fetch_option_chain_sim()
                if SIM_MODE else
                fetch_option_chain_live()
            )

            res = post_snapshot(payload)
            LOG.info("Snapshot OK | id=%s rows=%s",
                     res.get("snapshot_id"),
                     res.get("rows_saved"))

        except Exception as e:
            LOG.error("Worker error: %s", e)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
