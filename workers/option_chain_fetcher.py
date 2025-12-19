import time
import json
import os
import requests
import datetime
from typing import Dict, List

# =========================
# ENV CONFIG
# =========================
PHP_URL = os.getenv("SNAPSHOT_POST_URL")
API_TOKEN = os.getenv("API_WRITE_TOKEN")

if not PHP_URL or not API_TOKEN:
    raise RuntimeError("SNAPSHOT_POST_URL or API_WRITE_TOKEN missing")

POLL_INTERVAL = int(os.getenv("OC_POLL_INTERVAL", "3"))
STRIKE_RANGE = int(os.getenv("STRIKE_RANGE", "300"))

TIMEOUT = 10

# =========================
# UNDERLYINGS CONFIG
# =========================
UNDERLYINGS: List[Dict] = [
    {"id": 1, "symbol": "NIFTY",     "spot": 26186.45, "step": 50},
    {"id": 2, "symbol": "BANKNIFTY", "spot": 48250.00, "step": 100},
    {"id": 3, "symbol": "SENSEX",    "spot": 72100.00, "step": 100},
]

# =========================
# EXPIRY AUTO DETECT
# =========================
def detect_weekly_expiry(symbol: str) -> str:
    """
    NSE weekly expiry (Thursday)
    """
    today = datetime.date.today()
    days_ahead = (3 - today.weekday()) % 7  # Thursday = 3
    expiry = today + datetime.timedelta(days=days_ahead)

    # If today is Thursday but market already closed, push next week
    if today.weekday() == 3 and datetime.datetime.now().hour >= 15:
        expiry = expiry + datetime.timedelta(days=7)

    return expiry.strftime("%Y-%m-%d")

# =========================
# BUILD PAYLOAD
# =========================
def build_payload(u: Dict) -> Dict:
    expiry = detect_weekly_expiry(u["symbol"])
    spot = float(u["spot"])
    step = int(u["step"])

    atm = round(spot / step) * step

    rows = []
    for strike in range(
        atm - STRIKE_RANGE,
        atm + STRIKE_RANGE + step,
        step
    ):
        ce_ltp = round(abs(spot - strike) * 0.4 + 10, 2)
        pe_ltp = round(abs(spot - strike) * 0.4 + 10, 2)

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

# =========================
# MAIN LOOP
# =========================
print("🚀 Option Chain Worker started")
print(f"Poll interval: {POLL_INTERVAL}s")

while True:
    cycle_start = time.time()

    for u in UNDERLYINGS:
        try:
            payload = build_payload(u)

            response = requests.post(
                PHP_URL,
                headers={
                    "X-API-KEY": API_TOKEN,
                    "Content-Type": "application/json"
                },
                data=json.dumps(payload),
                timeout=TIMEOUT
            )

            if response.status_code == 200:
                print(
                    f"[OK] {u['symbol']} "
                    f"expiry={payload['expiry_date']} "
                    f"rows={len(payload['rows'])}"
                )
            else:
                print(
                    f"[WARN] {u['symbol']} "
                    f"HTTP {response.status_code} "
                    f"{response.text[:200]}"
                )

        except Exception as e:
            print(f"[ERROR] {u['symbol']} -> {e}")

    elapsed = round(time.time() - cycle_start, 2)
    sleep_time = max(1, POLL_INTERVAL - elapsed)
    time.sleep(sleep_time)
