import time, json, os, requests, datetime

PHP_URL = os.getenv("SNAPSHOT_POST_URL")
API_TOKEN = os.getenv("API_WRITE_TOKEN")

UNDERLYINGS = [
    {"id": 1, "symbol": "NIFTY",     "step": 50},
    {"id": 2, "symbol": "BANKNIFTY", "step": 100},
    {"id": 3, "symbol": "SENSEX",    "step": 100},
]

STRIKE_RANGE = 300
POLL_INTERVAL = int(os.getenv("OC_POLL_INTERVAL", 3))

def detect_expiry():
    today = datetime.date.today()
    days = (3 - today.weekday()) % 7
    return (today + datetime.timedelta(days=days)).strftime("%Y-%m-%d")

def fetch_spot(symbol: str) -> float:
    """
    TODO: Replace with Angel One LTP API
    Temporary fallback values ONLY for testing
    """
    fallback = {
        "NIFTY": 26186.45,
        "BANKNIFTY": 59069.20,
        "SENSEX": 84929.36
    }
    return fallback[symbol]

def build_payload(u):
    spot = fetch_spot(u["symbol"])
    step = u["step"]
    expiry = detect_expiry()
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

print("🚀 Option Chain Worker running")

while True:
    for u in UNDERLYINGS:
        try:
            payload = build_payload(u)
            r = requests.post(
                PHP_URL,
                headers={
                    "X-API-KEY": API_TOKEN,
                    "Content-Type": "application/json"
                },
                data=json.dumps(payload),
                timeout=10
            )
            print(u["symbol"], r.status_code)
        except Exception as e:
            print("ERROR:", e)

    time.sleep(POLL_INTERVAL)
