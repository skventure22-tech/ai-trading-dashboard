import time
import json
import os
import requests
from datetime import datetime

# ======================================================
# ENV CONFIG
# ======================================================
SNAPSHOT_POST_URL = os.getenv(
    "SNAPSHOT_POST_URL",
#    "https://surgialgo.shop/api/receive_oc_snapshot.php"
)

API_WRITE_TOKEN = os.getenv("API_WRITE_TOKEN")
SIM_MODE = os.getenv("SIM_MODE", "1") == "1"
POLL_INTERVAL = int(os.getenv("OC_POLL_INTERVAL", "3"))

if not API_WRITE_TOKEN:
    raise RuntimeError("API_WRITE_TOKEN is missing")

# ======================================================
# UNDERLYINGS CONFIG
# ======================================================
UNDERLYINGS = [
    {"id": 1, "symbol": "NIFTY",      "strike_step": 50,  "strike_range": 150},
    {"id": 2, "symbol": "BANKNIFTY",  "strike_step": 100, "strike_range": 300},
    {"id": 3, "symbol": "SENSEX",     "strike_step": 100, "strike_range": 300},
]

# ======================================================
# HELPERS
# ======================================================
def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def smart_expiry(symbol: str) -> str:
    """
    👉 Future-ready expiry logic
    Currently static / override by ENV
    """
    return os.getenv("EXPIRY_DATE", "2025-12-09")


# ======================================================
# SIMULATED OPTION CHAIN (SAFE MODE)
# ======================================================
def fetch_option_chain_sim(underlying):
    spot_map = {
        "NIFTY": 26186.45,
        "BANKNIFTY": 48250.00,
        "SENSEX": 72100.00,
    }

    spot = spot_map.get(underlying["symbol"], 10000)
    step = underlying["strike_step"]
    rng  = underlying["strike_range"]

    atm = round(spot / step) * step
    rows = []

    for strike in range(atm - rng, atm + rng + step, step):
        price = max(5, abs(spot - strike) * 0.45)

        rows.append({
            "strike_price": strike,
            "option_type": "CE",
            "ltp": round(price, 2),
            "oi": 100000
        })

        rows.append({
            "strike_price": strike,
            "option_type": "PE",
            "ltp": round(price, 2),
            "oi": 120000
        })

    return {
        "underlying_id": underlying["id"],
        "expiry_date": smart_expiry(underlying["symbol"]),
        "underlying_price": spot,
        "rows": rows
    }


# ======================================================
# PUSH SNAPSHOT TO PHP API
# ======================================================
def post_snapshot(payload: dict):
    r = requests.post(
        SNAPSHOT_POST_URL,
        headers={
            "X-API-KEY": API_WRITE_TOKEN,
            "Content-Type": "application/json"
        },
        data=json.dumps(payload),
        timeout=10
    )
    return r


# ======================================================
# MAIN LOOP
# ======================================================
def main():
    log("🚀 Option Chain Worker STARTED")
    log(f"SIM_MODE = {SIM_MODE}")
    log(f"POLL_INTERVAL = {POLL_INTERVAL}s")

    while True:
        for u in UNDERLYINGS:
            try:
                if SIM_MODE:
                    payload = fetch_option_chain_sim(u)
                else:
                    # 🔮 FUTURE: Angel One API fetch here
                    continue

                resp = post_snapshot(payload)

                if resp.status_code == 200:
                    log(f"✅ {u['symbol']} snapshot saved")
                else:
                    log(f"⚠️ {u['symbol']} POST {resp.status_code} {resp.text}")

            except Exception as e:
                log(f"❌ ERROR {u['symbol']} → {e}")

        time.sleep(POLL_INTERVAL)


# ======================================================
# ENTRY
# ======================================================
if __name__ == "__main__":
    main()
