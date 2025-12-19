import time
import json
import os
import requests
from datetime import datetime

SNAPSHOT_POST_URL = os.getenv("SNAPSHOT_POST_URL")
API_WRITE_TOKEN   = os.getenv("API_WRITE_TOKEN")

if not SNAPSHOT_POST_URL or not API_WRITE_TOKEN:
    raise RuntimeError("ENV vars missing")

POLL_INTERVAL = int(os.getenv("OC_POLL_INTERVAL", "3"))
SIM_MODE = os.getenv("SIM_MODE", "1") == "1"

UNDERLYINGS = [
    {"id": 1, "symbol": "NIFTY", "step": 50,  "range": 150, "spot": 26186.45},
    {"id": 2, "symbol": "BANKNIFTY", "step": 100, "range": 300, "spot": 48250.00},
    {"id": 3, "symbol": "SENSEX", "step": 100, "range": 300, "spot": 72100.00},
]

def smart_expiry():
    today = datetime.now().strftime("%Y-%m-%d")
    return today  # later replace with NSE calendar logic

def build_chain(u):
    spot = u["spot"]
    step = u["step"]
    atm  = round(spot / step) * step
    rows = []

    for strike in range(atm - u["range"], atm + u["range"] + step, step):
        ltp = round(max(5, abs(spot - strike) * 0.45), 1)
        rows.append({
            "strike_price": strike,
            "option_type": "CE",
            "ltp": ltp,
            "oi": 100000
        })
        rows.append({
            "strike_price": strike,
            "option_type": "PE",
            "ltp": ltp,
            "oi": 120000
        })

    return {
        "underlying_id": u["id"],
        "expiry_date": smart_expiry(),
        "underlying_price": spot,
        "rows": rows
    }

def post(payload):
    r = requests.post(
        SNAPSHOT_POST_URL,
        headers={
            "X-API-KEY": API_WRITE_TOKEN,
            "Content-Type": "application/json"
        },
        data=json.dumps(payload),
        timeout=10
    )
    print("POST", payload["underlying_id"], r.status_code, r.text)

def main():
    print("🚀 Option Chain Worker LIVE")

    while True:
        for u in UNDERLYINGS:
            try:
                payload = build_chain(u)
                post(payload)
            except Exception as e:
                print("ERROR:", e)

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
