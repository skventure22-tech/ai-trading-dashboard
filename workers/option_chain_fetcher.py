import time, json, os, requests, datetime

PHP_URL = os.getenv("SNAPSHOT_POST_URL")
API_TOKEN = os.getenv("API_WRITE_TOKEN")

UNDERLYINGS = [
    {"id": 1, "symbol": "NIFTY",     "spot": 26186.45, "step": 50},
    {"id": 2, "symbol": "BANKNIFTY", "spot": 48250.00, "step": 100},
    {"id": 3, "symbol": "SENSEX",    "spot": 72100.00, "step": 100},
]

STRIKE_RANGE = 150
POLL_INTERVAL = int(os.getenv("OC_POLL_INTERVAL", 3))

def detect_expiry(symbol: str) -> str:
    """Auto weekly expiry (Thursday)"""
    today = datetime.date.today()
    days = (3 - today.weekday()) % 7  # Thursday
    expiry = today + datetime.timedelta(days=days)
    return expiry.strftime("%Y-%m-%d")

def build_payload(u):
    expiry = detect_expiry(u["symbol"])
    spot = u["spot"]
    step = u["step"]
    atm = round(spot / step) * step

    rows = []
    for strike in range(atm - STRIKE_RANGE, atm + STRIKE_RANGE + step, step):
        rows.append({
            "strike_price": strike,
            "option_type": "CE",
            "ltp": round(abs(spot - strike) * 0.4 + 10, 2),
            "oi": 100000
        })
        rows.append({
            "strike_price": strike,
            "option_type": "PE",
            "ltp": round(abs(spot - strike) * 0.4 + 10, 2),
            "oi": 120000
        })

    return {
        "underlying_id": u["id"],
        "expiry_date": expiry,
        "underlying_price": spot,
        "rows": rows
    }

print("🚀 OC Worker started")

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
            print(f"{u['symbol']} ->", r.status_code)
        except Exception as e:
            print("ERROR:", e)

    time.sleep(POLL_INTERVAL)
