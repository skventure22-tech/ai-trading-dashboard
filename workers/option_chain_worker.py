import time, json, os, requests, datetime

POST_URL = os.getenv("SNAPSHOT_POST_URL")
API_TOKEN = os.getenv("API_WRITE_TOKEN")
POLL = int(os.getenv("OC_POLL_INTERVAL", "3"))

UNDERLYINGS = [
    {"id": 1, "symbol": "NIFTY",     "step": 50},
    {"id": 2, "symbol": "BANKNIFTY", "step": 100},
    {"id": 3, "symbol": "SENSEX",    "step": 100},
]

def detect_expiry():
    today = datetime.date.today()
    days = (3 - today.weekday()) % 7
    return (today + datetime.timedelta(days=days)).strftime("%Y-%m-%d")

def build_payload(u, spot):
    atm = round(spot / u["step"]) * u["step"]
    rows = []

    for strike in range(atm-300, atm+301, u["step"]):
        diff = abs(spot - strike)
        rows.append({
            "strike_price": strike,
            "option_type": "CE",
            "ltp": round(diff * 0.45 + 5, 2),
            "oi": 100000 + int(diff * 20),
            "oi_change": int(diff * 5)
        })
        rows.append({
            "strike_price": strike,
            "option_type": "PE",
            "ltp": round(diff * 0.45 + 5, 2),
            "oi": 120000 + int(diff * 20),
            "oi_change": -int(diff * 5)
        })

    return {
        "underlying_id": u["id"],
        "expiry_date": detect_expiry(),
        "underlying_price": round(spot, 2),
        "rows": rows
    }

print("🚀 Angel Option Chain Worker LIVE")

while True:
    for u in UNDERLYINGS:
        try:
            if u["symbol"] == "NIFTY":
                spot = 26186.45
            elif u["symbol"] == "BANKNIFTY":
                spot = 59069.20
            else:
                spot = 84929.36

            payload = build_payload(u, spot)

            r = requests.post(
                POST_URL,
                headers={
                    "X-API-KEY": API_TOKEN,
                    "Content-Type": "application/json"
                },
                data=json.dumps(payload),
                timeout=10
            )

            print(f"{u['symbol']} OK {r.status_code}")

        except Exception as e:
            print(f"{u['symbol']} ERROR", e)

    time.sleep(POLL)
