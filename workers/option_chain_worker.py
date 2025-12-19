import time
import json
import requests
import os

SERVER_API = os.getenv(
    "SERVER_API",
    "https://surgialgo.shop/api/receive_oc_snapshot.php"
)

API_WRITE_TOKEN = os.getenv(
    "API_WRITE_TOKEN",
    "1d0050a2f757a1aa39e252a89076bcdf0a82c7333e62d3c1c1e9c9012b187d80"
)

POLL_INTERVAL = int(os.getenv("OC_POLL_INTERVAL", "3"))

UNDERLYING_ID = 1          # NIFTY
EXPIRY_DATE   = "2025-12-09"
STRIKE_STEP   = 50

def fetch_sim_option_chain():
    spot = 26186.45
    atm  = round(spot / STRIKE_STEP) * STRIKE_STEP

    rows = []

    # ATM ±3 strikes
    for i in range(-3, 4):
        strike = atm + (i * STRIKE_STEP)

        rows.append({
            "strike_price": strike,
            "option_type": "CE",
            "ltp": round(max(5, abs(spot - strike) * 0.45), 2),
            "oi": 100000 + abs(i) * 15000
        })

        rows.append({
            "strike_price": strike,
            "option_type": "PE",
            "ltp": round(max(5, abs(spot - strike) * 0.45), 2),
            "oi": 120000 + abs(i) * 15000
        })

    return {
        "underlying_id": UNDERLYING_ID,
        "expiry_date": EXPIRY_DATE,
        "underlying_price": spot,
        "rows": rows
    }

def main():
    print("🚀 Option Chain Worker running (ATM ±3)")

    while True:
        try:
            payload = fetch_sim_option_chain()

            r = requests.post(
                SERVER_API,
                headers={
                    "Authorization": f"Bearer {API_WRITE_TOKEN}",
                    "Content-Type": "application/json"
                },
                data=json.dumps(payload),
                timeout=10
            )

            print("POST", r.status_code, "ROWS:", len(payload["rows"]))

        except Exception as e:
            print("ERROR:", e)

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
