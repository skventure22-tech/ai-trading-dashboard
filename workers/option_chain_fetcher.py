import time
import json
import os
import requests

PHP_RECEIVE_URL = os.getenv(
    "SNAPSHOT_POST_URL",
    "https://surgialgo.shop/api/receive_oc_snapshot.php"
)

API_WRITE_TOKEN = os.getenv("API_WRITE_TOKEN")

if not API_WRITE_TOKEN:
    raise RuntimeError("API_WRITE_TOKEN not set")

SIM_MODE = True
POLL_INTERVAL = 3

UNDERLYING_ID = 1
EXPIRY_DATE = "2025-12-09"
STRIKE_STEP = 50

def fetch_option_chain_sim():
    spot = 26186.45
    atm = round(spot / STRIKE_STEP) * STRIKE_STEP
    rows = []

    for strike in range(atm - 150, atm + 200, STRIKE_STEP):
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

def main():
    print("🚀 Option Chain Worker started")

    while True:
        try:
            payload = fetch_option_chain_sim()

            r = requests.post(
                PHP_RECEIVE_URL,
                headers={
                    "X-API-KEY": API_WRITE_TOKEN,
                    "Content-Type": "application/json"
                },
                data=json.dumps(payload),
                timeout=10
            )

            print("POST", r.status_code, r.text)

        except Exception as e:
            print("ERROR:", e)

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
