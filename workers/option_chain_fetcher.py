import time
import json
import os
import requests
import datetime
from typing import Dict

# ==========================
# ENV CONFIG
# ==========================
PHP_URL = os.getenv(
    "SNAPSHOT_POST_URL",
    "https://surgialgo.shop/api/receive_oc_snapshot.php"
)

API_TOKEN = os.getenv("API_WRITE_TOKEN")
if not API_TOKEN:
    raise RuntimeError("API_WRITE_TOKEN not set")

POLL_INTERVAL = int(os.getenv("OC_POLL_INTERVAL", "3"))
STRIKE_RANGE = int(os.getenv("STRIKE_RANGE", "150"))  # ± range

# ==========================
# UNDERLYINGS CONFIG
# ==========================
UNDERLYINGS = [
    {"id": 1, "symbol": "NIFTY",     "step": 50,  "spot": 26186.45},
    {"id": 2, "symbol": "BANKNIFTY", "step": 100, "spot": 48250.00},
    {"id": 3, "symbol": "SENSEX",    "step": 100, "spot": 72100.00},
]

# ==========================
# UTILS
# ==========================
def detect_expiry(symbol: str) -> str:
    """
    Auto weekly expiry:
    NSE weekly expiry = Thursday
    """
    today = datetime.date.today()
    days_ahead = (3 - today.weekday()) % 7  # Thursday = 3
    expiry = today + datetime.timedelta(days=days_ahead)
    return expiry.strftime("%Y-%m-%d")


def build_payload(u: Dict) -> Dict:
    expiry = detect_expiry(u["symbol"])
    spot   = float(u["spot"])
    step   = int(u["step"])
    atm    = round(spot / step) * step

    rows = []
    for strike in range(
        atm - STRIKE_RANGE,
        atm + STRIKE_RANGE + step,
        step
    ):
        ce_ltp = round(abs(spot - strike) * 0.40 + 10, 2)
        pe_ltp = round(abs(spot - strike) * 0.40 + 10, 2)

        rows.append({
            "strike_price": strike,
            "option_type": "CE",
            "ltp": ce_ltp,
            "oi": 100000
        })
        rows.append({
            "strike_price": strike,
            "option_type": "PE",
            "ltp": pe_ltp,
            "oi": 120000
        })

    return {
        "underlying_id": u["id"],
        "expiry_date": expiry,
        "underlying_price": spot,
        "rows": rows
    }


# ==========================
# MAIN LOOP
# ==========================
def main():
    print("🚀 Option Chain Worker started")
    print(f"POST URL: {PHP_URL}")
    print(f"POLL INTERVAL: {POLL_INTERVAL}s")

    while True:
        for u in UNDERLYINGS:
            payload = build_payload(u)
            try:
                r = requests.post(
                    PHP_URL,
                    headers={
                        "X-API-KEY": API_TOKEN,
                        "Content-Type": "application/json"
                    },
                    data=json.dumps(payload),
                    timeout=10
                )

                if r.status_code == 200:
                    print(
                        f"✅ {u['symbol']} | expiry {payload['expiry_date']} | OK"
                    )
                else:
                    print(
                        f"⚠️ {u['symbol']} | HTTP {r.status_code} | {r.text}"
                    )

            except Exception as e:
                print(f"❌ {u['symbol']} ERROR:", e)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
